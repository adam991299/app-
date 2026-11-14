from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from jarvis.config import ConfigError, Settings, load_settings, load_settings_from_env
from jarvis.config.settings import CircuitBreakers, Markets, NightMode, Risk, Tax

DEFAULT_CONFIG = Path(__file__).parents[2] / "config" / "default.yaml"


def write(tmp_path: Path, name: str, data: Any) -> Path:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else yaml.safe_dump(data), encoding="utf-8")
    return path


def test_shipped_default_file_matches_model_defaults() -> None:
    assert load_settings(DEFAULT_CONFIG) == Settings()


def test_defaults_follow_the_spec() -> None:
    settings = Settings()
    assert settings.risk.per_trade.max_risk_pct == 0.75
    assert settings.risk.portfolio.max_position_pct == 10
    assert settings.risk.circuit_breakers.daily_loss_pct == 2
    assert settings.risk.circuit_breakers.weekly_loss_pct == 4
    assert settings.risk.circuit_breakers.kill_switch_drawdown_pct == 10
    assert settings.risk.portfolio.long_only
    assert not settings.risk.technical_max.leverage_allowed
    assert not settings.markets.futures
    assert settings.tax.isk_schablon_tax_pct is None


def test_empty_file_gives_defaults(tmp_path: Path) -> None:
    assert load_settings(write(tmp_path, "c.yaml", "")) == Settings()


def test_override_is_deep_merged(tmp_path: Path) -> None:
    base = write(tmp_path, "base.yaml", {"risk": {"per_trade": {"max_risk_pct": 0.5}}})
    override = write(
        tmp_path,
        "override.yaml",
        {
            "risk": {"portfolio": {"max_sector_pct": 20}},
            "app": {"display_timezone": "Asia/Makassar"},
        },
    )
    settings = load_settings(base, override)
    assert settings.risk.per_trade.max_risk_pct == 0.5
    assert settings.risk.portfolio.max_sector_pct == 20
    assert settings.app.display_timezone == "Asia/Makassar"


def test_override_replaces_scalars(tmp_path: Path) -> None:
    base = write(tmp_path, "base.yaml", {"opportunities": {"max_per_day": 5}})
    override = write(tmp_path, "override.yaml", {"opportunities": {"max_per_day": 2}})
    assert load_settings(base, override).opportunities.max_per_day == 2


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("risk: [", "not valid YAML"),
        ("- a\n- b\n", "mapping at the top level"),
        ("unknown_section: 1\n", "unknown_section"),
        ("risk:\n  per_trade:\n    max_risk_pct: 50\n", "risk.per_trade.max_risk_pct"),
        ("app:\n  display_timezone: Mars/Olympus\n", "unknown IANA timezone"),
        ("app:\n  display_timezone: ''\n", "unknown IANA timezone"),
    ],
)
def test_invalid_files_are_rejected(tmp_path: Path, content: str, expected: str) -> None:
    with pytest.raises(ConfigError, match=expected):
        load_settings(write(tmp_path, "c.yaml", content))


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read config file"):
        load_settings(tmp_path / "missing.yaml")


def test_load_from_env(tmp_path: Path) -> None:
    base = write(tmp_path, "base.yaml", {})
    override = write(tmp_path, "o.yaml", {"check_in": {"interval_days": 14}})
    assert load_settings_from_env({"JARVIS_CONFIG": str(base)}) == Settings()
    env = {"JARVIS_CONFIG": str(base), "JARVIS_CONFIG_OVERRIDE": str(override)}
    assert load_settings_from_env(env).check_in.interval_days == 14


def test_load_from_env_requires_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_CONFIG", raising=False)
    with pytest.raises(ConfigError, match="JARVIS_CONFIG is not set"):
        load_settings_from_env()


def test_settings_are_immutable() -> None:
    with pytest.raises(ValidationError):
        Settings().risk.per_trade.max_risk_pct = 5


def test_night_mode_needs_a_window() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        NightMode.model_validate({"start": "23:00", "end": "23:00"})


@pytest.mark.parametrize(
    ("markets", "expected"),
    [
        ({"futures": True}, "futures require"),
        ({"us_equities": False, "us_extended_hours": True}, "extended hours require"),
    ],
)
def test_dependent_market_switches(markets: dict[str, bool], expected: str) -> None:
    with pytest.raises(ValidationError, match=expected):
        Markets.model_validate(markets)


def test_futures_allowed_with_commodities() -> None:
    assert Markets(commodities=True, futures=True).futures


@pytest.mark.parametrize(
    ("risk", "expected"),
    [
        ({"portfolio": {"max_position_pct": 30}}, "technical single-stock cap"),
        ({"portfolio": {"max_position_crypto_pct": 20}}, "exceeds max_crypto_total_pct"),
        ({"portfolio": {"max_crypto_total_pct": 45}}, "technical crypto cap"),
        ({"portfolio": {"max_gross_exposure_pct": 150}}, "requires leverage_allowed"),
        ({"portfolio": {"long_only": False}}, "short selling requires"),
        ({"gap": {"max_gap_loss_pct": 0.5}}, "gap-scenario loss"),
        ({"concurrency": {"max_open_positions": 3}}, "exceeds max_open_positions"),
        (
            {"daytrading": {"max_daily_loss_pct": 2}, "circuit_breakers": {"daily_loss_pct": 1}},
            "day-trading daily loss",
        ),
    ],
)
def test_inconsistent_risk_limits_are_rejected(risk: dict[str, Any], expected: str) -> None:
    with pytest.raises(ValidationError, match=expected):
        Risk.model_validate(risk)


def test_leverage_unlocks_gross_exposure_and_shorting() -> None:
    risk = Risk.model_validate(
        {
            "technical_max": {"leverage_allowed": True},
            "portfolio": {"max_gross_exposure_pct": 150, "long_only": False},
        }
    )
    assert risk.portfolio.max_gross_exposure_pct == 150


@pytest.mark.parametrize("level", [0, -1, 0.1, 6])
def test_circuit_breakers_cannot_be_disabled_or_loosened_freely(level: float) -> None:
    with pytest.raises(ValidationError):
        CircuitBreakers(daily_loss_pct=level)


def test_kill_switch_cannot_exceed_project_stop() -> None:
    with pytest.raises(ValidationError, match="project stop drawdown"):
        Settings.model_validate(
            {
                "risk": {"circuit_breakers": {"kill_switch_drawdown_pct": 20}},
                "project_stop_rules": {"max_total_live_drawdown_pct": 15},
            }
        )


def test_isk_figures_must_be_set_together() -> None:
    with pytest.raises(ValidationError, match="must be set together"):
        Tax(tax_year=2026)
    tax = Tax(tax_year=2026, isk_tax_free_level_sek=1.0, isk_schablon_tax_pct=1.0)
    assert tax.model == "isk"


@given(
    daily=st.floats(0.5, 5.0, allow_nan=False),
    weekly=st.floats(1.0, 10.0, allow_nan=False),
    kill=st.floats(2.0, 20.0, allow_nan=False),
)
def test_accepted_circuit_breakers_always_escalate(
    daily: float, weekly: float, kill: float
) -> None:
    try:
        breakers = CircuitBreakers(
            daily_loss_pct=daily, weekly_loss_pct=weekly, kill_switch_drawdown_pct=kill
        )
    except ValidationError:
        assert not daily < weekly < kill
    else:
        assert breakers.daily_loss_pct < breakers.weekly_loss_pct
        assert breakers.weekly_loss_pct < breakers.kill_switch_drawdown_pct
