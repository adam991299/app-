"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/api";
import { ActionError, controlsState, sendControl, setBudget, setTradingMode, type Command } from "@/lib/auth";
import { formatDateTime, formatDecimal, formatMoney, formatPercent } from "@/lib/format";

export const LIVE_PHRASE = "JAG FÖRSTÅR RISKEN";
const STEPS = [10, 25, 50, 75, 100];

/** Per-trade limits of each risk level (risk/profiles.py, D24): [max position %, risk %]. */
const LIMITS: Record<string, [number, number]> = {
  Försiktig: [7.5, 0.5],
  Balanserad: [10, 0.75],
  Offensiv: [20, 1.5],
};

function money(value: number): string {
  return formatMoney(value.toFixed(2), "SEK");
}

function useRun() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: "calm" | "warning" } | null>(null);
  const queries = useQueryClient();
  const run = async (action: () => Promise<string>) => {
    setBusy(true);
    setMessage(null);
    try {
      setMessage({ text: await action(), tone: "calm" });
      await queries.invalidateQueries();
    } catch (error) {
      setMessage({
        text: error instanceof ActionError ? error.message : "Något gick fel. Försök igen.",
        tone: "warning",
      });
    } finally {
      setBusy(false);
    }
  };
  return { busy, message, run };
}

function Message({ message }: { message: { text: string; tone: string } | null }) {
  if (message === null) return null;
  return (
    <p className="status-line" data-tone={message.tone} role="status">
      {message.text}
    </p>
  );
}

export function TradingControls() {
  const state = useQuery({ queryKey: ["controls"], queryFn: controlsState });
  const { busy, message, run } = useRun();
  const button = (command: Command, label: string, tone = "") => (
    <button
      className={`button ${tone}`}
      type="button"
      disabled={busy}
      onClick={() => void run(() => sendControl(command))}
    >
      {label}
    </button>
  );
  const s = state.data;
  return (
    <section className="card" aria-labelledby="ctl-h">
      <h2 id="ctl-h" className="label">Handeln</h2>
      {s === undefined ? (
        <p className="secondary">Läser läget …</p>
      ) : (
        <>
          <p className="status-line" data-tone={s.kill_switch_engaged || s.paused ? "warning" : "calm"}>
            {s.kill_switch_engaged
              ? "Kill switch är aktiv. Inga nya affärer tas."
              : s.paused
                ? "Handeln är pausad."
                : "Handeln är igång."}
          </p>
          <div className="button-row">
            {s.kill_switch_engaged
              ? button("reset_kill_switch", "Starta handeln igen")
              : s.paused
                ? button("resume", "Återuppta")
                : button("pause", "Pausa", "quiet")}
            {!s.kill_switch_engaged && button("kill_switch", "Kill switch", "danger")}
          </div>
          <p className="caption">
            Paus och kill switch stoppar nya affärer. Öppna positioner skyddas av stoppordrarna
            hos mäklaren.
          </p>
        </>
      )}
      <Message message={message?.tone === "warning" ? message : null} />
    </section>
  );
}

export function BudgetControl({ riskLevel }: { riskLevel: string | undefined }) {
  const state = useQuery({ queryKey: ["controls"], queryFn: controlsState });
  const portfolio = useQuery({ queryKey: ["portfolio"], queryFn: api.portfolio });
  const current = state.data !== undefined ? Number(state.data.budget_pct) : undefined;
  const [chosen, setChosen] = useState<number | null>(null);
  const { busy, message, run } = useRun();
  const pct = chosen ?? current ?? 100;
  const capital = portfolio.data?.net_liquidation != null ? Number(portfolio.data.net_liquidation) : null;
  const [maxPos, riskPct] = LIMITS[riskLevel ?? "Balanserad"] ?? [10, 0.75];
  const managed = capital !== null ? (capital * pct) / 100 : null;
  const raising = current !== undefined && pct > current;
  const pending = state.data?.pending_budget_pct ?? null;

  return (
    <section className="card" aria-labelledby="budget-h">
      <h2 id="budget-h" className="label">Jarvis budget</h2>
      <p className="explanation">Hur stor del av kontot Jarvis får förvalta.</p>
      <p className="big-value">
        {pct} %{managed !== null && <span className="secondary"> · {money(managed)}</span>}
      </p>
      <input
        className="slider"
        type="range"
        min={1}
        max={100}
        step={1}
        value={pct}
        list="budget-steps"
        aria-label="Jarvis budget i procent"
        onChange={(e) => {
          const raw = Number(e.target.value);
          const near = STEPS.find((step) => Math.abs(step - raw) <= 2);
          setChosen(near ?? raw);
        }}
      />
      <datalist id="budget-steps">
        {STEPS.map((step) => (
          <option key={step} value={step} label={`${step} %`} />
        ))}
      </datalist>
      <div className="steps" aria-hidden="true">
        {STEPS.map((step) => (
          <span key={step}>{step} %</span>
        ))}
      </div>
      {managed !== null ? (
        <ul className="list facts">
          <li className="row">
            <span>Max per affär</span>
            <span>ca {money((managed * maxPos) / 100)}</span>
          </li>
          <li className="row">
            <span>Om stoppen slår</span>
            <span>ca −{money((managed * riskPct) / 100)}</span>
          </li>
        </ul>
      ) : (
        <p className="caption">Beloppen visas när jag vet hur stort kontot är.</p>
      )}
      <p className="caption">
        Med risknivån {riskLevel ?? "Balanserad"}. Stresstester och förväntat spann visas när det
        finns resultat att räkna på.
      </p>
      {pending !== null && state.data?.pending_budget_from && (
        <p className="caption">
          Väntande höjning till {pending} % från {formatDateTime(state.data.pending_budget_from)}.
        </p>
      )}
      {raising && (
        <p className="status-line" data-tone="warning">
          En höjning gäller från i morgon{pct > (current ?? 0) * 2 ? ", och mer än en fördubbling tidigast om 24 timmar" : ""}.
        </p>
      )}
      <button
        className="button"
        type="button"
        disabled={busy || current === undefined || pct === current}
        onClick={() => void run(() => setBudget(String(pct)))}
      >
        Bekräfta {pct} % med passkey
      </button>
      <Message message={message} />
    </section>
  );
}

export function LiveTrading({ riskLevel }: { riskLevel: string | undefined }) {
  const state = useQuery({ queryKey: ["controls"], queryFn: controlsState });
  const economics = useQuery({ queryKey: ["economics"], queryFn: api.economics });
  const [open, setOpen] = useState(false);
  const [phrase, setPhrase] = useState("");
  const [budget, setBudgetText] = useState("10");
  const { busy, message, run } = useRun();
  const mode = state.data?.mode;
  const comparison = economics.data?.comparison ?? null;

  if (mode === "live") {
    return (
      <section className="card" aria-labelledby="live-h">
        <h2 id="live-h" className="label">Riktig handel</h2>
        <p className="status-line" data-tone="warning">Riktig handel är vald.</p>
        <button
          className="button quiet"
          type="button"
          disabled={busy}
          onClick={() => void run(() => setTradingMode("paper"))}
        >
          Tillbaka till papper
        </button>
        <Message message={message} />
      </section>
    );
  }
  const budgetOk = /^\d{1,3}$/.test(budget) && Number(budget) >= 1 && Number(budget) <= 100;
  return (
    <section className="card" aria-labelledby="live-h">
      <h2 id="live-h" className="label">Riktig handel</h2>
      {!open ? (
        <>
          <p className="explanation">Jarvis handlar nu med papperspengar.</p>
          <button className="button quiet" type="button" onClick={() => setOpen(true)}>
            Aktivera riktig handel
          </button>
        </>
      ) : (
        <div className="form">
          <p className="explanation">
            Riktig handel betyder att Jarvis köper och säljer med dina egna pengar. Du kan
            förlora pengar, och tidigare resultat lovar ingenting.
          </p>
          <ul className="list facts">
            <li className="row">
              <span>Risknivå</span>
              <span>{riskLevel ?? "–"}</span>
            </li>
            <li className="row">
              <span>Pappersresultat</span>
              {comparison !== null ? (
                <span>
                  {formatPercent(comparison.jarvis_pct)} på {comparison.days} dagar
                </span>
              ) : (
                <span>Inget ännu</span>
              )}
            </li>
            <li className="row">
              <span>Mot indexfonden</span>
              <span>
                {comparison !== null
                  ? `${formatDecimal(comparison.difference_pct, 2, true)} procentenheter`
                  : "–"}
              </span>
            </li>
          </ul>
          <p className="caption">
            Jarvis handlar först när gatewayn är inloggad på ditt riktiga konto. Annars står
            handeln still, så att papper och riktiga pengar aldrig blandas ihop.
          </p>
          <label className="field">
            <span>Startbudget i procent av kontot (rekommenderat 10 %)</span>
            <input
              value={budget}
              onChange={(e) => setBudgetText(e.target.value.trim())}
              inputMode="numeric"
              aria-invalid={!budgetOk}
            />
          </label>
          <label className="field">
            <span>Skriv {LIVE_PHRASE}</span>
            <input
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <button
            className="button danger"
            type="button"
            disabled={busy || phrase !== LIVE_PHRASE || !budgetOk}
            onClick={() => void run(() => setTradingMode("live", phrase, budget))}
          >
            Slå på riktig handel med passkey
          </button>
          <button className="button quiet" type="button" onClick={() => setOpen(false)}>
            Avbryt
          </button>
        </div>
      )}
      <Message message={message} />
    </section>
  );
}
