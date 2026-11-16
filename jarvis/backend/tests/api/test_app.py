from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx2 as httpx
import pytest

from jarvis.api.app import create_api_app
from jarvis.api.views import _briefing, _count_sv
from jarvis.broker.models import Fill
from jarvis.config.settings import Settings
from jarvis.domain import Side
from jarvis.store.repo import NewOrder, Store

D = Decimal
NOW = datetime(2026, 11, 16, 18, tzinfo=UTC)  # Monday 13:00 in New York: open


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
async def client(store: Store, clock: Clock) -> AsyncIterator[httpx.AsyncClient]:
    app = create_api_app(store, Settings(), clock)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as c:
        yield c


def state(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "base_currency": "SEK",
        "net_liquidation": "100482.35",
        "cash": "81250.10",
        "positions": [
            {
                "symbol": "MSFT",
                "quantity": 12,
                "currency": "USD",
                "average_price": "512.40",
                "last_price": "518.90",
                "market_value": "9872.00",
                "unrealized_pnl": "742.10",
                "unrealized_pnl_pct": "1.27",
                "stop_price": "489.00",
                "strategy": "trend",
            }
        ],
        "trading_state": "active",
        "reasons": [],
        "broker_connected": True,
        "reconciled": True,
    }
    return base | overrides


async def test_without_any_state_the_app_is_told_honestly(client: httpx.AsyncClient) -> None:
    status = (await client.get("/status")).json()
    assert status["trading_state"] == "halted"
    assert status["reasons"][0]["code"] == "no_state"
    assert status["mode"] == "paper"
    assert status["broker_connected"] is False
    assert status["markets"][0]["name_sv"] == "USA"
    portfolio = (await client.get("/portfolio")).json()
    assert portfolio["net_liquidation"] is None
    assert portfolio["positions"] == []
    assert (await client.get("/trades")).json() == {"trades": []}
    today = (await client.get("/today")).json()
    assert today == {
        "trades_count": 0,
        "realized_pnl": None,
        "risk_level_sv": today["risk_level_sv"],
    }


async def test_status_and_portfolio_from_state(
    client: httpx.AsyncClient, store: Store, clock: Clock
) -> None:
    await store.record_equity(at=NOW - timedelta(days=1), net_liquidation=D(100000), cash=D(1))
    await store.record_equity(at=NOW, net_liquidation=D("100482.35"), cash=D(1))
    await store.save_account_state(state(), at=NOW)
    status = (await client.get("/status")).json()
    assert status["trading_state"] == "active"
    assert status["broker_connected"] is True
    usa = status["markets"][0]
    assert (usa["is_open"], usa["closes_at"]) == (True, "2026-11-16T21:00:00Z")
    assert status["briefing_sv"] == "En position är öppen. Allt inom riskramarna. USA är öppen."
    portfolio = (await client.get("/portfolio")).json()
    assert portfolio["net_liquidation"] == "100482.35"
    assert portfolio["day_change"] == "482.35"
    assert portfolio["day_change_pct"] == "0.48"
    assert portfolio["positions"][0]["stop_price"] == "489.00"
    assert portfolio["positions"][0]["strategy"] == "Trendföljning"


async def test_blocked_state_carries_swedish_reasons(
    client: httpx.AsyncClient, store: Store
) -> None:
    await store.save_account_state(
        state(trading_state="kill_switch", reasons=["kill_switch_engaged"], positions=[]), at=NOW
    )
    status = (await client.get("/status")).json()
    assert status["reasons"] == [
        {
            "code": "kill_switch_engaged",
            "message_sv": "Kill switch är aktiv. Du behöver starta handeln igen i appen.",
        }
    ]
    assert status["briefing_sv"].startswith(
        "Inga positioner är öppna. Inga nya affärer tas just nu."
    )


async def test_stale_state_halts(client: httpx.AsyncClient, store: Store, clock: Clock) -> None:
    await store.save_account_state(state(), at=NOW)
    clock.now = NOW + timedelta(minutes=4)
    status = (await client.get("/status")).json()
    assert status["trading_state"] == "halted"
    assert "flera minuter" in status["reasons"][0]["message_sv"]


async def test_closed_market_shows_next_session(
    client: httpx.AsyncClient, store: Store, clock: Clock
) -> None:
    clock.now = datetime(2026, 11, 14, 12, tzinfo=UTC)  # Saturday
    await store.save_account_state(state(positions=[]), at=clock.now)
    usa = (await client.get("/status")).json()["markets"][0]
    assert usa["is_open"] is False
    assert usa["opens_at"] == "2026-11-16T14:30:00Z"
    assert usa["closes_at"] == "2026-11-16T21:00:00Z"


async def test_market_outside_the_calendar_has_no_times(
    client: httpx.AsyncClient, store: Store, clock: Clock
) -> None:
    clock.now = datetime(2031, 1, 1, tzinfo=UTC)
    usa = (await client.get("/status")).json()["markets"][0]
    assert (usa["opens_at"], usa["closes_at"]) == (None, None)


async def test_nordic_market_listed_when_enabled(store: Store, clock: Clock) -> None:
    settings = Settings.model_validate({"markets": {"nordic_equities": True}})
    app = create_api_app(store, settings, clock)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://a") as c:
        names = [m["name_sv"] for m in (await c.get("/status")).json()["markets"]]
    assert names == ["USA", "Stockholm"]


async def test_trades_explain_entries_and_exits(client: httpx.AsyncClient, store: Store) -> None:
    def order(cid: str, kind: str, side: str, **kw: Any) -> NewOrder:
        return NewOrder(
            cid,
            kind,
            "MSFT",
            side,
            12,
            kw.get("limit"),
            kw.get("stop"),
            strategy="trend",
            explanation_sv=kw.get("why"),
            currency="USD",
            parent_id=kw.get("parent"),
        )

    await store.add_order(
        order(
            "e",
            "entry",
            "buy",
            limit=D(512),
            stop=D(489),
            why="Kursen bröt över sin högsta nivå på 55 dagar.",
        ),
        at=NOW,
    )
    await store.add_order(order("e.stop", "stop", "sell", stop=D(489), parent="e"), at=NOW)
    await store.add_order(order("e.tp", "take_profit", "sell", limit=D(600), parent="e"), at=NOW)
    await store.add_order(
        order("x", "exit", "sell", limit=D(500), why="Manuell stängning."), at=NOW
    )
    for i, (cid, side) in enumerate(
        [("e", Side.BUY), ("e.stop", Side.SELL), ("e.tp", Side.SELL), ("x", Side.SELL)]
    ):
        await store.record_fill(
            Fill(f"f{i}", cid, "MSFT", side, 3, D("512.40"), D(1), NOW + timedelta(minutes=i))
        )
    trades = (await client.get("/trades", params={"limit": 10})).json()["trades"]
    assert [t["id"] for t in trades] == ["f3", "f2", "f1", "f0"]
    assert trades[3]["explanation_sv"] == "Kursen bröt över sin högsta nivå på 55 dagar."
    assert trades[2]["explanation_sv"] == "Stoppen hos mäklaren utlöstes. Såld till 512,40."
    assert trades[1]["explanation_sv"] == "Målkursen 600,00 nåddes."
    assert trades[0]["explanation_sv"] == "Manuell stängning."
    assert trades[0]["currency"] == "USD"
    assert trades[0]["strategy"] == "Trendföljning"
    assert trades[0]["price"] == "512.40"
    assert trades[0]["commission"] == "1.00"
    assert (await client.get("/today")).json()["trades_count"] == 4
    assert (await client.get("/trades", params={"limit": 0})).status_code == 422


def test_briefing_wording() -> None:
    assert _count_sv(3) == "Tre"
    assert _count_sv(12) == "12"
    soon = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
    from jarvis.api.schemas import MarketOut

    market = MarketOut(
        exchange="XNYS",
        name_sv="USA",
        is_open=False,
        opens_at=datetime(2026, 11, 16, 14, 30, tzinfo=UTC),
        closes_at=None,
    )
    payload = {"positions": [{}, {}], "trading_state": "active"}
    assert _briefing(payload, [market], soon) == (
        "Två positioner är öppna. Allt inom riskramarna. USA öppnar inom en timme."
    )
    later = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
    assert _briefing(payload, [market], later).endswith("USA öppnar om 4 timmar.")
    assert _briefing(payload, [], later) == "Två positioner är öppna. Allt inom riskramarna."


async def test_state_without_equity_history_has_no_day_change(
    client: httpx.AsyncClient, store: Store
) -> None:
    await store.save_account_state(state(net_liquidation="1000.123456"), at=NOW)
    portfolio = (await client.get("/portfolio")).json()
    assert portfolio["day_change"] is None
    assert portfolio["net_liquidation"] == "1000.123456"


async def test_no_markets_listed_when_none_enabled(store: Store, clock: Clock) -> None:
    settings = Settings.model_validate({"markets": {"us_equities": False}})
    app = create_api_app(store, settings, clock)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://a") as c:
        assert (await c.get("/status")).json()["markets"] == []


def test_swedish_number_in_sentences() -> None:
    from jarvis.api.views import _sv

    assert _sv(D("12345.6")) == "12 345,60"


def test_unknown_strategy_ids_are_shown_as_they_are() -> None:
    from jarvis.api.views import strategy_sv

    assert strategy_sv("experiment-7") == "experiment-7"
    assert strategy_sv(None) is None


async def test_daytrading_without_a_report_says_so(client: httpx.AsyncClient) -> None:
    body = (await client.get("/daytrading")).json()
    assert body["status"] == "unknown"
    assert body["status_sv"] == "Jag har ingen lägesrapport från daytradingen ännu."
    assert body["trades"] == []
    assert body["base_currency"] == "SEK"
    assert (body["max_open"], body["pause_after_losses"]) == (5, 3)


async def test_daytrading_shows_todays_trades_and_why_it_paused(
    client: httpx.AsyncClient, store: Store, clock: Clock
) -> None:
    def order(cid: str, kind: str, side: str, parent: str | None = None) -> NewOrder:
        return NewOrder(
            cid,
            kind,
            "AMD",
            side,
            10,
            D(150),
            D(140),
            strategy="orb",
            explanation_sv="Daytrade: kursen bröt över de första 15 minuternas högsta nivå."
            if kind == "entry"
            else None,
            currency="USD",
            parent_id=parent,
        )

    for entry in ("orb:AMD:2026-11-16", "orb:AMD:2026-11-16:2"):
        await store.add_order(order(entry, "entry", "buy"), at=NOW)
        await store.add_order(order(f"{entry}.stop", "stop", "sell", entry), at=NOW)
    fills = [
        ("orb:AMD:2026-11-16", Side.BUY, "150"),
        ("orb:AMD:2026-11-16.stop", Side.SELL, "140"),
        ("orb:AMD:2026-11-16:2", Side.BUY, "152"),
    ]
    for i, (cid, side, price) in enumerate(fills):
        await store.record_fill(
            Fill(f"d{i}", cid, "AMD", side, 10, D(price), D(1), NOW + timedelta(minutes=i))
        )
    await store.save_strategy_state(
        "orb",
        {
            "status": "losses_in_row",
            "open_count": 1,
            "max_open": 5,
            "day_result": "-1020.004",
            "losses_in_row": 3,
            "max_daily_loss_pct": 1.0,
            "pause_after_losses": 3,
        },
        at=NOW,
    )
    body = (await client.get("/daytrading")).json()
    assert body["status_sv"] == "Jag har pausat daytrading för i dag efter 3 förluster i rad."
    assert (body["open_count"], body["day_result"], body["losses_in_row"]) == (1, "-1020.00", 3)
    newest, first = body["trades"]
    assert newest["is_open"] is True
    assert newest["result"] is None
    assert newest["closed_at"] is None
    assert (first["buy_price"], first["sell_price"], first["result"]) == (
        "150.00",
        "140.00",
        "-102.00",
    )
    assert first["explanation_sv"].startswith("Daytrade:")
    clock.now = NOW + timedelta(minutes=10)
    stale = (await client.get("/daytrading")).json()
    assert stale["status"] == "unknown"
    assert "flera minuter" in stale["status_sv"]


@pytest.mark.parametrize(
    ("status", "text"),
    [
        (
            "daily_loss",
            "Jag har pausat daytrading för i dag: dagens förlust nådde 1,5 % av kapitalet.",
        ),
        ("not_validated", "Daytrading är avstängd tills strategin har klarat valideringen."),
        ("active", "Jag letar efter utbrott."),
    ],
)
def test_daytrading_wording(status: str, text: str) -> None:
    from jarvis.api.views import _daytrading_sv

    payload = {"status": status, "losses_in_row": 0, "max_daily_loss_pct": 1.5}
    assert _daytrading_sv(payload) == text


async def test_economics_before_any_data_is_honest(client: httpx.AsyncClient) -> None:
    body = (await client.get("/economics")).json()
    assert body["capital"] is None
    assert body["break_even_pct"] is None
    assert body["comparison"] is None
    assert "inte tillräckligt med data" in body["verdict_sv"]
    assert "saknas i inställningarna" in body["tax_sv"]
    assert body["commissions"] == []


async def test_economics_compares_with_the_index_fund(
    client: httpx.AsyncClient, store: Store
) -> None:
    await store.save_account_state(state(), at=NOW)
    start = NOW - timedelta(days=3)
    for i, value in enumerate(["100000", "101000", "102000"]):
        await store.record_equity(at=start + timedelta(days=i), net_liquidation=D(value), cash=D(0))
        await store.save_index_fund_close(
            "SPY", (start + timedelta(days=i)).date(), D(500) + i * 5, D("10.5")
        )
    body = (await client.get("/economics")).json()
    comparison = body["comparison"]
    assert (comparison["days"], comparison["jarvis_pct"], comparison["index_pct"]) == (
        3,
        "2.00",
        "2.00",
    )
    assert comparison["points"][0] == {
        "day": start.date().isoformat(),
        "jarvis": "100.00",
        "index": "100.00",
    }
    assert "för tidigt" in body["verdict_sv"]
    assert body["break_even_pct"] == "0.00"
    assert body["break_even_warning"] is False


@pytest.mark.parametrize(
    ("tax", "text"),
    [
        ({"model": "capital_gains"}, "beskattas inte som ISK"),
        (
            {"tax_year": 2025, "isk_tax_free_level_sek": 150000, "isk_schablon_tax_pct": 0.888},
            "gäller 2025",
        ),
        (
            {"tax_year": 2026, "isk_tax_free_level_sek": 0, "isk_schablon_tax_pct": 1.0},
            "ungefär 1,00 % av kapitalet",
        ),
    ],
)
async def test_isk_tax_text(store: Store, clock: Clock, tax: dict[str, Any], text: str) -> None:
    settings = Settings.model_validate(
        {"tax": tax, "economics": {"monthly_costs_sek": {"VPS": 300}}}
    )
    await store.save_account_state(state(), at=NOW)
    app = create_api_app(store, settings, clock)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        body = (await c.get("/economics")).json()
    assert text in body["tax_sv"]
    assert body["monthly_total"] == "300.00"
    assert body["break_even_warning"] is True  # 3 600 kr a year on ~100 000 kr is over 3 %


async def test_without_capital_no_tax_is_computed(store: Store, clock: Clock) -> None:
    tax = {"tax_year": 2026, "isk_tax_free_level_sek": 0, "isk_schablon_tax_pct": 1.0}
    app = create_api_app(store, Settings.model_validate({"tax": tax}), clock)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        body = (await c.get("/economics")).json()
    assert body["tax_sv"] == "Skatten räknas när jag vet hur stort kapitalet är."
