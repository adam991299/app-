// Swedish number and time formatting. Decimal strings are rounded and grouped as text,
// never converted to floats, so amounts are shown exactly.

/** The timezone the app shows times in (spec §1.7: selectable later in settings). */
export const DISPLAY_TIMEZONE = "Europe/Stockholm";

const MINUS = "−";
const NBSP = " ";

export type Sign = "positive" | "negative" | "zero";

export function signOf(value: string): Sign {
  const trimmed = value.trim();
  if (/^[+-]?0*(\.0*)?$/.test(trimmed)) return "zero";
  return trimmed.startsWith("-") ? "negative" : "positive";
}

/** Rounds a decimal string half away from zero and formats it like "100 000,10". */
export function formatDecimal(value: string, decimals = 2, showPlus = false): string {
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
  if (!match) return value;
  const negative = match[1] === "-";
  const whole = match[2] ?? "0";
  const fraction = (match[3] ?? "").padEnd(decimals + 1, "0");
  let scaled = BigInt(whole + fraction.slice(0, decimals));
  if (Number(fraction[decimals]) >= 5) scaled += BigInt(1);
  const digits = scaled.toString().padStart(decimals + 1, "0");
  const intPart = digits.slice(0, digits.length - decimals).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  const fracPart = decimals > 0 ? `,${digits.slice(-decimals)}` : "";
  const isZero = scaled === BigInt(0);
  const prefix = isZero ? "" : negative ? MINUS : showPlus ? "+" : "";
  return `${prefix}${intPart}${fracPart}`;
}

export function formatMoney(value: string, currency: string, showPlus = false): string {
  const unit = currency === "SEK" ? "kr" : currency;
  return `${formatDecimal(value, 2, showPlus)}${NBSP}${unit}`;
}

export function formatPercent(value: string): string {
  return `${formatDecimal(value, 2, true)}${NBSP}%`;
}

export function arrowFor(sign: Sign): string {
  return sign === "positive" ? "▲" : sign === "negative" ? "▼" : "•";
}

export function formatTime(iso: string, timeZone = DISPLAY_TIMEZONE): string {
  return new Intl.DateTimeFormat("sv-SE", { hour: "2-digit", minute: "2-digit", timeZone }).format(
    new Date(iso),
  );
}

export function formatDateTime(iso: string, timeZone = DISPLAY_TIMEZONE): string {
  return new Intl.DateTimeFormat("sv-SE", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  }).format(new Date(iso));
}

export function greeting(now: Date, timeZone = DISPLAY_TIMEZONE): string {
  const hour = Number(
    new Intl.DateTimeFormat("sv-SE", { hour: "numeric", hourCycle: "h23", timeZone }).format(now),
  );
  if (hour >= 5 && hour < 10) return "God morgon, Adam.";
  if (hour >= 10 && hour < 18) return "God dag, Adam.";
  if (hour >= 18 && hour < 23) return "God kväll, Adam.";
  return "God natt, Adam.";
}
