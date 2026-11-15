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
};
