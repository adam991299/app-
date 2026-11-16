"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type PointerEvent } from "react";

import { api, type Comparison, type Economics as EconomicsData } from "@/lib/api";
import { arrowFor, formatDecimal, formatMoney, formatPercent, formatTime, signOf } from "@/lib/format";

const HEIGHT = 220;
const PAD = { top: 12, right: 8, bottom: 28, left: 52 };

/** Evenly spaced round ticks (in % since the start) covering [low, high]. */
function niceTicks(low: number, high: number): number[] {
  const raw = Math.max(high - low, 0.5) / 3;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 2.5, 5, 10].find((m) => m * power >= raw) ?? 10) * power;
  const ticks: number[] = [];
  const top = Math.ceil(high / step - 1e-9) * step;
  for (let t = Math.floor(low / step + 1e-9) * step; t <= top + step * 1e-9; t += step) {
    ticks.push(Math.round(t * 1000) / 1000);
  }
  return ticks;
}

function tickLabel(pct: number): string {
  const text = formatDecimal(pct.toFixed(2), Number.isInteger(pct) ? 0 : 1, true);
  return `${text} %`;
}

/** Change since the start, from a series rebased to 100, as a decimal string. */
function sinceStart(value: string): string {
  const cents = Math.round(Number(value) * 100) - 10000;
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

function formatDay(day: string): string {
  return new Intl.DateTimeFormat("sv-SE", { day: "numeric", month: "short", timeZone: "UTC" }).format(
    new Date(`${day}T12:00:00Z`),
  );
}

function Pct({ value }: { value: string }) {
  const sign = signOf(value);
  return (
    <span className="change" data-sign={sign}>
      <span aria-hidden="true">{arrowFor(sign)}</span> {formatPercent(value)}
    </span>
  );
}

function Chart({ comparison, indexName }: { comparison: Comparison; indexName: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const [WIDTH, setWidth] = useState(640);
  const area = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = area.current;
    if (element === null) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry !== undefined) setWidth(Math.max(240, Math.round(entry.contentRect.width)));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const points = comparison.points;
  const values = points.flatMap((p) => [Number(p.jarvis) - 100, Number(p.index) - 100]);
  const ticks = niceTicks(Math.min(0, ...values), Math.max(0, ...values));
  const min = 100 + (ticks[0] ?? 0);
  const max = 100 + (ticks[ticks.length - 1] ?? 1);
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => PAD.top + ((max - v) / (max - min)) * innerH;
  const path = (key: "jarvis" | "index") =>
    points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(Number(p[key])).toFixed(1)}`).join(" ");

  const onMove = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const at = ((event.clientX - box.left) / box.width) * WIDTH;
    const i = Math.round(((at - PAD.left) / innerW) * (points.length - 1));
    setHover(Math.min(points.length - 1, Math.max(0, i)));
  };
  const shown = hover !== null ? points[hover] : undefined;
  const last = points.length - 1;

  return (
    <figure className="chart">
      <ul className="legend" aria-label="Förklaring">
        <li>
          <span className="swatch" data-series="jarvis" aria-hidden="true" /> Jarvis
        </li>
        <li>
          <span className="swatch" data-series="index" aria-hidden="true" /> {indexName}
        </li>
      </ul>
      <div className="chart-area" ref={area}>
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`Utveckling sedan ${formatDay(comparison.start)}: Jarvis ${formatPercent(comparison.jarvis_pct)}, ${indexName} ${formatPercent(comparison.index_pct)}.`}
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line
                className={t === 0 ? "grid base" : "grid"}
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={y(100 + t)}
                y2={y(100 + t)}
              />
              <text className="tick" x={PAD.left - 8} y={y(100 + t) + 4} textAnchor="end">
                {tickLabel(t)}
              </text>
            </g>
          ))}
          <text className="tick" x={PAD.left} y={HEIGHT - 8}>
            {formatDay(points[0]?.day ?? comparison.start)}
          </text>
          <text className="tick" x={WIDTH - PAD.right} y={HEIGHT - 8} textAnchor="end">
            {formatDay(points[last]?.day ?? comparison.start)}
          </text>
          <path className="series" data-series="index" d={path("index")} />
          <path className="series" data-series="jarvis" d={path("jarvis")} />
          {shown !== undefined && hover !== null && (
            <g>
              <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={HEIGHT - PAD.bottom} />
              <circle className="marker" data-series="index" cx={x(hover)} cy={y(Number(shown.index))} r={4} />
              <circle className="marker" data-series="jarvis" cx={x(hover)} cy={y(Number(shown.jarvis))} r={4} />
            </g>
          )}
        </svg>
        {shown !== undefined && hover !== null && (
          <div
            className="tooltip"
            style={{ left: `${(x(hover) / WIDTH) * 100}%` }}
            data-side={hover > last / 2 ? "left" : "right"}
          >
            <div className="caption">{formatDay(shown.day)}</div>
            <div>Jarvis {formatPercent(sinceStart(shown.jarvis))}</div>
            <div>
              {indexName} {formatPercent(sinceStart(shown.index))}
            </div>
          </div>
        )}
      </div>
      <details className="table-view">
        <summary>Visa som tabell</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Dag</th>
              <th scope="col">Jarvis</th>
              <th scope="col">{indexName}</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.day}>
                <td>{formatDay(p.day)}</td>
                <td>{formatPercent(sinceStart(p.jarvis))}</td>
                <td>{formatPercent(sinceStart(p.index))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

/** The economics line on the home screen; the details are one tap away. */
export function EconomicsCard({ data }: { data: EconomicsData }) {
  return (
    <section className="card" aria-labelledby="economics-h">
      <h2 id="economics-h" className="label">Ekonomi</h2>
      <Link className="link-row" href="/ekonomi">
        <span className="status-line">{data.verdict_sv}</span>
        <span className="secondary" aria-hidden="true">›</span>
      </Link>
    </section>
  );
}

export function Economics() {
  const query = useQuery({ queryKey: ["economics"], queryFn: api.economics });
  return (
    <div className="page">
      <Link className="back" href="/">
        ‹ Hem
      </Link>
      <h1 className="large-title">Ekonomi</h1>
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
        <EconomicsDetails data={query.data} />
      )}
    </div>
  );
}

function EconomicsDetails({ data }: { data: EconomicsData }) {
  const base = data.base_currency;
  const c = data.comparison;
  return (
    <div className="columns">
      <div className="column">
        <section className="card" aria-labelledby="eco-compare-h">
          <h2 id="eco-compare-h" className="label">Jarvis mot indexfonden</h2>
          <p className="status-line" role="status">
            {data.verdict_sv}
          </p>
          {c !== null ? (
            <>
              <ul className="list facts">
                <li className="row">
                  <span>Jarvis sedan {formatDay(c.start)}</span>
                  <Pct value={c.jarvis_pct} />
                </li>
                <li className="row">
                  <span>{data.index_name_sv}</span>
                  <Pct value={c.index_pct} />
                </li>
                <li className="row">
                  <span>Skillnad</span>
                  <span>
                    {formatDecimal(c.difference_pct, 2, true)} procentenheter
                  </span>
                </li>
              </ul>
              <Chart comparison={c} indexName={data.index_name_sv} />
              <p className="caption">
                Jarvis räknas efter avgifter, utan insättningar och uttag. Indexfonden räknas i
                kronor med dagens växelkurs. {c.days} handelsdagar.
              </p>
            </>
          ) : (
            <p className="secondary">
              Grafen visas när jag har följt både kontot och indexfonden i minst två handelsdagar.
            </p>
          )}
        </section>
      </div>
      <div className="column">
        <section className="card" aria-labelledby="eco-costs-h">
          <h2 id="eco-costs-h" className="label">Fasta kostnader</h2>
          <ul className="list facts">
            {data.monthly_costs.map((cost) => (
              <li className="row" key={cost.name_sv}>
                <span>{cost.name_sv}</span>
                <span>{formatMoney(cost.monthly, base)}/mån</span>
              </li>
            ))}
            <li className="row">
              <span className="headline">Break-even</span>
              <span className="headline">
                {data.break_even_pct !== null ? `${formatDecimal(data.break_even_pct)} % per år` : "–"}
              </span>
            </li>
          </ul>
          <p className={data.break_even_warning ? "status-line" : "caption"} data-tone={data.break_even_warning ? "warning" : "calm"}>
            {data.break_even_warning
              ? `Kostnaderna kräver mer än ${formatDecimal(String(data.break_even_limit_pct), 1)} % per år bara för att gå jämnt ut. Billigare data eller färre marknader skulle hjälpa.`
              : data.break_even_pct !== null
                ? "Så mycket måste jag tjäna per år bara för att täcka de fasta kostnaderna."
                : "Break-even räknas när jag vet hur stort kapitalet är."}
          </p>
        </section>
        <section className="card" aria-labelledby="eco-tax-h">
          <h2 id="eco-tax-h" className="label">ISK-skatt</h2>
          <p className="explanation">{data.tax_sv}</p>
        </section>
        <section className="card" aria-labelledby="eco-fees-h">
          <h2 id="eco-fees-h" className="label">Courtage hittills</h2>
          {data.commissions.length === 0 ? (
            <p className="secondary">Inga avgifter ännu.</p>
          ) : (
            <ul className="list facts">
              {data.commissions.map((fee) => (
                <li className="row" key={fee.currency}>
                  <span>{fee.currency === base ? "Kronor" : fee.currency}</span>
                  <span>{formatMoney(fee.amount, fee.currency)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <p className="caption footer">Uppdaterad {formatTime(data.as_of)}</p>
      </div>
    </div>
  );
}
