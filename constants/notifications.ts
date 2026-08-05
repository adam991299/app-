/**
 * All daily-reminder copy lives here in one place, on purpose — the brief calls out
 * wanting a single spot to A/B test notification copy later without hunting through
 * scheduling code.
 */
export const DAILY_REMINDER_COPY = {
  title: "Today's puzzle is ready 🧩",
  body: 'One question, one puzzle, thirty seconds. Keep your streak alive.',
} as const;

export const STREAK_AT_RISK_COPY = {
  title: 'Your streak is about to reset 🔥',
  body: "You haven't played today yet — don't lose your streak now.",
} as const;

export const DEFAULT_NOTIFICATION_HOUR = 9;
export const DEFAULT_NOTIFICATION_MINUTE = 0;

export const DAILY_REMINDER_IDENTIFIER = 'narmast-daily-reminder';
