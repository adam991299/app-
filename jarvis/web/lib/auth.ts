// Passkey login and protected actions. The server checks everything; this only carries
// the WebAuthn ceremonies between the browser and /api.
import { startAuthentication, startRegistration } from "@simplewebauthn/browser";

const TIMEOUT_MS = 8000;

export interface AuthState {
  registered: boolean;
  logged_in: boolean;
}

/** An error whose message is already Swedish and safe to show. */
export class ActionError extends Error {}

async function post<T>(path: string, body: unknown = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: "POST",
      credentials: "same-origin",
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { "content-type": "application/json", accept: "application/json", "x-jarvis": "1" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ActionError("Jag når inte servern just nu.");
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;
    throw new ActionError(typeof detail === "string" ? detail : "Något gick fel. Försök igen.");
  }
  return data as T;
}

async function ceremony<T>(run: () => Promise<T>): Promise<T> {
  try {
    return await run();
  } catch (error) {
    if (error instanceof ActionError) throw error;
    throw new ActionError("Passkeyn avbröts eller är inte tillgänglig på den här enheten.");
  }
}

export async function authState(): Promise<AuthState> {
  const response = await fetch("/api/auth/state", {
    credentials: "same-origin",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) throw new ActionError("Jag når inte servern just nu.");
  return (await response.json()) as AuthState;
}

export async function registerPasskey(setupCode: string): Promise<void> {
  const optionsJSON = await post<Parameters<typeof startRegistration>[0]["optionsJSON"]>(
    "/auth/register/options",
    { setup_code: setupCode },
  );
  const credential = await ceremony(() => startRegistration({ optionsJSON }));
  await post("/auth/register/verify", { credential });
}

export async function login(): Promise<void> {
  const optionsJSON = await post<Parameters<typeof startAuthentication>[0]["optionsJSON"]>(
    "/auth/login/options",
  );
  const credential = await ceremony(() => startAuthentication({ optionsJSON }));
  await post("/auth/login/verify", { credential });
}

export async function logout(): Promise<void> {
  await post("/auth/logout");
}

/** Asks for Face ID / the passkey bound to exactly this action and values, then runs it. */
async function confirmed(
  action: "deposit" | "risk_profile" | "control" | "budget" | "trading_mode",
  payload: Record<string, string>,
  path: string,
): Promise<string> {
  const optionsJSON = await post<Parameters<typeof startAuthentication>[0]["optionsJSON"]>(
    "/actions/options",
    { action, payload },
  );
  const credential = await ceremony(() => startAuthentication({ optionsJSON }));
  const result = await post<{ message_sv: string }>(path, { ...payload, credential });
  return result.message_sv;
}

export function registerCashFlow(amount: string, note: string): Promise<string> {
  return confirmed("deposit", { amount, note }, "/actions/deposit");
}

export function setRiskProfile(profile: "cautious" | "balanced" | "offensive"): Promise<string> {
  return confirmed("risk_profile", { profile }, "/actions/risk-profile");
}

export interface ControlsState {
  mode: "paper" | "live";
  paused: boolean;
  kill_switch_engaged: boolean;
  budget_pct: string;
  pending_budget_pct: string | null;
  pending_budget_from: string | null;
}

export async function controlsState(): Promise<ControlsState> {
  const response = await fetch("/api/controls", {
    credentials: "same-origin",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) throw new ActionError("Jag når inte servern just nu.");
  return (await response.json()) as ControlsState;
}

export type Command = "pause" | "resume" | "kill_switch" | "reset_kill_switch";

export function sendControl(command: Command): Promise<string> {
  return confirmed("control", { command }, "/actions/control");
}

export function setBudget(pct: string): Promise<string> {
  return confirmed("budget", { pct }, "/actions/budget");
}

export function setTradingMode(mode: "paper" | "live", phrase = "", budgetPct = "10"): Promise<string> {
  return confirmed("trading_mode", { mode, phrase, budget_pct: budgetPct }, "/actions/trading-mode");
}
