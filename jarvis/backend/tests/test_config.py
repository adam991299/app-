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


def test_every_default_is_the_number_in_the_spec() -> None:
    """Written by hand from JARVIS_SPEC.md, independently of the model defaults."""
    spec = {
        "app": {"locale": "sv-SE", "display_timezone": "Europe/Stockholm"},  # §0
        "night_mode": {"enabled": True, "start": "23:00:00", "end": "07:00:00"},  # §1.6
        "markets": {  # §3, D5
            "us_equities": True,
            "nordic_equities": False,
            "etfs": False,
            "commodities": False,
            "crypto": False,
            "futures": False,
            "us_extended_hours": False,
        },
        "universe": {"min_adv_nordics_msek": 5.0, "min_adv_us_musd": 20.0},  # §3
        "risk": {
            "per_trade": {"max_risk_pct": 0.75, "max_kelly_fraction": 0.25},  # §7
            "portfolio": {  # §7
                "max_position_pct": 10.0,
                "max_position_crypto_pct": 5.0,
                "max_position_small_cap_pct": 5.0,
                "max_sector_pct": 25.0,
                "max_crypto_total_pct": 15.0,
                "max_commodities_total_pct": 20.0,
                "max_gross_exposure_pct": 100.0,
                "min_cash_reserve_pct": 5.0,
            },
            "circuit_breakers": {  # §7, §11
                "daily_loss_pct": 2.0,
                "weekly_loss_pct": 4.0,
                "kill_switch_drawdown_pct": 10.0,
                "max_clock_drift_seconds": 1.0,
            },
            "turnover": {"max_annual_turnover_multiple": 10.0, "min_edge_to_cost_ratio": 2.0},
            "gap": {"single_stock_gap_pct": 25.0, "crypto_gap_pct": 40.0, "max_gap_loss_pct": 3.0},
            "technical_max": {"single_stock_pct_of_budget": 25.0, "crypto_total_pct": 40.0},  # §7.1
            "concurrency": {"max_open_positions": 25, "max_concurrent_daytrades": 5},  # §6.4.1
            "daytrading": {"max_daily_loss_pct": 1.0, "pause_after_consecutive_losses": 3},
        },
        "validation": {  # §6.3
            "min_oos_trades": 100,
            "min_deflated_sharpe_probability": 0.95,
            "max_drawdown_pct": 20.0,
            "min_profit_factor": 1.3,
            "min_positive_walk_forward_windows_pct": 60.0,
            "holdout_pct": 20.0,
            "max_free_parameters": 5,
        },
        "lifecycle": {  # §6.4, §11.3
            "paper_min_trading_days": 60,
            "paper_min_trades": 50,
            "slow_strategy_paper_min_months": 3,
            "paper_slippage_multiplier": 2.0,
        },
        "opportunities": {"max_per_day": 5, "reprice_daytrade_pct": 0.5, "reprice_swing_pct": 1.5},
        "tax": {  # §1.5: never hard-coded
            "model": "isk",
            "tax_year": None,
            "isk_tax_free_level_sek": None,
            "isk_schablon_tax_pct": None,
        },
        "economics": {"break_even_warning_pct": 3.0, "min_living_buffer_months": 12},  # §1.5
        "check_in": {"interval_days": 7, "halve_risk_after_days": 3, "wind_down_after_days": 7},
        "project_stop_rules": {  # §16
            "evaluation_months": 12,
            "max_total_live_drawdown_pct": 20.0,
            "min_months_per_capital_step": 3,
        },
    }
    assert Settings().model_dump(mode="json") == spec


@pytest.mark.parametrize(
    "content",
    [
        "risk:\n  technical_max:\n    leverage_allowed: true\n",
        "risk:\n  portfolio:\n    long_only: false\n",
        "risk:\n  portfolio:\n    max_gross_exposure_pct: 150\n",
        "trading:\n  mode: live\n",
        "mode: live\n",
    ],
)
def test_a_file_can_never_enable_leverage_shorting_or_live(tmp_path: Path, content: str) -> None:
    with pytest.raises(ConfigError):
        load_settings(write(tmp_path, "c.yaml", content))


@pytest.mark.parametrize(
    "content",
    [
        "risk:\n  circuit_breakers:\n    daily_loss_pct: true\n",
        "risk:\n  circuit_breakers:\n    daily_loss_pct: '3'\n",
        "risk:\n  turnover:\n    max_annual_turnover_multiple: .inf\n",
        "risk:\n  turnover:\n    max_annual_turnover_multiple: .nan\n",
        "risk:\n  gap:\n    single_stock_gap_pct: 0.0001\n",
        "risk:\n  gap:\n    crypto_gap_pct: 1\n",
        "risk:\n  portfolio:\n    min_cash_reserve_pct: 0\n",
        "risk:\n  concurrency:\n    max_open_positions: 100000\n",
        "risk:\n  daytrading:\n    pause_after_consecutive_losses: 1000\n",
        "check_in:\n  interval_days: 100000\n",
    ],
)
def test_limits_cannot_be_neutralised_with_extreme_values(tmp_path: Path, content: str) -> None:
    with pytest.raises(ConfigError):
        load_settings(write(tmp_path, "c.yaml", content))


def test_whole_numbers_are_accepted_for_percentages(tmp_path: Path) -> None:
    path = write(tmp_path, "c.yaml", "risk:\n  portfolio:\n    max_sector_pct: 20\n")
    assert load_settings(path).risk.portfolio.max_sector_pct == 20.0


def test_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    content = "check_in:\n  interval_days: 7\n  interval_days: 60\n"
    with pytest.raises(ConfigError, match="duplicate key 'interval_days'"):
        load_settings(write(tmp_path, "c.yaml", content))


def test_non_utf8_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(ConfigError, match="cannot read config file"):
        load_settings(path)


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
        ({"technical_max": {"single_stock_pct_of_budget": 8}}, "max_position_pct exceeds"),
        (
            {
                "portfolio": {"max_position_crypto_pct": 12},
                "technical_max": {"single_stock_pct_of_budget": 11},
            },
            "max_position_crypto_pct exceeds the technical",
        ),
        (
            {"portfolio": {"max_position_small_cap_pct": 12}},
            "small_cap_pct exceeds max_position_pct",
        ),
        (
            {"per_trade": {"max_risk_pct": 2}, "circuit_breakers": {"daily_loss_pct": 1.5}},
            "daily loss circuit",
        ),
        ({"portfolio": {"max_position_crypto_pct": 20}}, "exceeds max_crypto_total_pct"),
        ({"technical_max": {"crypto_total_pct": 10}}, "technical crypto cap"),
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
