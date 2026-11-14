"""Validated configuration for Jarvis.

Every default below comes from JARVIS_SPEC.md (section noted per group). Values the
spec does not fix are deliberately absent until the module that needs them is built.
All percentages are expressed in percent units (0.75 means 0.75 %).

Trading mode (paper/live) is intentionally NOT part of this file: live trading can
only be enabled by Adam in the app (spec §0 rule 3, §9.4), never by editing config.
"""

from __future__ import annotations

from datetime import time
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AppSettings(_Section):
    """Presentation settings (§0, §1.7). Exchange hours never depend on these."""

    locale: Literal["sv-SE"] = "sv-SE"
    display_timezone: str = "Europe/Stockholm"

    @field_validator("display_timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone: {value!r}") from exc
        return value


class NightMode(_Section):
    """Stricter limits at night in Adam's display timezone (§1.6)."""

    enabled: bool = True
    start: time = time(23, 0)
    end: time = time(7, 0)

    @model_validator(mode="after")
    def _non_empty_window(self) -> Self:
        if self.start == self.end:
            raise ValueError("night mode start and end must differ")
        return self


class Markets(_Section):
    """Which markets Jarvis may trade (§3, §9.2). A market is switched on only once
    its build phase has passed; futures and extended hours stay off unless Adam
    enables them."""

    us_equities: bool = True
    nordic_equities: bool = False
    etfs: bool = False
    commodities: bool = False
    crypto: bool = False
    futures: bool = False
    us_extended_hours: bool = False

    @model_validator(mode="after")
    def _dependent_switches(self) -> Self:
        if self.futures and not self.commodities:
            raise ValueError("futures require the commodities market to be enabled")
        if self.us_extended_hours and not self.us_equities:
            raise ValueError("US extended hours require US equities to be enabled")
        return self


class Universe(_Section):
    """Nightly universe filter thresholds (§3)."""

    min_adv_nordics_msek: float = Field(default=5.0, gt=0)
    min_adv_us_musd: float = Field(default=20.0, gt=0)


class PerTradeRisk(_Section):
    """Per-trade limits (§7)."""

    max_risk_pct: float = Field(default=0.75, gt=0, le=2.0)
    max_kelly_fraction: float = Field(default=0.25, gt=0, le=0.25)


class PortfolioRisk(_Section):
    """Per-portfolio limits (§7)."""

    max_position_pct: float = Field(default=10.0, gt=0, le=100)
    max_position_crypto_pct: float = Field(default=5.0, gt=0, le=100)
    max_position_small_cap_pct: float = Field(default=5.0, gt=0, le=100)
    max_sector_pct: float = Field(default=25.0, gt=0, le=100)
    max_crypto_total_pct: float = Field(default=15.0, gt=0, le=100)
    max_commodities_total_pct: float = Field(default=20.0, gt=0, le=100)
    max_gross_exposure_pct: float = Field(default=100.0, gt=0, le=200)
    min_cash_reserve_pct: float = Field(default=5.0, ge=0, lt=100)
    long_only: bool = True


class CircuitBreakers(_Section):
    """Stop rules (§7). They cannot be disabled; levels may move within the bounds."""

    daily_loss_pct: float = Field(default=2.0, ge=0.5, le=5.0)
    weekly_loss_pct: float = Field(default=4.0, ge=1.0, le=10.0)
    kill_switch_drawdown_pct: float = Field(default=10.0, ge=2.0, le=20.0)
    max_clock_drift_seconds: float = Field(default=1.0, gt=0, le=1.0)

    @model_validator(mode="after")
    def _escalating(self) -> Self:
        if not self.daily_loss_pct < self.weekly_loss_pct < self.kill_switch_drawdown_pct:
            raise ValueError(
                "circuit breakers must escalate: daily < weekly < kill switch drawdown"
            )
        return self


class Turnover(_Section):
    """Over-trading guard (§7)."""

    max_annual_turnover_multiple: float = Field(default=10.0, gt=0)
    min_edge_to_cost_ratio: float = Field(default=2.0, ge=1.0)


class GapRisk(_Section):
    """Gap scenario sizing (§7)."""

    single_stock_gap_pct: float = Field(default=25.0, gt=0, le=100)
    crypto_gap_pct: float = Field(default=40.0, gt=0, le=100)
    max_gap_loss_pct: float = Field(default=3.0, gt=0, le=10)


class TechnicalMax(_Section):
    """Hard caps protecting against bugs and mis-taps (§7.1)."""

    single_stock_pct_of_budget: float = Field(default=25.0, gt=0, le=25.0)
    crypto_total_pct: float = Field(default=40.0, gt=0, le=40.0)
    leverage_allowed: bool = False


class Concurrency(_Section):
    """Simultaneous-position limits (§6.4.1)."""

    max_open_positions: int = Field(default=25, ge=1)
    max_concurrent_daytrades: int = Field(default=5, ge=0)


class Daytrading(_Section):
    """Day-trading engine limits (§6.2.1)."""

    max_daily_loss_pct: float = Field(default=1.0, gt=0, le=2.0)
    pause_after_consecutive_losses: int = Field(default=3, ge=1)


class Risk(_Section):
    per_trade: PerTradeRisk = PerTradeRisk()
    portfolio: PortfolioRisk = PortfolioRisk()
    circuit_breakers: CircuitBreakers = CircuitBreakers()
    turnover: Turnover = Turnover()
    gap: GapRisk = GapRisk()
    technical_max: TechnicalMax = TechnicalMax()
    concurrency: Concurrency = Concurrency()
    daytrading: Daytrading = Daytrading()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        portfolio, tech = self.portfolio, self.technical_max
        problems: list[str] = []
        if portfolio.max_position_pct > tech.single_stock_pct_of_budget:
            problems.append("max_position_pct exceeds the technical single-stock cap")
        if portfolio.max_position_crypto_pct > portfolio.max_crypto_total_pct:
            problems.append("max_position_crypto_pct exceeds max_crypto_total_pct")
        if portfolio.max_crypto_total_pct > tech.crypto_total_pct:
            problems.append("max_crypto_total_pct exceeds the technical crypto cap")
        if portfolio.max_gross_exposure_pct > 100 and not tech.leverage_allowed:
            problems.append("gross exposure above 100 % requires leverage_allowed")
        if not portfolio.long_only and not tech.leverage_allowed:
            problems.append("short selling requires leverage_allowed (margin account)")
        if self.per_trade.max_risk_pct > self.gap.max_gap_loss_pct:
            problems.append("per-trade risk exceeds the allowed gap-scenario loss")
        if self.concurrency.max_concurrent_daytrades > self.concurrency.max_open_positions:
            problems.append("max_concurrent_daytrades exceeds max_open_positions")
        if self.daytrading.max_daily_loss_pct > self.circuit_breakers.daily_loss_pct:
            problems.append("day-trading daily loss limit exceeds the overall daily limit")
        if problems:
            raise ValueError("; ".join(problems))
        return self


class Validation(_Section):
    """Strategy validation thresholds (§6.3)."""

    min_oos_trades: int = Field(default=100, ge=1)
    min_deflated_sharpe_probability: float = Field(default=0.95, gt=0.5, lt=1)
    max_drawdown_pct: float = Field(default=20.0, gt=0, le=100)
    min_profit_factor: float = Field(default=1.3, gt=1.0)
    min_positive_walk_forward_windows_pct: float = Field(default=60.0, gt=50, le=100)
    holdout_pct: float = Field(default=20.0, gt=0, lt=50)
    max_free_parameters: int = Field(default=5, ge=1, le=5)


class Lifecycle(_Section):
    """Promotion requirements (§6.4) and paper-result haircut (§11.3)."""

    paper_min_trading_days: int = Field(default=60, ge=1)
    paper_min_trades: int = Field(default=50, ge=1)
    slow_strategy_paper_min_months: int = Field(default=3, ge=1)
    paper_slippage_multiplier: float = Field(default=2.0, ge=1.0)


class Opportunities(_Section):
    """Opportunity notifications (§9.2.2)."""

    max_per_day: int = Field(default=5, ge=0)
    reprice_daytrade_pct: float = Field(default=0.5, gt=0)
    reprice_swing_pct: float = Field(default=1.5, gt=0)


class Tax(_Section):
    """Tax model (§1.5, §1.7, §12). The ISK figures change yearly and must be entered
    from Skatteverket; they are never hard-coded, so they start unset."""

    model: Literal["isk", "capital_gains"] = "isk"
    tax_year: int | None = Field(default=None, ge=2024)
    isk_tax_free_level_sek: float | None = Field(default=None, ge=0)
    isk_schablon_tax_pct: float | None = Field(default=None, ge=0, le=10)

    @model_validator(mode="after")
    def _isk_figures_come_together(self) -> Self:
        figures = (self.tax_year, self.isk_tax_free_level_sek, self.isk_schablon_tax_pct)
        if any(f is not None for f in figures) and any(f is None for f in figures):
            raise ValueError(
                "tax_year, isk_tax_free_level_sek and isk_schablon_tax_pct must be set together"
            )
        return self


class Economics(_Section):
    """Cost honesty thresholds (§1.5)."""

    break_even_warning_pct: float = Field(default=3.0, gt=0)
    min_living_buffer_months: int = Field(default=12, ge=12)


class CheckIn(_Section):
    """Adam's own dead-man's switch (§11.2)."""

    interval_days: int = Field(default=7, ge=1)
    halve_risk_after_days: int = Field(default=3, ge=1)
    wind_down_after_days: int = Field(default=7, ge=1)


class ProjectStopRules(_Section):
    """Pre-committed stop rules for the whole project (§16)."""

    evaluation_months: int = Field(default=12, ge=1)
    max_total_live_drawdown_pct: float = Field(default=20.0, gt=0, le=20.0)
    min_months_per_capital_step: int = Field(default=3, ge=1)


class Settings(_Section):
    app: AppSettings = AppSettings()
    night_mode: NightMode = NightMode()
    markets: Markets = Markets()
    universe: Universe = Universe()
    risk: Risk = Risk()
    validation: Validation = Validation()
    lifecycle: Lifecycle = Lifecycle()
    opportunities: Opportunities = Opportunities()
    tax: Tax = Tax()
    economics: Economics = Economics()
    check_in: CheckIn = CheckIn()
    project_stop_rules: ProjectStopRules = ProjectStopRules()

    @model_validator(mode="after")
    def _kill_switch_before_project_stop(self) -> Self:
        kill = self.risk.circuit_breakers.kill_switch_drawdown_pct
        if kill > self.project_stop_rules.max_total_live_drawdown_pct:
            raise ValueError("kill switch drawdown must not exceed the project stop drawdown")
        return self
