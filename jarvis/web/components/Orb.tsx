import type { TradingState } from "@/lib/api";

export type OrbTone = "calm" | "waiting" | "dimmed" | "warning";

export function orbTone(state: TradingState, anyMarketOpen: boolean): OrbTone {
  if (state === "active") return anyMarketOpen ? "calm" : "waiting";
  if (state === "paused") return "dimmed";
  return "warning";
}

/** Jarvis's face (§9.1): colour and motion show the system state at a glance. */
export function Orb({ tone }: { tone: OrbTone }) {
  return (
    <div className="orb" data-tone={tone} aria-hidden="true">
      <div className="orb-core" />
    </div>
  );
}
