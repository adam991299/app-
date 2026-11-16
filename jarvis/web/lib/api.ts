// Mirrors jarvis/contracts/api.schema.json. Money values are decimal strings.

export type TradingState =
  | "active"
  | "no_new_trades"
  | "closing_only"
  | "paused"
  | "kill_switch"
  | "halted";

export interface Reason {
  code: string;
  message_sv: string;
}

export interface Market {
  exchange: string;
  name_sv: string;
  is_open: boolean;
  opens_at: string | null;
  closes_at: string | null;
}

export interface Status {
  mode: "paper" | "live";
  trading_state: TradingState;
  reasons: Reason[];
  broker_connected: boolean;
  markets: Market[];
  briefing_sv: string;
  as_of: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  currency: string;
  average_price: string;
  last_price: string | null;
  market_value: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_pct: string | null;
  stop_price: string | null;
  strategy: string | null;
}

export interface Portfolio {
  base_currency: string;
  net_liquidation: string | null;
  cash: string | null;
  day_change: string | null;
  day_change_pct: string | null;
  positions: Position[];
  as_of: string;
}

export interface Trade {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  price: string;
  commission: string;
  currency: string;
  at: string;
  strategy: string | null;
  explanation_sv: string | null;
}

export interface Trades {
  trades: Trade[];
}

export interface Today {
  trades_count: number;
  realized_pnl: string | null;
  risk_level_sv: string;
}

export type DaytradingStatus =
  | "not_validated"
  | "market_closed"
  | "active"
  | "full"
  | "losses_in_row"
  | "daily_loss"
  | "closing"
  | "unknown";

export interface DayTrade {
  id: string;
  symbol: string;
  currency: string;
  quantity: number;
  buy_price: string | null;
  sell_price: string | null;
  result: string | null;
  is_open: boolean;
  opened_at: string;
  closed_at: string | null;
  explanation_sv: string | null;
}

export interface Daytrading {
  status: DaytradingStatus;
  status_sv: string;
  open_count: number | null;
  max_open: number;
  day_result: string | null;
  base_currency: string;
  losses_in_row: number | null;
  max_daily_loss_pct: number;
  pause_after_losses: number;
  trades: DayTrade[];
  as_of: string;
}

export interface Cost {
  name_sv: string;
  monthly: string;
}

export interface ComparisonPoint {
  day: string;
  jarvis: string;
  index: string;
}

export interface Comparison {
  start: string;
  days: number;
  jarvis_pct: string;
  index_pct: string;
  difference_pct: string;
  points: ComparisonPoint[];
}

export interface Amount {
  amount: string;
  currency: string;
}

export interface Economics {
  base_currency: string;
  capital: string | null;
  monthly_costs: Cost[];
  monthly_total: string;
  break_even_pct: string | null;
  break_even_warning: boolean;
  break_even_limit_pct: number;
  tax_drag_pct: string | null;
  tax_sv: string;
  index_name_sv: string;
  verdict_sv: string;
  comparison: Comparison | null;
  commissions: Amount[];
  as_of: string;
}

/** Property names per contract type, compared with the JSON Schema by `npm test`. */
export const CONTRACT_KEYS = {
  StatusOut: ["mode", "trading_state", "reasons", "broker_connected", "markets", "briefing_sv", "as_of"],
  ReasonOut: ["code", "message_sv"],
  MarketOut: ["exchange", "name_sv", "is_open", "opens_at", "closes_at"],
  PortfolioOut: ["base_currency", "net_liquidation", "cash", "day_change", "day_change_pct", "positions", "as_of"],
  PositionOut: [
    "symbol", "quantity", "currency", "average_price", "last_price", "market_value",
    "unrealized_pnl", "unrealized_pnl_pct", "stop_price", "strategy",
  ],
  TradesOut: ["trades"],
  TradeOut: [
    "id", "symbol", "side", "quantity", "price", "commission", "currency", "at", "strategy",
    "explanation_sv",
  ],
  TodayOut: ["trades_count", "realized_pnl", "risk_level_sv"],
  DaytradingOut: [
    "status", "status_sv", "open_count", "max_open", "day_result", "base_currency",
    "losses_in_row", "max_daily_loss_pct", "pause_after_losses", "trades", "as_of",
  ],
  EconomicsOut: [
    "base_currency", "capital", "monthly_costs", "monthly_total", "break_even_pct",
    "break_even_warning", "break_even_limit_pct", "tax_drag_pct", "tax_sv", "index_name_sv",
    "verdict_sv", "comparison", "commissions", "as_of",
  ],
  CostOut: ["name_sv", "monthly"],
  ComparisonOut: ["start", "days", "jarvis_pct", "index_pct", "difference_pct", "points"],
  ComparisonPointOut: ["day", "jarvis", "index"],
  AmountOut: ["amount", "currency"],
  DayTradeOut: [
    "id", "symbol", "currency", "quantity", "buy_price", "sell_price", "result", "is_open",
    "opened_at", "closed_at", "explanation_sv",
  ],
} as const;

const TIMEOUT_MS = 8000;

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`, {
    signal: AbortSignal.timeout(TIMEOUT_MS),
    headers: { accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`API ${path} answered ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  status: () => get<Status>("/status"),
  portfolio: () => get<Portfolio>("/portfolio"),
  trades: (limit: number) => get<Trades>(`/trades?limit=${limit}`),
  today: () => get<Today>("/today"),
  daytrading: () => get<Daytrading>("/daytrading"),
  economics: () => get<Economics>("/economics"),
};
