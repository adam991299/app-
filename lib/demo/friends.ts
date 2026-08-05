import { getDemoPuzzleForDate, getDemoQuestionForDate } from './content';
import { seededBool, seededInt } from './prng';
import type { FriendActivityRow, WeeklyLeaderboardRow } from '@/types/database';

export interface DemoFriend {
  id: string;
  display_name: string;
  avatar_emoji: string;
  avatar_color: string;
  invite_code: string;
  base_streak: number;
}

/** Canned friends already connected in demo mode, so Friends/Leaderboard/Home aren't empty. */
export const DEMO_FRIENDS: DemoFriend[] = [
  { id: 'demo-friend-anna', display_name: 'Anna', avatar_emoji: '🦊', avatar_color: '#E4572E', invite_code: 'ANNA42', base_streak: 12 },
  { id: 'demo-friend-oskar', display_name: 'Oskar', avatar_emoji: '🐻', avatar_color: '#2A9D8F', invite_code: 'OSKAR7', base_streak: 5 },
  { id: 'demo-friend-elin', display_name: 'Elin', avatar_emoji: '🦋', avatar_color: '#D68A1E', invite_code: 'ELIN99', base_streak: 21 },
  { id: 'demo-friend-marcus', display_name: 'Marcus', avatar_emoji: '🐢', avatar_color: '#8A7D6B', invite_code: 'MRKS03', base_streak: 2 },
];

export function findDemoFriendByCode(code: string): DemoFriend | null {
  const upper = code.trim().toUpperCase();
  return DEMO_FRIENDS.find((f) => f.invite_code === upper) ?? null;
}

export function findDemoFriendById(id: string): DemoFriend | null {
  return DEMO_FRIENDS.find((f) => f.id === id) ?? null;
}

interface FriendDayResult {
  questionSolved: boolean;
  questionGuessCount: number;
  questionTimeSeconds: number;
  questionScore: number;
  puzzleSolved: boolean;
  puzzleTimeSeconds: number;
  puzzleScore: number;
}

/** Deterministically "plays" a friend's day so activity/leaderboard/head-to-head stay
 * consistent for the same friend + date across the whole app. */
export function simulateFriendDay(friend: DemoFriend, date: string): FriendDayResult {
  const key = `${friend.id}:${date}`;
  const questionSolved = seededBool(`${key}:qs`, 0.85);
  const questionGuessCount = questionSolved ? seededInt(`${key}:qg`, 1, 3) : 3;
  const questionTimeSeconds = seededInt(`${key}:qt`, 8, 90);
  const questionScore = questionSolved ? Math.max(1000 - (questionGuessCount - 1) * 300, 100) : 0;

  const puzzleSolved = seededBool(`${key}:ps`, 0.9);
  const puzzleTimeSeconds = seededInt(`${key}:pt`, 15, 240);
  const puzzleScore = puzzleSolved ? Math.max(1000 - Math.floor(puzzleTimeSeconds / 10) * 50, 100) : 0;

  return {
    questionSolved,
    questionGuessCount,
    questionTimeSeconds,
    questionScore,
    puzzleSolved,
    puzzleTimeSeconds,
    puzzleScore,
  };
}

function startOfWeekUTC(date: Date): Date {
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = d.getUTCDay(); // 0 = Sunday
  const diff = (day + 6) % 7; // days since Monday
  d.setUTCDate(d.getUTCDate() - diff);
  return d;
}

function datesForCurrentWeek(now: Date): string[] {
  const start = startOfWeekUTC(now);
  const dates: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setUTCDate(start.getUTCDate() + i);
    if (d.getTime() > now.getTime()) break;
    dates.push(d.toISOString().slice(0, 10));
  }
  return dates;
}

export function demoWeeklyLeaderboardForFriends(
  now: Date,
  friendTotals: { total_score: number; total_time_seconds: number }
): Omit<WeeklyLeaderboardRow, 'user_id' | 'display_name' | 'avatar_emoji' | 'avatar_color' | 'rank'>[] {
  const dates = datesForCurrentWeek(now);
  return DEMO_FRIENDS.map((friend) => {
    let total_score = 0;
    let total_time_seconds = 0;
    let questions_solved = 0;
    let puzzles_solved = 0;
    for (const date of dates) {
      const r = simulateFriendDay(friend, date);
      total_score += r.questionScore + r.puzzleScore;
      total_time_seconds += r.questionTimeSeconds + r.puzzleTimeSeconds;
      if (r.questionSolved) questions_solved += 1;
      if (r.puzzleSolved) puzzles_solved += 1;
    }
    return { total_score, total_time_seconds, questions_solved, puzzles_solved };
  });
}

export function demoFriendActivityFeed(now: Date, limit: number): FriendActivityRow[] {
  const today = now.toISOString().slice(0, 10);
  const yesterday = new Date(now.getTime() - 86400000).toISOString().slice(0, 10);
  const entries: FriendActivityRow[] = [];

  for (const friend of DEMO_FRIENDS) {
    for (const date of [today, yesterday]) {
      const r = simulateFriendDay(friend, date);
      const question = getDemoQuestionForDate(date);
      const puzzle = getDemoPuzzleForDate(date);
      const completedAt = `${date}T${String(seededInt(`${friend.id}:${date}:h`, 7, 22)).padStart(2, '0')}:${String(
        seededInt(`${friend.id}:${date}:m`, 0, 59)
      ).padStart(2, '0')}:00.000Z`;

      entries.push({
        user_id: friend.id,
        display_name: friend.display_name,
        avatar_emoji: friend.avatar_emoji,
        avatar_color: friend.avatar_color,
        kind: 'puzzle',
        solved: r.puzzleSolved,
        guess_count: null,
        time_seconds: r.puzzleTimeSeconds,
        completed_at: completedAt,
      });
      entries.push({
        user_id: friend.id,
        display_name: friend.display_name,
        avatar_emoji: friend.avatar_emoji,
        avatar_color: friend.avatar_color,
        kind: 'question',
        solved: r.questionSolved,
        guess_count: r.questionGuessCount,
        time_seconds: r.questionTimeSeconds,
        completed_at: completedAt,
      });
      void puzzle;
      void question;
    }
  }

  return entries
    .sort((a, b) => (a.completed_at < b.completed_at ? 1 : -1))
    .slice(0, limit);
}
