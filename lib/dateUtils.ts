/**
 * Content-day rules.
 *
 * Design decision (documented per the brief): the daily question and puzzle reset at a
 * fixed 00:00 UTC boundary, not local midnight. Every player worldwide gets the exact
 * same content on the exact same UTC calendar day — that's what makes the weekly
 * leaderboard, friend activity feed and head-to-head comparisons well-defined without
 * per-user timezone math. A player near the UTC dateline will see "today's" content
 * change at a time that isn't their local midnight; the countdown on the home screen
 * always counts down to that real boundary so it's never a surprise.
 */

/** Today's content date, as YYYY-MM-DD in UTC. This is the key used against
 * daily_questions.date / daily_puzzles.date. */
export function getContentDateUTC(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

/** Milliseconds until the next 00:00 UTC boundary. */
export function msUntilNextContentDay(now: Date = new Date()): number {
  const next = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0, 0)
  );
  return next.getTime() - now.getTime();
}

export function formatCountdown(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/** Friendly "today" label for headers, in the device's local calendar/format. */
export function formatFriendlyDate(date: Date = new Date()): string {
  return date.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
}

export function isSameContentDay(dateA: string, dateB: string): boolean {
  return dateA === dateB;
}
