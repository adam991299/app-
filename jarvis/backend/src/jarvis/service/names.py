"""The backend services in the architecture (spec §2)."""

from enum import StrEnum


class ServiceName(StrEnum):
    API = "api"
    BROKER = "broker-service"
    EXECUTION = "execution-engine"
    RISK = "risk-engine"
    MARKET_DATA = "market-data-service"
    STRATEGY = "strategy-engine"
    RESEARCH = "research-lab"
    NEWS = "news-service"
    LEARNING = "learning-service"
    SCHEDULER = "scheduler"
    WATCHDOG = "watchdog"
    NOTIFIER = "notifier"
    BACKUP = "backup"
