"""Storage for passkey login (§10): credentials, one-time challenges and sessions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from jarvis.store.db import session_factory
from jarvis.store.tables import AuditEntry, AuthChallenge, AuthSession, Passkey


@dataclass(frozen=True, slots=True)
class StoredPasskey:
    credential_id: bytes
    public_key: bytes
    sign_count: int


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


class AuthStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = session_factory(engine)

    async def has_passkey(self) -> bool:
        async with self._sessions() as session:
            return bool(await session.scalar(select(func.count()).select_from(Passkey)))

    async def passkeys(self) -> list[StoredPasskey]:
        async with self._sessions() as session:
            rows = await session.scalars(select(Passkey).order_by(Passkey.created_at))
            return [StoredPasskey(r.credential_id, r.public_key, r.sign_count) for r in rows]

    async def add_passkey(
        self, credential_id: bytes, public_key: bytes, sign_count: int, *, at: datetime
    ) -> None:
        async with self._sessions.begin() as session:
            session.add(
                Passkey(
                    credential_id=credential_id,
                    public_key=public_key,
                    sign_count=sign_count,
                    created_at=at,
                )
            )
            session.add(AuditEntry(at=at, actor="adam", action="passkey_added", details={}))

    async def passkey_used(self, credential_id: bytes, sign_count: int, *, at: datetime) -> None:
        async with self._sessions.begin() as session:
            row = await session.get_one(Passkey, credential_id)
            row.sign_count, row.last_used_at = sign_count, at

    async def save_challenge(self, challenge: bytes, purpose: str, *, expires_at: datetime) -> None:
        async with self._sessions.begin() as session:
            session.add(AuthChallenge(challenge=challenge, purpose=purpose, expires_at=expires_at))

    async def take_challenge(self, challenge: bytes, purpose: str, *, now: datetime) -> bool:
        """Consumes the challenge. True only if it existed for this purpose and had not
        expired; a challenge can never be used twice."""
        async with self._sessions.begin() as session:
            row = await session.get(AuthChallenge, challenge)
            if row is None:
                return False
            await session.delete(row)
            return row.purpose == purpose and now < row.expires_at

    async def start_session(self, token: str, *, at: datetime, expires_at: datetime) -> None:
        async with self._sessions.begin() as session:
            session.add(
                AuthSession(token_hash=token_hash(token), created_at=at, expires_at=expires_at)
            )
            session.add(AuditEntry(at=at, actor="adam", action="login", details={}))

    async def session_valid(self, token: str, *, now: datetime) -> bool:
        async with self._sessions() as session:
            row = await session.get(AuthSession, token_hash(token))
            return row is not None and now < row.expires_at

    async def end_session(self, token: str, *, at: datetime) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                delete(AuthSession).where(AuthSession.token_hash == token_hash(token))
            )
            session.add(AuditEntry(at=at, actor="adam", action="logout", details={}))

    async def forget_expired(self, *, now: datetime) -> None:
        async with self._sessions.begin() as session:
            await session.execute(delete(AuthChallenge).where(AuthChallenge.expires_at <= now))
            await session.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
