"use client";

import { useQuery } from "@tanstack/react-query";

import { DaytradingCard } from "@/components/Daytrading";
import { Orb, orbTone } from "@/components/Orb";
import { api, type Market, type Portfolio, type Position, type Status, type Trade } from "@/lib/api";
import {
  arrowFor,
  formatDateTime,
  formatDecimal,
  formatMoney,
  formatPercent,
  formatTime,
  greeting,
  signOf,
} from "@/lib/format";

const STATE_TEXT: Record<Status["trading_state"], string> = {
  active: "Jarvis handlar",
  no_new_trades: "Inga nya affärer i dag",
  closing_only: "Bara stängningar den här veckan",
  paused: "Pausad",
  kill_switch: "Kill switch aktiv",
  halted: "Stoppad",
};

function stateText(status: Status): string {
  const anyOpen = status.markets.some((m) => m.is_open);
  if (status.trading_state === "active" && !anyOpen) return "Jarvis väntar – marknaden stängd";
  return STATE_TEXT[status.trading_state];
}

function Change({ amount, percent, currency }: { amount: string; percent: string | null; currency: string }) {
  const sign = signOf(amount);
  return (
    <span className="change" data-sign={sign}>
      <span aria-hidden="true">{arrowFor(sign)}</span> {formatMoney(amount, currency, true)}
      {percent !== null && <> ({formatPercent(percent)})</>}
    </span>
  );
}

function MarketRow({ market }: { market: Market }) {
  const time = market.is_open ? market.closes_at : market.opens_at;
  const label = market.is_open ? "Stänger" : "Öppnar";
  return (
    <li className="row">
      <span>
        <span className="dot" data-open={market.is_open} aria-hidden="true" /> {market.name_sv}
      </span>
      <span className="secondary">
        {market.is_open ? "Öppen" : "Stängd"}
        {time !== null && ` · ${label} ${formatDateTime(time)}`}
      </span>
    </li>
  );
}

function PositionRow({ position, base }: { position: Position; base: string }) {
  return (
    <li className="item">
      <div className="item-head">
        <span className="headline">{position.symbol}</span>
        <span className="headline">
          {position.market_value !== null ? formatMoney(position.market_value, base) : "–"}
        </span>
      </div>
      <div className="item-head secondary">
        <span>
          {formatDecimal(String(position.quantity), 0)} st
          {position.stop_price !== null &&
            ` · stopp ${formatMoney(position.stop_price, position.currency)}`}
        </span>
        {position.unrealized_pnl !== null && (
          <Change amount={position.unrealized_pnl} percent={position.unrealized_pnl_pct} currency={base} />
        )}
      </div>
      {position.strategy !== null && <div className="caption">Strategi: {position.strategy}</div>}
    </li>
  );
}

function TradeRow({ trade }: { trade: Trade }) {
  return (
    <li className="item">
      <div className="item-head">
        <span className="headline">
          {trade.side === "buy" ? "Köpt" : "Sålt"} {formatDecimal(String(trade.quantity), 0)} {trade.symbol}
        </span>
        <span>{formatMoney(trade.price, trade.currency)}</span>
      </div>
      <div className="secondary">{formatDateTime(trade.at)}</div>
      {trade.explanation_sv !== null && <p className="explanation">{trade.explanation_sv}</p>}
    </li>
  );
}

function Skeleton() {
  return (
    <div className="page" aria-busy="true" aria-label="Laddar">
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-orb" />
      <div className="skeleton skeleton-card" />
      <div className="skeleton skeleton-card" />
    </div>
  );
}

function Hero({ status, portfolio }: { status: Status; portfolio: Portfolio }) {
  const anyOpen = status.markets.some((m) => m.is_open);
  return (
    <section className="hero">
      <Orb tone={orbTone(status.trading_state, anyOpen)} />
      <p className="state" role="status">
        {stateText(status)}
      </p>
      {status.trading_state !== "active" && status.reasons[0] && (
        <p className="secondary reason">{status.reasons[0].message_sv}</p>
      )}
      <p className="big-number">
        {portfolio.net_liquidation !== null
          ? formatMoney(portfolio.net_liquidation, portfolio.base_currency)
          : "–"}
      </p>
      {portfolio.day_change !== null ? (
        <p className="subhead">
          <Change amount={portfolio.day_change} percent={portfolio.day_change_pct} currency={portfolio.base_currency} />{" "}
          <span className="secondary">i dag</span>
        </p>
      ) : (
        <p className="secondary subhead">Ingen förändring att visa ännu.</p>
      )}
    </section>
  );
}

export function Home() {
  const status = useQuery({ queryKey: ["status"], queryFn: api.status });
  const portfolio = useQuery({ queryKey: ["portfolio"], queryFn: api.portfolio });
  const trades = useQuery({ queryKey: ["trades"], queryFn: () => api.trades(10) });
  const today = useQuery({ queryKey: ["today"], queryFn: api.today });
  const daytrading = useQuery({ queryKey: ["daytrading"], queryFn: api.daytrading });
  const queries = [status, portfolio, trades, today];

  if (queries.some((q) => q.isError && q.data === undefined)) {
    return (
      <div className="page center">
        <Orb tone="dimmed" />
        <h1 className="title">Jag når inte servern just nu.</h1>
        <p className="secondary">
          Dina positioner skyddas av stoppordrarna hos mäklaren även när appen inte får kontakt.
        </p>
        <button className="button" type="button" onClick={() => queries.forEach((q) => void q.refetch())}>
          Försök igen
        </button>
      </div>
    );
  }
  if (!status.data || !portfolio.data || !trades.data || !today.data) return <Skeleton />;

  const base = portfolio.data.base_currency;
  return (
    <div className="page">
      <header className="top">
        <div>
          <h1 className="large-title">{greeting(new Date(status.data.as_of))}</h1>
          <p className="secondary briefing">{status.data.briefing_sv}</p>
        </div>
        <span className="badge" data-mode={status.data.mode}>
          {status.data.mode === "paper" ? "PAPPER" : "LIVE"}
        </span>
      </header>

      <div className="columns">
        <div className="column">
          <Hero status={status.data} portfolio={portfolio.data} />

          <section className="card" aria-labelledby="today-h">
            <h2 id="today-h" className="label">Idag</h2>
            <dl className="today">
              <div>
                <dt>Affärer</dt>
                <dd>{today.data.trades_count}</dd>
              </div>
              <div>
                <dt>Resultat</dt>
                <dd>
                  {today.data.realized_pnl !== null ? (
                    <Change amount={today.data.realized_pnl} percent={null} currency={base} />
                  ) : (
                    "–"
                  )}
                </dd>
              </div>
              <div>
                <dt>Risknivå</dt>
                <dd>{today.data.risk_level_sv}</dd>
              </div>
            </dl>
          </section>

          {daytrading.data !== undefined && <DaytradingCard data={daytrading.data} />}

          <section className="card" aria-labelledby="markets-h">
            <h2 id="markets-h" className="label">Marknader</h2>
            <ul className="list">
              {status.data.markets.map((m) => (
                <MarketRow key={m.exchange} market={m} />
              ))}
            </ul>
          </section>
        </div>

        <div className="column">
          <section className="card" aria-labelledby="positions-h">
            <h2 id="positions-h" className="label">Innehav</h2>
            {portfolio.data.positions.length === 0 ? (
              <div className="empty">
                <p>Inga innehav just nu.</p>
                <p className="secondary">Jag köper först när en strategi ger signal och risken ryms inom ramarna.</p>
              </div>
            ) : (
              <ul className="list">
                {portfolio.data.positions.map((p) => (
                  <PositionRow key={p.symbol} position={p} base={base} />
                ))}
              </ul>
            )}
          </section>

          <section className="card" aria-labelledby="trades-h">
            <h2 id="trades-h" className="label">Senaste affärer</h2>
            {trades.data.trades.length === 0 ? (
              <div className="empty">
                <p>Inga affärer ännu.</p>
                <p className="secondary">Varje affär visas här med en förklaring av varför jag gjorde den.</p>
              </div>
            ) : (
              <ul className="list">
                {trades.data.trades.map((t) => (
                  <TradeRow key={t.id} trade={t} />
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>

      <footer className="caption footer">Uppdaterad {formatTime(status.data.as_of)}</footer>
    </div>
  );
}
