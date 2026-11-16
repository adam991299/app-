"""Passkey login and protected actions, with a software authenticator that signs for real."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import cbor2
import httpx2 as httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.ext.asyncio import AsyncEngine

from jarvis.api.app import create_api_app
from jarvis.api.auth import AuthConfig, RateLimiter, action_purpose, auth_config_from_env
from jarvis.config.settings import Settings
from jarvis.risk.profiles import RiskProfile
from jarvis.store.auth import AuthStore
from jarvis.store.repo import Store

NOW = datetime(2026, 11, 16, 18, tzinfo=UTC)
ORIGIN = "https://localhost"
CONFIG = AuthConfig(rp_id="localhost", origin=ORIGIN, setup_code="hemlig-kod-123")
HEADERS = {"x-jarvis": "1", "origin": ORIGIN}


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Authenticator:
    """A platform passkey: P-256 key, user presence and verification always given."""

    def __init__(self, rp_id: str = "localhost") -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(16)
        self.rp_hash = hashlib.sha256(rp_id.encode()).digest()
        self.count = 0

    def _client_data(self, kind: str, challenge: str, origin: str) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": challenge, "origin": origin, "crossOrigin": False}
        ).encode()

    def create(self, options: dict[str, Any], origin: str = ORIGIN) -> dict[str, Any]:
        numbers = self.key.public_key().public_numbers()
        cose = {
            1: 2,
            3: -7,
            -1: 1,
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        }
        auth_data = (
            self.rp_hash
            + bytes([0x45])  # user present, user verified, attested credential data
            + struct.pack(">I", self.count)
            + bytes(16)
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + cbor2.dumps(cose)
        )
        client = self._client_data("webauthn.create", options["challenge"], origin)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {"clientDataJSON": b64(client), "attestationObject": b64(attestation)},
            "clientExtensionResults": {},
        }

    def get(
        self, options: dict[str, Any], origin: str = ORIGIN, flags: int = 0x05
    ) -> dict[str, Any]:
        self.count += 1
        auth_data = self.rp_hash + bytes([flags]) + struct.pack(">I", self.count)
        client = self._client_data("webauthn.get", options["challenge"], origin)
        signature = self.key.sign(
            auth_data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client),
                "authenticatorData": b64(auth_data),
                "signature": b64(signature),
                "userHandle": b64(b"adam"),
            },
            "clientExtensionResults": {},
        }


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def auth_store(engine: AsyncEngine) -> AuthStore:
    return AuthStore(engine)


def client_for(store: Store, auth_store: AuthStore, clock: Clock) -> httpx.AsyncClient:
    app = create_api_app(store, Settings(), clock, (auth_store, CONFIG))
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=ORIGIN, headers=HEADERS
    )


@pytest.fixture
async def client(
    store: Store, auth_store: AuthStore, clock: Clock
) -> AsyncIterator[httpx.AsyncClient]:
    async with client_for(store, auth_store, clock) as c:
        yield c


async def register(client: httpx.AsyncClient, key: Authenticator) -> None:
    options = await client.post("/auth/register/options", json={"setup_code": CONFIG.setup_code})
    assert options.status_code == 200, options.text
    done = await client.post(
        "/auth/register/verify", json={"credential": key.create(options.json())}
    )
    assert done.status_code == 200, done.text


async def confirm(
    client: httpx.AsyncClient, key: Authenticator, action: str, payload: dict[str, str]
) -> dict[str, Any]:
    options = await client.post("/actions/options", json={"action": action, "payload": payload})
    assert options.status_code == 200, options.text
    return key.get(options.json())


async def test_first_passkey_needs_the_setup_code(client: httpx.AsyncClient) -> None:
    assert (await client.get("/auth/state")).json() == {"registered": False, "logged_in": False}
    for code in ("", "fel"):
        refused = await client.post("/auth/register/options", json={"setup_code": code})
        assert refused.status_code == 403
        assert refused.json()["detail"] == "Fel engångskod."
    await register(client, Authenticator())
    assert (await client.get("/auth/state")).json() == {"registered": True, "logged_in": True}
    cookie = client.cookies.jar
    assert any(c.name == "jarvis_session" and c.secure for c in cookie)


async def test_without_a_setup_code_no_passkey_can_be_created(
    store: Store, auth_store: AuthStore, clock: Clock
) -> None:
    app = create_api_app(
        store, Settings(), clock, (auth_store, AuthConfig("localhost", ORIGIN, None))
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=ORIGIN, headers=HEADERS
    ) as c:
        assert (await c.post("/auth/register/options", json={"setup_code": ""})).status_code == 403


async def test_a_second_passkey_needs_a_login(
    client: httpx.AsyncClient, store: Store, auth_store: AuthStore, clock: Clock
) -> None:
    await register(client, Authenticator())
    async with client_for(store, auth_store, clock) as stranger:
        refused = await stranger.post(
            "/auth/register/options", json={"setup_code": CONFIG.setup_code}
        )
        assert refused.status_code == 403
        assert "Logga in först" in refused.json()["detail"]
    await register(client, Authenticator())  # logged in: a backup passkey is fine
    assert len(await auth_store.passkeys()) == 2


async def test_login_logout_and_sign_counter(
    client: httpx.AsyncClient, store: Store, auth_store: AuthStore, clock: Clock
) -> None:
    key = Authenticator()
    await register(client, key)
    async with client_for(store, auth_store, clock) as phone:
        options = (await phone.post("/auth/login/options")).json()
        assert options["userVerification"] == "required"
        assert (
            await phone.post("/auth/login/verify", json={"credential": key.get(options)})
        ).status_code == 200
        assert (await phone.get("/auth/state")).json()["logged_in"] is True
        assert (await auth_store.passkeys())[0].sign_count == 1
        assert (await phone.post("/auth/logout")).status_code == 200
        assert (await phone.get("/auth/state")).json()["logged_in"] is False
        assert (await phone.post("/auth/logout")).status_code == 200  # no cookie: still fine


async def test_sessions_expire(client: httpx.AsyncClient, clock: Clock) -> None:
    await register(client, Authenticator())
    clock.now += timedelta(hours=13)
    assert (await client.get("/auth/state")).json()["logged_in"] is False


async def test_login_without_any_passkey(client: httpx.AsyncClient) -> None:
    assert (await client.post("/auth/login/options")).status_code == 409


async def test_requests_from_elsewhere_are_refused(client: httpx.AsyncClient) -> None:
    no_header = await client.post("/auth/login/options", headers={"x-jarvis": ""})
    other_site = await client.post(
        "/auth/login/options", headers={"origin": "https://evil.example"}
    )
    assert (no_header.status_code, other_site.status_code) == (403, 403)


async def test_unknown_or_forged_passkeys_are_refused(
    client: httpx.AsyncClient, store: Store, auth_store: AuthStore, clock: Clock
) -> None:
    key = Authenticator()
    await register(client, key)
    async with client_for(store, auth_store, clock) as other:
        stranger = Authenticator()
        options = (await other.post("/auth/login/options")).json()
        unknown = await other.post("/auth/login/verify", json={"credential": stranger.get(options)})
        assert unknown.status_code == 401
        options = (await other.post("/auth/login/options")).json()
        forged = key.get(options)
        forged["response"]["signature"] = stranger.get(options)["response"]["signature"]
        assert (
            await other.post("/auth/login/verify", json={"credential": forged})
        ).status_code == 401
        options = (await other.post("/auth/login/options")).json()
        no_face_id = key.get(options, flags=0x01)  # present but not verified
        assert (
            await other.post("/auth/login/verify", json={"credential": no_face_id})
        ).status_code == 401
        options = (await other.post("/auth/login/options")).json()
        wrong_site = key.get(options, origin="https://evil.example")
        assert (
            await other.post("/auth/login/verify", json={"credential": wrong_site})
        ).status_code == 401
        garbage = await other.post("/auth/login/verify", json={"credential": {"response": {}}})
        assert garbage.status_code == 400
        bad_id = key.get((await other.post("/auth/login/options")).json())
        bad_id["rawId"] = "!!!"
        assert (
            await other.post("/auth/login/verify", json={"credential": bad_id})
        ).status_code == 401
        assert (await other.get("/auth/state")).json()["logged_in"] is False


async def test_a_challenge_works_once_and_not_after_it_expires(
    client: httpx.AsyncClient, clock: Clock
) -> None:
    key = Authenticator()
    await register(client, key)
    options = (await client.post("/auth/login/options")).json()
    answer = key.get(options)
    assert (await client.post("/auth/login/verify", json={"credential": answer})).status_code == 200
    again = await client.post("/auth/login/verify", json={"credential": key.get(options)})
    assert again.status_code == 400
    options = (await client.post("/auth/login/options")).json()
    clock.now += timedelta(minutes=3)
    late = await client.post("/auth/login/verify", json={"credential": key.get(options)})
    assert late.status_code == 400
    register_late = await client.post(
        "/auth/register/verify", json={"credential": key.create(options)}
    )
    assert register_late.status_code == 400


async def test_a_broken_registration_is_refused(client: httpx.AsyncClient) -> None:
    key = Authenticator()
    options = (
        await client.post("/auth/register/options", json={"setup_code": CONFIG.setup_code})
    ).json()
    broken = key.create(options, origin="https://evil.example")
    assert (
        await client.post("/auth/register/verify", json={"credential": broken})
    ).status_code == 400


async def test_deposit_needs_login_and_a_matching_confirmation(
    client: httpx.AsyncClient, store: Store, auth_store: AuthStore, clock: Clock
) -> None:
    async with client_for(store, auth_store, clock) as stranger:
        assert (
            await stranger.post("/actions/deposit", json={"amount": "1", "credential": {}})
        ).status_code == 401
    key = Authenticator()
    await register(client, key)
    payload = {"amount": "5000", "note": "Lön"}
    credential = await confirm(client, key, "deposit", payload)
    tampered = await client.post(
        "/actions/deposit", json={"amount": "50000", "note": "Lön", "credential": credential}
    )
    assert tampered.status_code == 400  # the confirmation was for 5 000, and is now used up
    credential = await confirm(client, key, "deposit", payload)
    done = await client.post("/actions/deposit", json={**payload, "credential": credential})
    assert done.status_code == 200, done.text
    assert "insättningen" in done.json()["message_sv"]
    credential = await confirm(client, key, "deposit", {"amount": "-200.50", "note": ""})
    out = await client.post(
        "/actions/deposit", json={"amount": "-200.50", "note": "", "credential": credential}
    )
    assert "uttaget" in out.json()["message_sv"]


@pytest.mark.parametrize("amount", ["abc", "0", "NaN", "20000000", "1.234"])
async def test_unusable_amounts_are_refused(client: httpx.AsyncClient, amount: str) -> None:
    key = Authenticator()
    await register(client, key)
    response = await client.post("/actions/deposit", json={"amount": amount, "credential": {}})
    assert response.status_code == 422


async def test_risk_level_raises_wait_a_day_and_lowering_is_immediate(
    client: httpx.AsyncClient, store: Store
) -> None:
    key = Authenticator()
    await register(client, key)
    credential = await confirm(client, key, "risk_profile", {"profile": "offensive"})
    raised = await client.post(
        "/actions/risk-profile", json={"profile": "offensive", "credential": credential}
    )
    assert raised.json()["message_sv"].startswith("Risknivån blir Offensiv från i morgon.")
    credential = await confirm(client, key, "risk_profile", {"profile": "cautious"})
    lowered = await client.post(
        "/actions/risk-profile", json={"profile": "cautious", "credential": credential}
    )
    assert lowered.json()["message_sv"] == "Risknivån är nu Försiktig."
    assert await store.risk_profile(NOW) is RiskProfile.CAUTIOUS


async def test_unknown_actions_are_refused(client: httpx.AsyncClient) -> None:
    await register(client, Authenticator())
    response = await client.post("/actions/options", json={"action": "withdraw_all", "payload": {}})
    assert response.status_code == 422


def test_rate_limit() -> None:
    now = [0.0]
    limiter = RateLimiter(limit=2, window=60, now=lambda: now[0])
    limiter.check("a")
    limiter.check("a")
    with pytest.raises(Exception, match="429"):
        limiter.check("a")
    limiter.check("b")
    now[0] = 61
    limiter.check("a")


async def test_the_api_rate_limits_logins(client: httpx.AsyncClient) -> None:
    codes = [(await client.post("/auth/login/options")).status_code for _ in range(21)]
    assert codes[-1] == 429


def test_config_from_env_and_action_binding() -> None:
    assert auth_config_from_env({}) == AuthConfig("localhost", "https://localhost", None)
    config = auth_config_from_env(
        {"JARVIS_DOMAIN": "jarvis.tail.ts.net", "JARVIS_PASSKEY_SETUP_CODE": " x "}
    )
    assert (config.origin, config.setup_code) == ("https://jarvis.tail.ts.net", "x")
    assert action_purpose("deposit", {"amount": "1"}) != action_purpose("deposit", {"amount": "10"})
    assert unb64(b64(b"ok")) == b"ok"


async def run_action(
    client: httpx.AsyncClient, key: Authenticator, action: str, path: str, payload: dict[str, str]
) -> httpx.Response:
    credential = await confirm(client, key, action, payload)
    return await client.post(path, json={**payload, "credential": credential})


async def test_pause_resume_and_kill_switch_need_a_passkey(
    client: httpx.AsyncClient, store: Store
) -> None:
    key = Authenticator()
    await register(client, key)
    for command, check in (
        ("pause", lambda c: c.paused),
        ("resume", lambda c: not c.paused),
        ("kill_switch", lambda c: c.kill_switch_engaged),
        ("reset_kill_switch", lambda c: not c.kill_switch_engaged),
    ):
        done = await run_action(client, key, "control", "/actions/control", {"command": command})
        assert done.status_code == 200, done.text
        assert check(await store.controls())
    state = (await client.get("/controls")).json()
    assert state == {
        "mode": "paper",
        "paused": False,
        "kill_switch_engaged": False,
        "budget_pct": "100",
        "pending_budget_pct": None,
        "pending_budget_from": None,
    }


async def test_budget_changes_follow_the_rules(client: httpx.AsyncClient, clock: Clock) -> None:
    key = Authenticator()
    await register(client, key)
    lowered = await run_action(client, key, "budget", "/actions/budget", {"pct": "10"})
    assert lowered.json()["message_sv"] == "Jarvis budget är nu 10 % av kontot."
    raised = await run_action(client, key, "budget", "/actions/budget", {"pct": "20"})
    assert raised.json()["message_sv"].endswith("från i morgon.")
    tripled = await run_action(client, key, "budget", "/actions/budget", {"pct": "30"})
    assert tripled.json()["message_sv"].endswith("om 24 timmar.")
    state = (await client.get("/controls")).json()
    assert (state["budget_pct"], state["pending_budget_pct"]) == ("10", "30")
    for wrong in ("0", "101", "12.5", "x", "Infinity"):
        refused = await client.post("/actions/budget", json={"pct": wrong, "credential": {}})
        assert refused.status_code == 422, wrong


async def test_live_needs_the_phrase_and_a_passkey_and_paper_is_one_step_back(
    client: httpx.AsyncClient, store: Store
) -> None:
    key = Authenticator()
    await register(client, key)
    wrong = {"mode": "live", "phrase": "jag förstår risken", "budget_pct": "10"}
    refused = await client.post("/actions/trading-mode", json={**wrong, "credential": {}})
    assert refused.status_code == 422
    assert "JAG FÖRSTÅR RISKEN" in refused.json()["detail"]
    live = {"mode": "live", "phrase": "JAG FÖRSTÅR RISKEN", "budget_pct": "10"}
    done = await run_action(client, key, "trading_mode", "/actions/trading-mode", live)
    assert done.status_code == 200, done.text
    assert "högst 10 %" in done.json()["message_sv"]
    controls = await store.controls()
    assert controls.trading_mode == "live"
    assert await store.budget_pct(NOW) == 10
    again = {"mode": "live", "phrase": "JAG FÖRSTÅR RISKEN", "budget_pct": "25"}
    await run_action(client, key, "trading_mode", "/actions/trading-mode", again)
    assert await store.budget_pct(NOW) == 10  # going live never raises the budget
    back = {"mode": "paper", "phrase": "", "budget_pct": "10"}
    done = await run_action(client, key, "trading_mode", "/actions/trading-mode", back)
    assert done.json()["message_sv"] == "Jarvis är tillbaka i pappershandel."
    assert (await store.controls()).trading_mode == "paper"


async def test_actions_without_login_are_refused(client: httpx.AsyncClient) -> None:
    await register(client, Authenticator())
    client.cookies.clear()
    for path, body in (
        ("/actions/control", {"command": "pause"}),
        ("/actions/budget", {"pct": "10"}),
        ("/actions/trading-mode", {"mode": "paper"}),
    ):
        assert (await client.post(path, json={**body, "credential": {}})).status_code == 401
