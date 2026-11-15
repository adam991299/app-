"""How execution tells Adam something needs attention (delivered by the notifier, §9.3)."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class AlertLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alerts(Protocol):
    async def send(self, level: AlertLevel, message_sv: str) -> None: ...
