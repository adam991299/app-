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

const ecoDays = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16"];
const jarvisPath = [100, 100.4, 100.1, 100.9, 101.3, 101.0, 101.8, 102.2, 101.6, 102.4, 102.9, 102.5, 103.1, 103.4, 102.8, 103.6, 104.0, 103.7, 104.3, 104.1, 104.62];
const indexPath = [100, 100.6, 100.9, 100.5, 101.2, 101.8, 101.4, 102.0, 102.6, 102.1, 102.4, 103.0, 102.7, 102.2, 102.9, 103.3, 102.8, 103.1, 103.5, 103.2, 103.38];

export const economics = {
  base_currency: "SEK",
  capital: "100482.35",
  monthly_costs: [
    { name_sv: "Server (Oracle Always Free)", monthly: "0.00" },
    { name_sv: "Marknadsdata (IBKR, USA-aktier)", monthly: "0.00" },
    { name_sv: "Övrigt", monthly: "0.00" },
  ],
  monthly_total: "0.00",
  break_even_pct: "0.00",
  break_even_warning: false,
  break_even_limit_pct: 3.0,
  tax_drag_pct: null,
  tax_sv: "Årets ISK-siffror från Skatteverket saknas i inställningarna, så jag räknar inte med skatten än. Jag gissar dem aldrig.",
  index_name_sv: "S&P 500-fonden (SPY)",
  verdict_sv: "Jag ligger 1,24 procentenheter före S&P 500-fonden (SPY) efter kostnader.",
  comparison: {
    start: ecoDays[0],
    days: ecoDays.length,
    jarvis_pct: "4.62",
    index_pct: "3.38",
    difference_pct: "1.24",
    points: ecoDays.map((day, i) => ({ day, jarvis: jarvisPath[i].toFixed(2), index: indexPath[i].toFixed(2) })),
  },
  commissions: [{ amount: "14.20", currency: "USD" }],
  as_of: "2026-11-16T18:02:00Z",
};

export const economicsEmpty = {
  ...economics,
  capital: null,
  break_even_pct: null,
  verdict_sv: "Jag har ännu inte tillräckligt med data för att jämföra mig med S&P 500-fonden (SPY). Jämförelsen börjar när jag har följt kontot i minst två handelsdagar.",
  comparison: null,
  commissions: [],
};
