"""Alerts by e-mail over SMTP with TLS (free with Adam's own mail account, decision D9).

Credentials come only from the environment. A failed delivery raises, so the execution
engine keeps the alert and retries it at the next reconciliation.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import EmailMessage

from jarvis.config import ConfigError
from jarvis.execution.alerts import AlertLevel, Alerts

SUBJECTS_SV = {
    AlertLevel.CRITICAL: "Jarvis: kräver din uppmärksamhet",
    AlertLevel.WARNING: "Jarvis: varning",
    AlertLevel.INFO: "Jarvis: information",
}


@dataclass(frozen=True, slots=True)
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipient: str
    timeout_seconds: float = 20.0


def smtp_settings_from_env(env: Mapping[str, str]) -> SmtpSettings | None:
    """None when e-mail is not configured (alerts then only reach the log)."""
    names = ("JARVIS_SMTP_HOST", "JARVIS_SMTP_USER", "JARVIS_SMTP_PASSWORD", "JARVIS_ALERT_EMAIL")
    present = [bool(env.get(n)) for n in names]
    if not any(present):
        return None
    if not all(present):
        missing = [n for n, ok in zip(names, present, strict=True) if not ok]
        raise ConfigError(f"e-mail alerts are half configured; missing {', '.join(missing)}")
    try:
        port = int(env.get("JARVIS_SMTP_PORT", "465"))
    except ValueError as exc:
        raise ConfigError("JARVIS_SMTP_PORT must be a number") from exc
    return SmtpSettings(
        host=env["JARVIS_SMTP_HOST"],
        port=port,
        username=env["JARVIS_SMTP_USER"],
        password=env["JARVIS_SMTP_PASSWORD"],
        sender=env.get("JARVIS_SMTP_FROM") or env["JARVIS_SMTP_USER"],
        recipient=env["JARVIS_ALERT_EMAIL"],
    )


class EmailAlerts:
    def __init__(
        self,
        settings: SmtpSettings,
        connect: Callable[[SmtpSettings], smtplib.SMTP] | None = None,
    ) -> None:
        self._s = settings
        self._connect = connect or _connect_tls

    def _send(self, level: AlertLevel, message_sv: str) -> None:
        mail = EmailMessage()
        mail["Subject"] = SUBJECTS_SV[level]
        mail["From"] = self._s.sender
        mail["To"] = self._s.recipient
        mail.set_content(
            f"{message_sv}\n\nDetta är ett automatiskt meddelande från Jarvis. "
            "Öppna appen för detaljer."
        )
        with self._connect(self._s) as smtp:
            smtp.login(self._s.username, self._s.password)
            smtp.send_message(mail)

    async def send(self, level: AlertLevel, message_sv: str) -> None:
        await asyncio.to_thread(self._send, level, message_sv)


def _connect_tls(settings: SmtpSettings) -> smtplib.SMTP:
    return smtplib.SMTP_SSL(
        settings.host,
        settings.port,
        timeout=settings.timeout_seconds,
        context=ssl.create_default_context(),
    )


class FanOut:
    """Send every alert to several channels; it counts as delivered only if all succeed
    (a failed one is retried later, so the log may then show the alert twice)."""

    def __init__(self, *channels: Alerts) -> None:
        self._channels = channels

    async def send(self, level: AlertLevel, message_sv: str) -> None:
        errors = []
        for channel in self._channels:
            try:
                await channel.send(level, message_sv)
            except Exception as exc:  # one broken channel must not silence the others
                errors.append(exc)
        if errors:
            raise errors[0]
