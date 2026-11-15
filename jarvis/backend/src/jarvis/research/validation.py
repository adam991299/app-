"""Strategy validation (spec §6.3). A candidate must pass every check; anything that
cannot be checked counts as failed.

Procedure:
1. The last ``holdout_pct`` of history is locked away and touched exactly once, at the end.
2. Walk-forward on the rest: in each window the parameter set with the best in-sample
   Sharpe is chosen and judged only on the following out-of-sample period.
3. Every parameter set tried is a *trial*. All trials, also earlier ones from the registry,
   raise the bar through the Deflated Sharpe Ratio.
4. The out-of-sample result is compared with the chosen index fund over the same days.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from statistics import fmean

from jarvis.config.settings import Validation
from jarvis.research.costs import CostModel
from jarvis.research.event_backtest import Trade, run_event
from jarvis.research.metrics import (
    annualised_sharpe,
    deflated_sharpe,
    max_drawdown,
    profit_factor,
    returns,
    sharpe,
)
from jarvis.strategy.bars import Bar
from jarvis.strategy.trend import TrendParameters

FREE_PARAMETERS = 4  # entry and exit lookback, ATR period, ATR multiple


@dataclass(frozen=True, slots=True)
class Trial:
    params: TrendParameters
    window: int
    sample: str  # "in", "out" or "holdout"
    sharpe: float  # per day
    trades: int


@dataclass(frozen=True, slots=True)
class Check:
    key: str
    name_sv: str
    value: float | None
    required: str
    passed: bool


@dataclass(slots=True)
class Evaluation:
    daily: dict[date, float] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)

    @property
    def returns(self) -> list[float]:
        return [self.daily[d] for d in sorted(self.daily)]


@dataclass(slots=True)
class ValidationReport:
    passed: bool
    checks: list[Check]
    chosen: TrendParameters | None
    out_of_sample: Evaluation
    holdout: Evaluation
    trials: list[Trial]
    edge_r: float  # mean out-of-sample result per trade, in units of initial risk


def common_dates(series: Mapping[str, list[Bar]]) -> list[date]:
    sets = [{b.day for b in bars} for bars in series.values()]
    return sorted(set.intersection(*sets)) if sets else []


def evaluate(
    series: Mapping[str, list[Bar]],
    params: TrendParameters,
    start: date,
    end: date,
    costs: CostModel,
) -> Evaluation:
    """Equal-weight portfolio of one backtest per symbol, counting only days and entries in
    [start, end]. Earlier bars are used for warm-up only."""
    per_day: dict[date, list[float]] = {}
    trades: list[Trade] = []
    for bars in series.values():
        window = [b for b in bars if b.day <= end]
        first = next((i for i, b in enumerate(window) if b.day >= start), len(window))
        warm = window[max(0, first - params.bars_needed) :]
        offset = first - max(0, first - params.bars_needed)
        result = run_event(warm, params, costs=costs)
        daily = returns(result.equity)
        for i, value in enumerate(daily, start=1):
            if i >= offset:
                per_day.setdefault(warm[i].day, []).append(value)
        trades.extend(t for t in result.trades if t.entry_index >= offset)
    return Evaluation({d: fmean(v) for d, v in per_day.items()}, trades)


def _windows(days: list[date], train: int, test: int) -> list[tuple[date, date, date, date]]:
    out, start = [], 0
    while start + train + test <= len(days):
        out.append(
            (
                days[start],
                days[start + train - 1],
                days[start + train],
                days[start + train + test - 1],
            )
        )
        start += test
    return out


def validate(
    series: Mapping[str, list[Bar]],
    grid: Sequence[TrendParameters],
    rules: Validation,
    *,
    benchmark: list[Bar] | None,
    earlier_trial_sharpes: Sequence[float] = (),
    costs: CostModel | None = None,
    train_days: int = 504,
    test_days: int = 126,
) -> ValidationReport:
    model = costs or CostModel()
    days = common_dates(series)
    cut = int(len(days) * (1 - rules.holdout_pct / 100))
    research, holdout_days = days[:cut], days[cut:]
    trials: list[Trial] = []
    oos = Evaluation()
    positive_windows = 0
    windows = _windows(research, train_days, test_days)

    for number, (train_start, train_end, test_start, test_end) in enumerate(windows):
        scored = []
        for params in grid:
            inside = evaluate(series, params, train_start, train_end, model)
            score = sharpe(inside.returns)
            trials.append(Trial(params, number, "in", score, len(inside.trades)))
            scored.append((score, params))
        best = max(scored, key=lambda pair: pair[0])[1]
        outside = evaluate(series, best, test_start, test_end, model)
        trials.append(Trial(best, number, "out", sharpe(outside.returns), len(outside.trades)))
        oos.daily.update(outside.daily)
        oos.trades.extend(outside.trades)
        positive_windows += sum(outside.returns) > 0

    chosen = None
    holdout = Evaluation()
    if research and holdout_days:
        overall = [
            (sharpe(evaluate(series, p, research[0], research[-1], model).returns), p) for p in grid
        ]
        chosen = max(overall, key=lambda pair: pair[0])[1]
        holdout = evaluate(series, chosen, holdout_days[0], holdout_days[-1], model)
        trials.append(Trial(chosen, -1, "holdout", sharpe(holdout.returns), len(holdout.trades)))

    all_sharpes = [*earlier_trial_sharpes, *(t.sharpe for t in trials if t.sample == "in")]
    checks = _checks(rules, oos, holdout, len(windows), positive_windows, all_sharpes, benchmark)
    edge = fmean(t.r_multiple for t in oos.trades) if oos.trades else 0.0
    return ValidationReport(
        passed=all(c.passed for c in checks),
        checks=checks,
        chosen=chosen,
        out_of_sample=oos,
        holdout=holdout,
        trials=trials,
        edge_r=edge,
    )


def _benchmark_check(oos: Evaluation, benchmark: list[Bar] | None) -> Check:
    name = "Bättre riskjusterat än indexfonden"
    if benchmark is None or not oos.daily:
        return Check("benchmark", name, None, "jämförelsedata krävs", False)
    closes = {b.day: float(b.close) for b in benchmark}
    days = sorted(d for d in oos.daily if d in closes)
    index_returns = returns([closes[d] for d in days])
    strategy, index = annualised_sharpe(oos.returns), annualised_sharpe(index_returns)
    return Check("benchmark", name, strategy - index, "> 0 (Sharpe-skillnad)", strategy > index)


def _checks(
    rules: Validation,
    oos: Evaluation,
    holdout: Evaluation,
    windows: int,
    positive: int,
    trial_sharpes: Sequence[float],
    benchmark: list[Bar] | None,
) -> list[Check]:
    curve = [1.0]
    for r in oos.returns:
        curve.append(curve[-1] * (1 + r))
    dsr = deflated_sharpe(oos.returns, trial_sharpes) if oos.returns else 0.0
    drawdown = max_drawdown(curve) * 100
    factor = profit_factor(oos.trades)
    share = positive / windows * 100 if windows else 0.0
    holdout_sharpe = annualised_sharpe(holdout.returns) if holdout.returns else None
    return [
        Check(
            "trades",
            "Affärer utanför urvalet",
            len(oos.trades),
            f">= {rules.min_oos_trades}",
            len(oos.trades) >= rules.min_oos_trades,
        ),
        Check(
            "dsr",
            "Deflaterad Sharpe (sannolikhet)",
            dsr,
            f">= {rules.min_deflated_sharpe_probability}",
            dsr >= rules.min_deflated_sharpe_probability,
        ),
        Check(
            "drawdown",
            "Största nedgång (%)",
            drawdown,
            f"<= {rules.max_drawdown_pct}",
            bool(oos.returns) and drawdown <= rules.max_drawdown_pct,
        ),
        Check(
            "profit_factor",
            "Profit factor efter kostnader",
            factor,
            f">= {rules.min_profit_factor}",
            factor >= rules.min_profit_factor,
        ),
        Check(
            "windows",
            "Positiva walk-forward-fönster (%)",
            share,
            f">= {rules.min_positive_walk_forward_windows_pct}",
            windows > 0 and share >= rules.min_positive_walk_forward_windows_pct,
        ),
        Check(
            "parameters",
            "Fria parametrar",
            FREE_PARAMETERS,
            f"<= {rules.max_free_parameters}",
            rules.max_free_parameters >= FREE_PARAMETERS,
        ),
        Check(
            "holdout",
            "Låst holdout (Sharpe per år)",
            holdout_sharpe,
            "> 0",
            holdout_sharpe is not None and holdout_sharpe > 0,
        ),
        _benchmark_check(oos, benchmark),
    ]


def report_sv(name: str, report: ValidationReport) -> str:
    """A short, honest report in Swedish (§6.5)."""
    lines = [f"# Validering: {name}", ""]
    verdict = "klarade alla krav" if report.passed else "klarade INTE kraven och handlas inte"
    lines.append(f"Strategin {verdict}.")
    lines.append("")
    lines.append("| Krav | Värde | Gräns | Resultat |")
    lines.append("|---|---|---|---|")
    for check in report.checks:
        value = "saknas" if check.value is None else f"{check.value:.2f}".replace(".", ",")
        lines.append(
            f"| {check.name_sv} | {value} | {check.required} | "
            f"{'godkänt' if check.passed else 'underkänt'} |"
        )
    lines.append("")
    lines.append(
        f"Prövade varianter: {sum(t.sample == 'in' for t in report.trials)}. "
        "Varje variant höjer kravet på resultatet (deflaterad Sharpe)."
    )
    return "\n".join(lines)
