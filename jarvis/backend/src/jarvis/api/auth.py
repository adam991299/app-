"""Passkey login and the actions that change something (§10, §9.2).

- Only Adam: the first passkey can be created only with the one-time setup code from the
  server's ``.env``; more passkeys only by someone already logged in.
- Every action that changes something needs a login *and* a fresh passkey confirmation
  (Face ID) bound to exactly that action and its values, so a stolen session cookie alone
  cannot change anything.
- CSRF: cookies are SameSite=Strict, and every POST must come from the app's own origin
  with the ``X-Jarvis: 1`` header. Login and actions are rate limited.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from jarvis.risk.profiles import NAMES_SV, RiskProfile
from jarvis.store.auth import AuthStore
from jarvis.store.repo import Store

COOKIE = "jarvis_session"
MAX_DEPOSIT = Decimal(10_000_000)


@dataclass(frozen=True, slots=True)
class AuthConfig:
    rp_id: str  # the app's domain, e.g. jarvis.example.ts.net
    origin: str  # https://<domain>
    setup_code: str | None  # one-time code for the first passkey; None disables setup
    session_hours: int = 12
    challenge_seconds: int = 120


def auth_config_from_env(env: Mapping[str, str]) -> AuthConfig:
    domain = env.get("JARVIS_DOMAIN", "localhost").strip() or "localhost"
    code = env.get("JARVIS_PASSKEY_SETUP_CODE", "").strip()
    return AuthConfig(rp_id=domain, origin=f"https://{domain}", setup_code=code or None)


class RateLimiter:
    """At most ``limit`` requests per ``window`` seconds per client address."""

    def __init__(self, limit: int, window: float, now: Callable[[], float] = time.monotonic):
        self._limit, self._window, self._now = limit, window, now
        self._seen: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = self._now()
        seen = self._seen[key]
        while seen and now - seen[0] > self._window:
            seen.popleft()
        if len(seen) >= self._limit:
            raise HTTPException(429, "För många försök. Vänta en minut och försök igen.")
        seen.append(now)


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetupIn(_Body):
    setup_code: str = Field(default="", max_length=128)


class CredentialIn(_Body):
    credential: dict[str, Any]


class ActionOptionsIn(_Body):
    action: str = Field(pattern="^(deposit|risk_profile|control|budget|trading_mode)$")
    payload: dict[str, str]


class DepositIn(CredentialIn):
    amount: str = Field(max_length=32)
    note: str = Field(default="", max_length=200)


class RiskProfileIn(CredentialIn):
    profile: RiskProfile


class ControlIn(CredentialIn):
    command: Literal["pause", "resume", "kill_switch", "reset_kill_switch"]


class BudgetIn(CredentialIn):
    pct: str = Field(max_length=8)


class TradingModeIn(CredentialIn):
    mode: Literal["paper", "live"]
    phrase: str = Field(default="", max_length=64)
    budget_pct: str = Field(default="10", max_length=8)


LIVE_PHRASE = "JAG FÖRSTÅR RISKEN"
CONTROL_SV = {
    "pause": "Handeln är pausad. Öppna positioner skyddas av stoppordrarna hos mäklaren.",
    "resume": "Handeln är igång igen.",
    "kill_switch": (
        "Kill switch är aktiverad. Inga nya affärer tas förrän du startar handeln igen. "
        "Öppna positioner skyddas av stoppordrarna hos mäklaren."
    ),
    "reset_kill_switch": "Kill switch är avstängd och handeln kan börja igen.",
}


def _plain(value: Decimal) -> str:
    """10.0 -> "10", 12.5 -> "12.5"."""
    return format(value.normalize(), "f")


def parse_budget(text: str) -> Decimal:
    try:
        pct = Decimal(text)
    except InvalidOperation as error:
        raise HTTPException(422, "Budgeten måste vara ett tal i procent.") from error
    if (
        not pct.is_finite()
        or not Decimal(1) <= pct <= Decimal(100)
        or pct != pct.quantize(Decimal(1))
    ):
        raise HTTPException(422, "Budgeten är en hel procentsats mellan 1 och 100.")
    return pct


def action_purpose(action: str, payload: Mapping[str, str]) -> str:
    """Binds a confirmation to one action and its exact values."""
    body = json.dumps({"action": action, "payload": dict(payload)}, sort_keys=True)
    return "action:" + hashlib.sha256(body.encode()).hexdigest()


def _b64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _challenge_of(credential: Mapping[str, Any]) -> bytes:
    try:
        client = json.loads(_b64url(credential["response"]["clientDataJSON"]))
        return _b64url(client["challenge"])
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(400, "Svaret från din passkey gick inte att läsa.") from error


def _options(options: object) -> JSONResponse:
    return JSONResponse(json.loads(options_to_json(options)))  # type: ignore[arg-type]


def create_auth_router(
    auth: AuthStore, store: Store, config: AuthConfig, clock: Callable[[], datetime]
) -> APIRouter:
    router = APIRouter()
    limiter = RateLimiter(limit=20, window=60)

    def guard(request: Request) -> None:
        """Same-origin POSTs only, with the app's header, within the rate limit."""
        if request.headers.get("x-jarvis") != "1" or request.headers.get("origin") != config.origin:
            raise HTTPException(403, "Förfrågan kom inte från appen.")
        limiter.check(request.client.host if request.client else "unknown")

    async def logged_in(request: Request) -> bool:
        token = request.cookies.get(COOKIE)
        return token is not None and await auth.session_valid(token, now=clock())

    async def require_login(request: Request) -> None:
        if not await logged_in(request):
            raise HTTPException(401, "Du behöver logga in med din passkey.")

    async def new_challenge(purpose: str) -> bytes:
        now = clock()
        await auth.forget_expired(now=now)
        challenge = secrets.token_bytes(32)
        expires = now + timedelta(seconds=config.challenge_seconds)
        await auth.save_challenge(challenge, purpose, expires_at=expires)
        return challenge

    async def confirm(credential: Mapping[str, Any], purpose: str) -> None:
        """A fresh passkey assertion for ``purpose``, with user verification (Face ID)."""
        challenge = _challenge_of(credential)
        if not await auth.take_challenge(challenge, purpose, now=clock()):
            raise HTTPException(400, "Bekräftelsen har gått ut eller gäller något annat.")
        known = {p.credential_id: p for p in await auth.passkeys()}
        passkey = known.get(_b64url(str(credential.get("rawId", ""))))
        if passkey is None:
            raise HTTPException(401, "Den här passkeyn känner jag inte igen.")
        try:
            verified = verify_authentication_response(
                credential=dict(credential),
                expected_challenge=challenge,
                expected_rp_id=config.rp_id,
                expected_origin=config.origin,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count,
                require_user_verification=True,
            )
        except InvalidAuthenticationResponse as error:
            raise HTTPException(401, "Passkeyn kunde inte bekräftas.") from error
        await auth.passkey_used(passkey.credential_id, verified.new_sign_count, at=clock())

    async def login(response: Response) -> None:
        token = secrets.token_urlsafe(32)
        now = clock()
        hours = timedelta(hours=config.session_hours)
        await auth.start_session(token, at=now, expires_at=now + hours)
        response.set_cookie(
            COOKIE,
            token,
            max_age=int(hours.total_seconds()),
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
        )

    async def assertion_options(purpose: str) -> JSONResponse:
        passkeys = await auth.passkeys()
        if not passkeys:
            raise HTTPException(409, "Det finns ingen passkey ännu.")
        options = generate_authentication_options(
            rp_id=config.rp_id,
            challenge=await new_challenge(purpose),
            allow_credentials=[PublicKeyCredentialDescriptor(id=p.credential_id) for p in passkeys],
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        return _options(options)

    @router.get("/auth/state")
    async def state(request: Request) -> dict[str, bool]:
        return {"registered": await auth.has_passkey(), "logged_in": await logged_in(request)}

    @router.post("/auth/register/options", dependencies=[Depends(guard)])
    async def register_options(body: SetupIn, request: Request) -> JSONResponse:
        if await auth.has_passkey():
            if not await logged_in(request):
                raise HTTPException(403, "Det finns redan en passkey. Logga in först.")
        elif config.setup_code is None or not hmac.compare_digest(
            body.setup_code.encode(), config.setup_code.encode()
        ):
            raise HTTPException(403, "Fel engångskod.")
        known = await auth.passkeys()
        options = generate_registration_options(
            rp_id=config.rp_id,
            rp_name="Jarvis",
            user_name="adam",
            user_id=b"adam",
            user_display_name="Adam",
            challenge=await new_challenge("register"),
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=[PublicKeyCredentialDescriptor(id=p.credential_id) for p in known],
        )
        return _options(options)

    @router.post("/auth/register/verify", dependencies=[Depends(guard)])
    async def register_verify(body: CredentialIn, response: Response) -> dict[str, bool]:
        challenge = _challenge_of(body.credential)
        if not await auth.take_challenge(challenge, "register", now=clock()):
            raise HTTPException(400, "Registreringen har gått ut. Börja om.")
        try:
            verified = verify_registration_response(
                credential=body.credential,
                expected_challenge=challenge,
                expected_rp_id=config.rp_id,
                expected_origin=config.origin,
                require_user_verification=True,
            )
        except InvalidRegistrationResponse as error:
            raise HTTPException(400, "Passkeyn kunde inte skapas.") from error
        await auth.add_passkey(
            verified.credential_id,
            verified.credential_public_key,
            verified.sign_count,
            at=clock(),
        )
        await login(response)
        return {"ok": True}

    @router.post("/auth/login/options", dependencies=[Depends(guard)])
    async def login_options() -> JSONResponse:
        return await assertion_options("login")

    @router.post("/auth/login/verify", dependencies=[Depends(guard)])
    async def login_verify(body: CredentialIn, response: Response) -> dict[str, bool]:
        await confirm(body.credential, "login")
        await login(response)
        return {"ok": True}

    @router.post("/auth/logout", dependencies=[Depends(guard)])
    async def logout(request: Request, response: Response) -> dict[str, bool]:
        token = request.cookies.get(COOKIE)
        if token is not None:
            await auth.end_session(token, at=clock())
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
        return {"ok": True}

    @router.post("/actions/options", dependencies=[Depends(guard), Depends(require_login)])
    async def action_options(body: ActionOptionsIn) -> JSONResponse:
        return await assertion_options(action_purpose(body.action, body.payload))

    @router.post("/actions/deposit", dependencies=[Depends(guard), Depends(require_login)])
    async def deposit(body: DepositIn) -> dict[str, str]:
        try:
            amount = Decimal(body.amount)
        except InvalidOperation as error:
            raise HTTPException(422, "Beloppet är inte ett tal.") from error
        if not amount.is_finite() or amount == 0 or abs(amount) > MAX_DEPOSIT:
            raise HTTPException(422, "Beloppet måste vara skilt från noll och rimligt stort.")
        if amount != amount.quantize(Decimal("0.01")):
            raise HTTPException(422, "Beloppet kan ha högst två decimaler.")
        note = body.note.strip()
        await confirm(
            body.credential, action_purpose("deposit", {"amount": body.amount, "note": body.note})
        )
        await store.record_cash_flow(
            amount, at=clock(), note=note or ("Insättning" if amount > 0 else "Uttag")
        )
        kind = "insättningen" if amount > 0 else "uttaget"
        return {
            "message_sv": f"Jag har registrerat {kind}. Den räknas inte som vinst eller förlust."
        }

    @router.post("/actions/risk-profile", dependencies=[Depends(guard), Depends(require_login)])
    async def risk_profile(body: RiskProfileIn) -> dict[str, str]:
        await confirm(
            body.credential, action_purpose("risk_profile", {"profile": body.profile.value})
        )
        now = clock()
        effective = await store.set_risk_profile(body.profile, actor="adam", at=now)
        name = NAMES_SV[body.profile]
        if effective <= now:
            return {"message_sv": f"Risknivån är nu {name}."}
        return {
            "message_sv": f"Risknivån blir {name} från i morgon. En höjning väntar alltid en dag."
        }

    @router.get("/controls")
    async def controls() -> dict[str, Any]:
        now = clock()
        state = await store.controls()
        pending = await store.pending_budget(now)
        return {
            "mode": state.trading_mode,
            "paused": state.paused,
            "kill_switch_engaged": state.kill_switch_engaged,
            "budget_pct": _plain(await store.budget_pct(now)),
            "pending_budget_pct": None if pending is None else _plain(pending[0]),
            "pending_budget_from": None if pending is None else pending[1].isoformat(),
        }

    @router.post("/actions/control", dependencies=[Depends(guard), Depends(require_login)])
    async def control(body: ControlIn) -> dict[str, str]:
        await confirm(body.credential, action_purpose("control", {"command": body.command}))
        now = clock()
        if body.command in ("pause", "resume"):
            await store.set_paused(body.command == "pause", actor="adam", at=now)
        elif body.command == "kill_switch":
            await store.engage_kill_switch("adam", actor="adam", at=now)
        else:
            await store.reset_kill_switch(actor="adam", at=now)
        return {"message_sv": CONTROL_SV[body.command]}

    @router.post("/actions/budget", dependencies=[Depends(guard), Depends(require_login)])
    async def budget(body: BudgetIn) -> dict[str, str]:
        pct = parse_budget(body.pct)
        await confirm(body.credential, action_purpose("budget", {"pct": body.pct}))
        now = clock()
        effective = await store.set_budget(pct, actor="adam", at=now)
        if effective <= now:
            return {"message_sv": f"Jarvis budget är nu {pct} % av kontot."}
        when = "om 24 timmar" if effective - now >= timedelta(hours=24) else "från i morgon"
        return {"message_sv": f"Jarvis budget blir {pct} % av kontot {when}."}

    @router.post("/actions/trading-mode", dependencies=[Depends(guard), Depends(require_login)])
    async def trading_mode(body: TradingModeIn) -> dict[str, str]:
        payload = {"mode": body.mode, "phrase": body.phrase, "budget_pct": body.budget_pct}
        if body.mode == "paper":
            await confirm(body.credential, action_purpose("trading_mode", payload))
            await store.set_trading_mode("paper", actor="adam", at=clock())
            return {"message_sv": "Jarvis är tillbaka i pappershandel."}
        if body.phrase != LIVE_PHRASE:
            raise HTTPException(422, f"Skriv exakt {LIVE_PHRASE} för att slå på riktig handel.")
        pct = parse_budget(body.budget_pct)
        await confirm(body.credential, action_purpose("trading_mode", payload))
        now = clock()
        if pct < await store.budget_pct(now):
            await store.set_budget(pct, actor="adam", at=now)
        await store.set_trading_mode("live", actor="adam", at=now)
        return {
            "message_sv": (
                f"Riktig handel är vald med en budget på högst {pct} % av kontot. Jarvis handlar "
                "först när gatewayn är inloggad på ditt riktiga konto; tills dess står handeln "
                "still."
            )
        }

    return router
