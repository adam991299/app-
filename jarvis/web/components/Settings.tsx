"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { BudgetControl, LiveTrading, TradingControls } from "@/components/Controls";
import { api } from "@/lib/api";
import {
  ActionError,
  authState,
  login,
  logout,
  registerCashFlow,
  registerPasskey,
  setRiskProfile,
} from "@/lib/auth";

type Profile = "cautious" | "balanced" | "offensive";

const PROFILES: { id: Profile; name: string; detail: string }[] = [
  { id: "cautious", name: "Försiktig", detail: "0,5 % risk per affär, högst 7,5 % i en aktie." },
  { id: "balanced", name: "Balanserad", detail: "0,75 % risk per affär, högst 10 % i en aktie." },
  { id: "offensive", name: "Offensiv", detail: "1,5 % risk per affär, högst 20 % i en aktie." },
];

/** "5 000,50" -> "5000.50"; null when it is not an amount with at most two decimals. */
export function parseAmount(text: string): string | null {
  const plain = text.replace(/[\s ]/g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(plain) || Number(plain) === 0) return null;
  return plain;
}

function useAction() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: "calm" | "warning" } | null>(null);
  const run = async (action: () => Promise<string | void>, done?: string) => {
    setBusy(true);
    setMessage(null);
    try {
      const text = await action();
      setMessage({ text: text ?? done ?? "Klart.", tone: "calm" });
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

function Setup({ onDone }: { onDone: () => void }) {
  const [code, setCode] = useState("");
  const { busy, message, run } = useAction();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      await registerPasskey(code.trim());
      onDone();
    }, "Passkeyn är skapad och du är inloggad.");
  };
  return (
    <section className="card" aria-labelledby="setup-h">
      <h2 id="setup-h" className="label">Skapa din passkey</h2>
      <p className="explanation">
        Första gången behövs engångskoden från serverns <code>.env</code>{" "}
        (raden <code>JARVIS_PASSKEY_SETUP_CODE</code>). Sedan loggar du in med Face ID.
      </p>
      <form className="form" onSubmit={submit}>
        <label className="field">
          <span>Engångskod</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            autoComplete="one-time-code"
            autoCapitalize="none"
            spellCheck={false}
            required
          />
        </label>
        <button className="button" type="submit" disabled={busy || code.trim() === ""}>
          Skapa passkey
        </button>
      </form>
      <Message message={message} />
    </section>
  );
}

function Login({ onDone }: { onDone: () => void }) {
  const { busy, message, run } = useAction();
  return (
    <section className="card" aria-labelledby="login-h">
      <h2 id="login-h" className="label">Logga in</h2>
      <p className="explanation">Ändringar kräver att du loggar in med din passkey.</p>
      <button
        className="button"
        type="button"
        disabled={busy}
        onClick={() =>
          void run(async () => {
            await login();
            onDone();
          }, "Du är inloggad.")
        }
      >
        Logga in med passkey
      </button>
      <Message message={message} />
    </section>
  );
}

function CashFlow() {
  const [direction, setDirection] = useState<"in" | "out">("in");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const { busy, message, run } = useAction();
  const queries = useQueryClient();
  const parsed = parseAmount(amount);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (parsed === null) return;
    const signed = direction === "in" ? parsed : `-${parsed}`;
    void run(async () => {
      const text = await registerCashFlow(signed, note.trim());
      setAmount("");
      setNote("");
      await queries.invalidateQueries();
      return text;
    });
  };
  return (
    <section className="card" aria-labelledby="cash-h">
      <h2 id="cash-h" className="label">Insättning eller uttag</h2>
      <p className="explanation">
        Registrera pengar du har satt in eller tagit ut hos IBKR, så räknas de inte som vinst
        eller förlust. Själva överföringen gör du hos IBKR.
      </p>
      <form className="form" onSubmit={submit}>
        <div className="segmented" role="radiogroup" aria-label="Typ">
          {(["in", "out"] as const).map((d) => (
            <button
              key={d}
              type="button"
              role="radio"
              aria-checked={direction === d}
              onClick={() => setDirection(d)}
            >
              {d === "in" ? "Insättning" : "Uttag"}
            </button>
          ))}
        </div>
        <label className="field">
          <span>Belopp i kronor</span>
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            placeholder="10 000"
            aria-invalid={amount !== "" && parsed === null}
            required
          />
        </label>
        <label className="field">
          <span>Anteckning (valfri)</span>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} />
        </label>
        <button className="button" type="submit" disabled={busy || parsed === null}>
          Bekräfta med passkey
        </button>
      </form>
      <Message message={message} />
    </section>
  );
}

function RiskLevel({ current }: { current: string | undefined }) {
  const { busy, message, run } = useAction();
  const queries = useQueryClient();
  return (
    <section className="card" aria-labelledby="risk-h">
      <h2 id="risk-h" className="label">Risknivå</h2>
      <p className="explanation">
        Nu: {current ?? "–"}. En sänkning gäller direkt, en höjning från i morgon.
      </p>
      <ul className="list">
        {PROFILES.map((p) => (
          <li key={p.id} className="row">
            <span>
              <span className="headline">{p.name}</span>
              <span className="caption block">{p.detail}</span>
            </span>
            <button
              className="button small"
              type="button"
              disabled={busy || current === p.name}
              onClick={() =>
                void run(async () => {
                  const text = await setRiskProfile(p.id);
                  await queries.invalidateQueries();
                  return text;
                })
              }
            >
              {current === p.name ? "Vald" : "Välj"}
            </button>
          </li>
        ))}
      </ul>
      <Message message={message} />
    </section>
  );
}

export function Settings() {
  const state = useQuery({ queryKey: ["auth"], queryFn: authState });
  const today = useQuery({ queryKey: ["today"], queryFn: api.today });
  const queries = useQueryClient();
  const refresh = () => void queries.invalidateQueries({ queryKey: ["auth"] });

  let body;
  if (state.isError && state.data === undefined) {
    body = (
      <div className="empty">
        <p>Jag når inte servern just nu.</p>
        <button className="button" type="button" onClick={() => void state.refetch()}>
          Försök igen
        </button>
      </div>
    );
  } else if (state.data === undefined) {
    body = <div className="skeleton skeleton-card" aria-busy="true" aria-label="Laddar" />;
  } else if (!state.data.registered) {
    body = <Setup onDone={refresh} />;
  } else if (!state.data.logged_in) {
    body = <Login onDone={refresh} />;
  } else {
    body = (
      <div className="columns">
        <div className="column">
          <TradingControls />
          <BudgetControl riskLevel={today.data?.risk_level_sv} />
          <CashFlow />
        </div>
        <div className="column">
          <RiskLevel current={today.data?.risk_level_sv} />
          <LiveTrading riskLevel={today.data?.risk_level_sv} />
          <button
            className="button quiet"
            type="button"
            onClick={() => void logout().finally(refresh)}
          >
            Logga ut
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Link className="back" href="/">
        ‹ Hem
      </Link>
      <h1 className="large-title">Inställningar</h1>
      {body}
    </div>
  );
}
