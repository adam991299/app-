// Example data for tests and screenshots only. Never shipped to the app.
export const status = {
  mode: "paper",
  trading_state: "active",
  reasons: [],
  broker_connected: true,
  markets: [
    { exchange: "XNYS", name_sv: "USA", is_open: true, opens_at: "2026-11-16T14:30:00Z", closes_at: "2026-11-16T21:00:00Z" },
    { exchange: "XSTO", name_sv: "Stockholm", is_open: false, opens_at: "2026-11-17T08:00:00Z", closes_at: "2026-11-17T16:30:00Z" },
  ],
  briefing_sv: "Två positioner är öppna. Allt inom riskramarna. USA stänger om tre timmar.",
  as_of: "2026-11-16T18:02:00Z",
};

export const portfolio = {
  base_currency: "SEK",
  net_liquidation: "100482.35",
  cash: "81250.10",
  day_change: "482.35",
  day_change_pct: "0.48",
  positions: [
    { symbol: "MSFT", quantity: 12, currency: "USD", average_price: "512.40", last_price: "518.90", market_value: "9872.00", unrealized_pnl: "742.10", unrealized_pnl_pct: "1.27", stop_price: "489.00", strategy: "Trendföljning" },
    { symbol: "XOM", quantity: 40, currency: "USD", average_price: "121.10", last_price: "119.85", market_value: "9360.25", unrealized_pnl: "-259.75", unrealized_pnl_pct: "-1.03", stop_price: "114.50", strategy: "Trendföljning" },
  ],
  as_of: "2026-11-16T18:02:00Z",
};

export const trades = {
  trades: [
    { id: "t2", symbol: "XOM", side: "buy", quantity: 40, price: "121.10", commission: "1.00", currency: "USD", at: "2026-11-16T15:12:00Z", strategy: "Trendföljning", explanation_sv: "Kursen bröt över sin högsta nivå på 55 dagar. Stoppen ligger 5,5 % under köpet." },
    { id: "t1", symbol: "MSFT", side: "buy", quantity: 12, price: "512.40", commission: "1.00", currency: "USD", at: "2026-11-13T15:41:00Z", strategy: "Trendföljning", explanation_sv: "Kursen bröt över sin högsta nivå på 55 dagar." },
  ],
};

export const today = { trades_count: 1, realized_pnl: "0", risk_level_sv: "Balanserad" };

export const empty = {
  status: { ...status, markets: status.markets.map((m) => ({ ...m, is_open: false })), briefing_sv: "Inga affärer pågår. Marknaderna är stängda." },
  portfolio: { ...portfolio, net_liquidation: "100000.00", cash: "100000.00", day_change: null, day_change_pct: null, positions: [] },
  trades: { trades: [] },
  today: { trades_count: 0, realized_pnl: null, risk_level_sv: "Balanserad" },
};

export const killSwitch = {
  ...status,
  trading_state: "kill_switch",
  reasons: [{ code: "kill_switch_engaged", message_sv: "Kill switch är aktiv. Du behöver starta handeln igen i appen." }],
  briefing_sv: "Handeln är stoppad. Öppna positioner skyddas av stoppordrarna hos mäklaren.",
};

export const daytrading = {
  status: "losses_in_row",
  status_sv: "Jag har pausat daytrading för i dag efter 3 förluster i rad.",
  open_count: 1,
  max_open: 5,
  day_result: "-1820.40",
  base_currency: "SEK",
  losses_in_row: 3,
  max_daily_loss_pct: 1.0,
  pause_after_losses: 3,
  trades: [
    { id: "orb:AMD:2026-11-16:2", symbol: "AMD", currency: "USD", quantity: 20, buy_price: "152.10", sell_price: null, result: null, is_open: true, opened_at: "2026-11-16T16:05:00Z", closed_at: null, explanation_sv: "Daytrade igen: kursen bröt över dagens högsta nivå (151,95). Stopp vid öppningsintervallets lägsta nivå 147,20." },
    { id: "orb:AMD:2026-11-16", symbol: "AMD", currency: "USD", quantity: 20, buy_price: "150.00", sell_price: "151.80", result: "34.00", is_open: false, opened_at: "2026-11-16T14:55:00Z", closed_at: "2026-11-16T15:40:00Z", explanation_sv: "Daytrade: kursen bröt över de första 15 minuternas högsta nivå (149,80). Stopp vid öppningsintervallets lägsta nivå 147,20." },
    { id: "orb:NKE:2026-11-16", symbol: "NKE", currency: "USD", quantity: 60, buy_price: "61.40", sell_price: "59.95", result: "-89.20", is_open: false, opened_at: "2026-11-16T14:50:00Z", closed_at: "2026-11-16T15:20:00Z", explanation_sv: null },
  ],
  as_of: "2026-11-16T18:02:00Z",
};

export const daytradingEmpty = {
  ...daytrading,
  status: "not_validated",
  status_sv: "Daytrading är avstängd tills strategin har klarat valideringen.",
  open_count: 0,
  day_result: "0",
  losses_in_row: 0,
  trades: [],
};
