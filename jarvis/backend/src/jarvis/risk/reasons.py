"""Why the risk engine blocked something. Codes are stable; Adam sees the Swedish text."""

from enum import StrEnum


class Reason(StrEnum):
    # Trading state (circuit breakers, kill switch, health)
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    WEEKLY_LOSS_LIMIT = "weekly_loss_limit"
    KILL_SWITCH_DRAWDOWN = "kill_switch_drawdown"
    KILL_SWITCH_ENGAGED = "kill_switch_engaged"
    PAUSED = "paused"
    BROKER_DISCONNECTED = "broker_disconnected"
    BROKER_ERRORS = "broker_errors"
    CLOCK_DRIFT = "clock_drift"
    NOT_RECONCILED = "not_reconciled"
    # Order validity
    INVALID_QUANTITY = "invalid_quantity"
    INVALID_PRICE = "invalid_price"
    MISSING_STOP = "missing_stop"
    INVALID_STOP = "invalid_stop"
    SHORT_SELLING_NOT_ALLOWED = "short_selling_not_allowed"
    COVERED_BY_STOP = "covered_by_stop"
    NO_EQUITY = "no_equity"
    # Market data and timing
    MISSING_QUOTE = "missing_quote"
    STALE_QUOTE = "stale_quote"
    FUTURE_QUOTE = "future_quote"
    PRICE_DEVIATION = "price_deviation"
    MARKET_CLOSED = "market_closed"
    OUTSIDE_TRADING_WINDOW = "outside_trading_window"
    ORDER_RATE_MINUTE = "order_rate_minute"
    ORDER_RATE_DAY = "order_rate_day"
    # Sizing and portfolio limits
    TRADE_RISK_LIMIT = "trade_risk_limit"
    POSITION_LIMIT = "position_limit"
    GAP_LOSS_LIMIT = "gap_loss_limit"
    UNKNOWN_SECTOR = "unknown_sector"
    SECTOR_LIMIT = "sector_limit"
    CRYPTO_LIMIT = "crypto_limit"
    COMMODITIES_LIMIT = "commodities_limit"
    GROSS_EXPOSURE_LIMIT = "gross_exposure_limit"
    CASH_RESERVE = "cash_reserve"
    UNSETTLED_CASH = "unsettled_cash"
    MAX_OPEN_POSITIONS = "max_open_positions"
    # Economics
    MISSING_EDGE = "missing_edge"
    EDGE_TOO_SMALL = "edge_too_small"


MESSAGES_SV: dict[Reason, str] = {
    Reason.DAILY_LOSS_LIMIT: "Dagens förlust har nått gränsen. Inga nya affärer i dag.",
    Reason.WEEKLY_LOSS_LIMIT: (
        "Veckans förlust har nått gränsen. Bara stängningar resten av veckan."
    ),
    Reason.KILL_SWITCH_DRAWDOWN: (
        "Nedgången från toppen har nått gränsen. Kill switch är aktiverad."
    ),
    Reason.KILL_SWITCH_ENGAGED: "Kill switch är aktiv. Du behöver starta handeln igen i appen.",
    Reason.PAUSED: "Handeln är pausad.",
    Reason.BROKER_DISCONNECTED: "Ingen anslutning till mäklaren.",
    Reason.BROKER_ERRORS: "För många fel i rad mot mäklaren.",
    Reason.CLOCK_DRIFT: "Serverns klocka avviker för mycket.",
    Reason.NOT_RECONCILED: "Positionerna stämmer inte mot mäklaren.",
    Reason.INVALID_QUANTITY: "Ordern har ett ogiltigt antal.",
    Reason.INVALID_PRICE: "Ordern har ett ogiltigt pris.",
    Reason.MISSING_STOP: "Ordern saknar stop-loss.",
    Reason.INVALID_STOP: "Stop-lossen ligger inte under köppriset.",
    Reason.SHORT_SELLING_NOT_ALLOWED: (
        "Ordern skulle sälja mer än innehavet. Blankning är inte tillåten."
    ),
    Reason.COVERED_BY_STOP: (
        "Aktierna skyddas redan av en stopporder hos mäklaren. Den tas bort före försäljningen."
    ),
    Reason.NO_EQUITY: "Kontot har inget kapital att handla med.",
    Reason.MISSING_QUOTE: "Det finns ingen aktuell kurs.",
    Reason.STALE_QUOTE: "Kursen är för gammal.",
    Reason.FUTURE_QUOTE: "Kursens tidsstämpel ligger i framtiden.",
    Reason.PRICE_DEVIATION: "Limitpriset avviker för mycket från senaste kurs.",
    Reason.MARKET_CLOSED: "Marknaden är stängd.",
    Reason.OUTSIDE_TRADING_WINDOW: "Inga nya affärer precis efter öppning eller före stängning.",
    Reason.ORDER_RATE_MINUTE: "För många order den senaste minuten.",
    Reason.ORDER_RATE_DAY: "För många order i dag.",
    Reason.TRADE_RISK_LIMIT: "Risken i affären är större än tillåtet.",
    Reason.POSITION_LIMIT: "Positionen skulle bli större än tillåtet.",
    Reason.GAP_LOSS_LIMIT: "Ett kursras förbi stoppen skulle ge för stor förlust.",
    Reason.UNKNOWN_SECTOR: "Bolagets sektor är okänd, så sektorgränsen kan inte kontrolleras.",
    Reason.SECTOR_LIMIT: "Sektorn skulle få för stor andel av kapitalet.",
    Reason.CRYPTO_LIMIT: "Krypto skulle få för stor andel av kapitalet.",
    Reason.COMMODITIES_LIMIT: "Råvaror skulle få för stor andel av kapitalet.",
    Reason.GROSS_EXPOSURE_LIMIT: "Den totala exponeringen skulle överstiga kapitalet.",
    Reason.CASH_RESERVE: "Kassareserven skulle bli för liten.",
    Reason.UNSETTLED_CASH: "Pengarna från dagens försäljningar är inte likvida än.",
    Reason.MAX_OPEN_POSITIONS: "Det finns redan max antal öppna positioner.",
    Reason.MISSING_EDGE: "Affären saknar beräknad förväntad vinst.",
    Reason.EDGE_TOO_SMALL: "Förväntad vinst är för liten jämfört med kostnaderna.",
}


def message_sv(reason: Reason) -> str:
    return MESSAGES_SV[reason]
