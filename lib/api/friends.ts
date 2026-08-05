import { getContentDateUTC } from '@/lib/dateUtils';
import {
  demoFriendActivityFeed,
  demoWeeklyLeaderboardForFriends,
  DEMO_FRIENDS,
  findDemoFriendByCode,
  findDemoFriendById,
  simulateFriendDay,
} from '@/lib/demo/friends';
import { getDemoState, updateDemoState } from '@/lib/demo/store';
import { isSupabaseConfigured } from '@/lib/env';
import { supabase } from '@/lib/supabase';
import type { FindUserByCodeRow, FriendActivityRow, UserRow, WeeklyLeaderboardRow } from '@/types/database';

export interface FriendSummary {
  id: string;
  display_name: string;
  avatar_emoji: string;
  avatar_color: string;
  current_streak: number;
  longest_streak: number;
}

export async function findUserByCode(code: string): Promise<FindUserByCodeRow | null> {
  if (!isSupabaseConfigured) {
    const friend = findDemoFriendByCode(code);
    if (!friend) return null;
    return { id: friend.id, display_name: friend.display_name, avatar_emoji: friend.avatar_emoji, avatar_color: friend.avatar_color };
  }
  const { data, error } = await supabase.rpc('find_user_by_invite_code', { p_code: code });
  if (error) throw error;
  return data?.[0] ?? null;
}

export async function addFriendByCode(code: string): Promise<UserRow> {
  if (!isSupabaseConfigured) {
    const friend = findDemoFriendByCode(code);
    if (!friend) throw new Error('No player found for that code.');
    await updateDemoState((s) => {
      if (!s.friendIds.includes(friend.id)) s.friendIds.push(friend.id);
    });
    return {
      id: friend.id,
      display_name: friend.display_name,
      avatar_emoji: friend.avatar_emoji,
      avatar_color: friend.avatar_color,
      avatar_url: null,
      invite_code: friend.invite_code,
      notification_time: '09:00:00',
      notifications_enabled: true,
      timezone: 'UTC',
      is_premium: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }
  const { data, error } = await supabase.rpc('add_friend_by_code', { p_code: code });
  if (error) throw error;
  return data as unknown as UserRow;
}

export async function listFriends(): Promise<FriendSummary[]> {
  if (!isSupabaseConfigured) {
    const state = await getDemoState();
    return state.friendIds
      .map((id) => findDemoFriendById(id))
      .filter((f): f is NonNullable<typeof f> => Boolean(f))
      .map((f) => ({
        id: f.id,
        display_name: f.display_name,
        avatar_emoji: f.avatar_emoji,
        avatar_color: f.avatar_color,
        current_streak: f.base_streak,
        longest_streak: f.base_streak + 3,
      }));
  }

  const { data: ids, error: idsError } = await supabase.rpc('my_friend_ids');
  if (idsError) throw idsError;
  const friendIds = (ids ?? []) as unknown as string[];
  if (friendIds.length === 0) return [];

  const [{ data: users }, { data: streaks }] = await Promise.all([
    supabase.from('users').select('id,display_name,avatar_emoji,avatar_color').in('id', friendIds),
    supabase.from('streaks').select('user_id,current_streak,longest_streak').in('user_id', friendIds),
  ]);

  const streakByUser = new Map((streaks ?? []).map((s) => [s.user_id, s]));
  return (users ?? []).map((u) => ({
    id: u.id,
    display_name: u.display_name,
    avatar_emoji: u.avatar_emoji,
    avatar_color: u.avatar_color,
    current_streak: streakByUser.get(u.id)?.current_streak ?? 0,
    longest_streak: streakByUser.get(u.id)?.longest_streak ?? 0,
  }));
}

export async function getWeeklyLeaderboard(): Promise<WeeklyLeaderboardRow[]> {
  if (!isSupabaseConfigured) {
    const state = await getDemoState();
    const now = new Date();
    const myTotals = Object.values(state.questionAttempts).reduce(
      (acc, a) => {
        acc.score += a.score;
        acc.time += a.time_seconds;
        return acc;
      },
      { score: 0, time: 0 }
    );
    Object.values(state.puzzleAttempts).forEach((a) => {
      myTotals.score += a.score;
      myTotals.time += a.time_seconds;
    });

    const friendTotals = state.friendIds
      .map((id) => findDemoFriendById(id))
      .filter((f): f is NonNullable<typeof f> => Boolean(f));

    const allFriendWeeklyTotals = demoWeeklyLeaderboardForFriends(now, { total_score: 0, total_time_seconds: 0 });

    const rows: Omit<WeeklyLeaderboardRow, 'rank'>[] = [
      {
        user_id: 'demo-me',
        display_name: state.profile?.display_name ?? 'You',
        avatar_emoji: state.profile?.avatar_emoji ?? '🙂',
        avatar_color: state.profile?.avatar_color ?? '#E4572E',
        total_score: myTotals.score,
        total_time_seconds: myTotals.time,
        questions_solved: Object.values(state.questionAttempts).filter((a) => a.solved).length,
        puzzles_solved: Object.values(state.puzzleAttempts).filter((a) => a.solved).length,
      },
      ...friendTotals.map((friend) => {
        const totals = allFriendWeeklyTotals[DEMO_FRIENDS.findIndex((f) => f.id === friend.id)];
        return {
          user_id: friend.id,
          display_name: friend.display_name,
          avatar_emoji: friend.avatar_emoji,
          avatar_color: friend.avatar_color,
          ...totals,
        };
      }),
    ];

    const sorted = rows.sort(
      (a, b) => b.total_score - a.total_score || a.total_time_seconds - b.total_time_seconds
    );
    return sorted.map((row, index) => ({ ...row, rank: index + 1 }));
  }

  const { data, error } = await supabase.rpc('weekly_leaderboard');
  if (error) throw error;
  return (data ?? []) as unknown as WeeklyLeaderboardRow[];
}

export async function getFriendActivityFeed(limit = 20): Promise<FriendActivityRow[]> {
  if (!isSupabaseConfigured) {
    const state = await getDemoState();
    const all = demoFriendActivityFeed(new Date(), 40);
    return all.filter((entry) => state.friendIds.includes(entry.user_id)).slice(0, limit);
  }
  const { data, error } = await supabase.rpc('friend_activity_feed', { p_limit: limit });
  if (error) throw error;
  return (data ?? []) as unknown as FriendActivityRow[];
}

export interface HeadToHeadDay {
  date: string;
  me: { questionSolved: boolean; questionGuesses: number; puzzleSolved: boolean; puzzleTimeSeconds: number };
  friend: { questionSolved: boolean; questionGuesses: number; puzzleSolved: boolean; puzzleTimeSeconds: number };
}

export async function getHeadToHead(friendId: string, days = 7): Promise<HeadToHeadDay[]> {
  const today = getContentDateUTC();
  const dates: string[] = [];
  for (let i = 0; i < days; i++) {
    const d = new Date(new Date(`${today}T00:00:00Z`).getTime() - i * 86400000);
    dates.push(d.toISOString().slice(0, 10));
  }

  if (!isSupabaseConfigured) {
    const state = await getDemoState();
    const friend = findDemoFriendById(friendId);
    if (!friend) return [];
    return dates.map((date) => {
      const myQuestion = Object.values(state.questionAttempts).find((a) => a.question_id === `q-${date}`);
      const myPuzzle = Object.values(state.puzzleAttempts).find((a) => a.puzzle_id === `p-${date}`);
      const r = simulateFriendDay(friend, date);
      return {
        date,
        me: {
          questionSolved: myQuestion?.solved ?? false,
          questionGuesses: myQuestion?.guess_count ?? 0,
          puzzleSolved: myPuzzle?.solved ?? false,
          puzzleTimeSeconds: myPuzzle?.time_seconds ?? 0,
        },
        friend: {
          questionSolved: r.questionSolved,
          questionGuesses: r.questionGuessCount,
          puzzleSolved: r.puzzleSolved,
          puzzleTimeSeconds: r.puzzleTimeSeconds,
        },
      };
    });
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return [];

  const [{ data: myQ }, { data: myP }, { data: friendQ }, { data: friendP }, { data: questions }, { data: puzzles }] =
    await Promise.all([
      supabase.from('question_attempts').select('*').eq('user_id', user.id),
      supabase.from('puzzle_attempts').select('*').eq('user_id', user.id),
      supabase.from('question_attempts').select('*').eq('user_id', friendId),
      supabase.from('puzzle_attempts').select('*').eq('user_id', friendId),
      supabase.from('daily_questions').select('id,date').in('date', dates),
      supabase.from('daily_puzzles').select('id,date').in('date', dates),
    ]);

  const questionIdByDate = new Map((questions ?? []).map((q) => [q.date, q.id]));
  const puzzleIdByDate = new Map((puzzles ?? []).map((p) => [p.date, p.id]));

  const findAttempt = <T extends { question_id?: string; puzzle_id?: string }>(rows: T[] | null, id: string, key: 'question_id' | 'puzzle_id') =>
    (rows ?? []).find((r) => r[key] === id);

  return dates.map((date) => {
    const questionId = questionIdByDate.get(date);
    const puzzleId = puzzleIdByDate.get(date);
    const myQuestion = questionId ? findAttempt(myQ, questionId, 'question_id') : undefined;
    const myPuzzle = puzzleId ? findAttempt(myP, puzzleId, 'puzzle_id') : undefined;
    const theirQuestion = questionId ? findAttempt(friendQ, questionId, 'question_id') : undefined;
    const theirPuzzle = puzzleId ? findAttempt(friendP, puzzleId, 'puzzle_id') : undefined;
    return {
      date,
      me: {
        questionSolved: (myQuestion as any)?.solved ?? false,
        questionGuesses: (myQuestion as any)?.guess_count ?? 0,
        puzzleSolved: (myPuzzle as any)?.solved ?? false,
        puzzleTimeSeconds: (myPuzzle as any)?.time_seconds ?? 0,
      },
      friend: {
        questionSolved: (theirQuestion as any)?.solved ?? false,
        questionGuesses: (theirQuestion as any)?.guess_count ?? 0,
        puzzleSolved: (theirPuzzle as any)?.solved ?? false,
        puzzleTimeSeconds: (theirPuzzle as any)?.time_seconds ?? 0,
      },
    };
  });
}
