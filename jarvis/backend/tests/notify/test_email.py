from __future__ import annotations

from email.message import EmailMessage
from typing import Any

import pytest

from jarvis.config import ConfigError
from jarvis.execution.alerts import AlertLevel
from jarvis.notify import email as email_module
from jarvis.notify.email import EmailAlerts, FanOut, SmtpSettings, smtp_settings_from_env

FULL = {
    "JARVIS_SMTP_HOST": "smtp.gmail.com",
    "JARVIS_SMTP_USER": "jarvis.bot@example.com",
    "JARVIS_SMTP_PASSWORD": "app-password",
    "JARVIS_ALERT_EMAIL": "adam@example.com",
}


def test_not_configured_means_log_only() -> None:
    assert smtp_settings_from_env({}) is None


def test_full_configuration() -> None:
    settings = smtp_settings_from_env(FULL)
    assert settings is not None
    assert (settings.host, settings.port, settings.sender) == (
        "smtp.gmail.com",
        465,
        "jarvis.bot@example.com",
    )
    custom = smtp_settings_from_env(FULL | {"JARVIS_SMTP_PORT": "587", "JARVIS_SMTP_FROM": "a@b"})
    assert custom is not None
    assert (custom.port, custom.sender) == (587, "a@b")


def test_half_configuration_refuses_to_start() -> None:
    with pytest.raises(ConfigError, match="JARVIS_ALERT_EMAIL"):
        smtp_settings_from_env({k: v for k, v in FULL.items() if k != "JARVIS_ALERT_EMAIL"})
    with pytest.raises(ConfigError, match="number"):
        smtp_settings_from_env(FULL | {"JARVIS_SMTP_PORT": "x"})


class FakeSmtp:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[EmailMessage] = []
        self.logins: list[tuple[str, str]] = []

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def login(self, user: str, password: str) -> None:
        self.logins.append((user, password))

    def send_message(self, mail: EmailMessage) -> None:
        if self.fail:
            raise OSError("smtp down")
        self.sent.append(mail)


SETTINGS = SmtpSettings("smtp", 465, "u", "p", "jarvis@x", "adam@x")


async def test_sends_a_swedish_mail() -> None:
    smtp = FakeSmtp()
    alerts = EmailAlerts(SETTINGS, connect=lambda s: smtp)  # type: ignore[arg-type,return-value]
    await alerts.send(AlertLevel.CRITICAL, "Positionen i AAPL saknar fullt skydd.")
    (mail,) = smtp.sent
    assert mail["Subject"] == "Jarvis: kräver din uppmärksamhet"
    assert mail["To"] == "adam@x"
    assert "saknar fullt skydd" in mail.get_content()
    assert smtp.logins == [("u", "p")]


async def test_failed_delivery_raises_so_it_is_retried() -> None:
    alerts = EmailAlerts(SETTINGS, connect=lambda s: FakeSmtp(fail=True))  # type: ignore[arg-type,return-value]
    with pytest.raises(OSError, match="smtp down"):
        await alerts.send(AlertLevel.WARNING, "x")


def test_default_connection_uses_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    made: dict[str, Any] = {}

    def fake_ssl(host: str, port: int, **kwargs: Any) -> str:
        made.update(host=host, port=port, **kwargs)
        return "connection"

    monkeypatch.setattr("smtplib.SMTP_SSL", fake_ssl)
    connection: object = email_module._connect_tls(SETTINGS)
    assert connection == "connection"
    assert (made["host"], made["port"], made["timeout"]) == ("smtp", 465, 20.0)
    assert made["context"] is not None


class Channel:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.got: list[str] = []

    async def send(self, level: AlertLevel, message_sv: str) -> None:
        if self.fail:
            raise RuntimeError("down")
        self.got.append(message_sv)


async def test_fan_out_reaches_every_channel_even_when_one_fails() -> None:
    ok, broken = Channel(), Channel(fail=True)
    with pytest.raises(RuntimeError, match="down"):
        await FanOut(broken, ok).send(AlertLevel.INFO, "hej")
    assert ok.got == ["hej"]
    both = Channel(), Channel()
    await FanOut(*both).send(AlertLevel.INFO, "allt väl")
    assert [c.got for c in both] == [["allt väl"], ["allt väl"]]
