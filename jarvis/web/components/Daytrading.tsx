"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { api, type DayTrade, type Daytrading as DaytradingData } from "@/lib/api";
import { arrowFor, formatDecimal, formatMoney, formatTime, signOf } from "@/lib/format";

const PAUSED: DaytradingData["status"][] = ["losses_in_row", "daily_loss", "unknown"];

export function statusTone(status: DaytradingData["status"]): "warning" | "calm" {
  return PAUSED.includes(status) ? "warning" : "calm";
}

function Result({ amount, currency }: { amount: string; currency: string }) {
  const sign = signOf(amount);
  return (
    <span className="change" data-sign={sign}>
      <span aria-hidden="true">{arrowFor(sign)}</span> {formatMoney(amount, currency, true)}
    </span>
  );
}

function DayTradeRow({ trade }: { trade: DayTrade }) {
  return (
    <li className="item">
      <div className="item-head">
        <span className="headline">
          {trade.symbol} · {formatDecimal(String(trade.quantity), 0)} st
        </span>
        {trade.result !== null ? (
          <Result amount={trade.result} currency={trade.currency} />
        ) : (
          <span className="pill">Öppen</span>
        )}
      </div>
      <div className="secondary">
        Köpt {formatTime(trade.opened_at)}
        {trade.buy_price !== null && ` för ${formatMoney(trade.buy_price, trade.currency)}`}
        {trade.closed_at !== null && ` · Såld ${formatTime(trade.closed_at)}`}
        {trade.sell_price !== null && ` för ${formatMoney(trade.sell_price, trade.currency)}`}
      </div>
      {trade.explanation_sv !== null && <p className="explanation">{trade.explanation_sv}</p>}
    </li>
  );
}

/** The day-trading line on the home screen; the details are one tap away. */
export function DaytradingCard({ data }: { data: DaytradingData }) {
  return (
    <section className="card" aria-labelledby="daytrading-h">
      <h2 id="daytrading-h" className="label">Daytrading</h2>
      <Link className="link-row" href="/daytrading">
        <span className="status-line" data-tone={statusTone(data.status)}>
          {data.status_sv}
        </span>
        <span className="secondary" aria-hidden="true">›</span>
      </Link>
      <p className="caption">
        {data.trades.length === 0
          ? "Inga daytrades i dag."
          : `${data.trades.length} daytrades i dag`}
      </p>
    </section>
  );
}

export function Daytrading() {
  const query = useQuery({ queryKey: ["daytrading"], queryFn: api.daytrading });

  return (
    <div className="page">
      <Link className="back" href="/">
        ‹ Hem
      </Link>
      <h1 className="large-title">Daytrading</h1>
      {query.isError && query.data === undefined ? (
        <div className="empty">
          <p>Jag når inte servern just nu.</p>
          <button className="button" type="button" onClick={() => void query.refetch()}>
            Försök igen
          </button>
        </div>
      ) : query.data === undefined ? (
        <div className="skeleton skeleton-card" aria-busy="true" aria-label="Laddar" />
      ) : (
        <DaytradingDetails data={query.data} />
      )}
    </div>
  );
}

function DaytradingDetails({ data }: { data: DaytradingData }) {
  return (
    <div className="columns">
      <div className="column">
        <section className="card" aria-labelledby="dt-status-h">
          <h2 id="dt-status-h" className="label">Läge</h2>
          <p className="status-line" data-tone={statusTone(data.status)} role="status">
            {data.status_sv}
          </p>
          <ul className="list facts">
            <li className="row">
              <span>Öppna</span>
              <span>{data.open_count !== null ? `${data.open_count} av ${data.max_open}` : "–"}</span>
            </li>
            <li className="row">
              <span>Resultat i dag</span>
              {data.day_result !== null ? (
                <Result amount={data.day_result} currency={data.base_currency} />
              ) : (
                <span>–</span>
              )}
            </li>
            <li className="row">
              <span>Förluster i rad</span>
              <span>
                {data.losses_in_row !== null
                  ? `${data.losses_in_row} av ${data.pause_after_losses}`
                  : "–"}
              </span>
            </li>
          </ul>
        </section>
        <section className="card" aria-labelledby="dt-rules-h">
          <h2 id="dt-rules-h" className="label">Regler</h2>
          <ul className="list secondary">
            <li>Köper när kursen bryter över de första minuternas högsta nivå.</li>
            <li>Samma aktie igen bara efter en ny högsta nivå för dagen, högst 3 gånger.</li>
            <li>Högst {data.max_open} daytrades öppna samtidigt.</li>
            <li>
              Pausar för dagen vid {formatDecimal(String(data.max_daily_loss_pct), 1)} % förlust
              eller {data.pause_after_losses} förluster i rad.
            </li>
            <li>Säljer allt 15 minuter före börsens slut.</li>
          </ul>
        </section>
      </div>
      <div className="column">
        <section className="card" aria-labelledby="dt-trades-h">
          <h2 id="dt-trades-h" className="label">I dag</h2>
          {data.trades.length === 0 ? (
            <div className="empty">
              <p>Inga daytrades i dag.</p>
              <p className="secondary">Varje daytrade visas här med köp, försäljning och resultat.</p>
            </div>
          ) : (
            <ul className="list">
              {data.trades.map((t) => (
                <DayTradeRow key={t.id} trade={t} />
              ))}
            </ul>
          )}
        </section>
        <p className="caption footer">Uppdaterad {formatTime(data.as_of)}</p>
      </div>
    </div>
  );
}
