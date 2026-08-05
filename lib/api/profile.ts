import { demoQuestions } from '@/lib/demo/content';
import { ensureDemoProfile, getDemoState, updateDemoState } from '@/lib/demo/store';
import { isSupabaseConfigured } from '@/lib/env';
import { supabase } from '@/lib/supabase';
import type { StreakRow, UserRow } from '@/types/database';

export async function getMyProfile(): Promise<UserRow> {
  if (!isSupabaseConfigured) return ensureDemoProfile();

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error('Not signed in');
  const { data, error } = await supabase.from('users').select('*').eq('id', user.id).single();
  if (error) throw error;
  return data;
}

export type ProfilePatch = Partial<
  Pick<UserRow, 'display_name' | 'avatar_emoji' | 'avatar_color' | 'notification_time' | 'notifications_enabled' | 'timezone'>
>;

/**
 * Demo-mode-only convenience so the paywall is actually explorable without a real
 * RevenueCat project: flips the local demo profile's `is_premium` flag directly. This
 * bypasses ProfilePatch on purpose — real Supabase mode has no equivalent (and
 * couldn't: `is_premium` is deliberately excluded from ProfilePatch, and even the raw
 * table's UPDATE grant excludes it — see 0008_users_column_privileges.sql. Only
 * revenuecat-webhook can flip it for real.) A no-op when Supabase is configured.
 */
export async function simulatePremiumPurchaseInDemoMode(): Promise<UserRow | null> {
  if (isSupabaseConfigured) return null;
  const state = await updateDemoState((s) => {
    if (s.profile) s.profile = { ...s.profile, is_premium: true, updated_at: new Date().toISOString() };
  });
  return state.profile;
}

export async function updateProfile(patch: ProfilePatch): Promise<UserRow> {
  if (!isSupabaseConfigured) {
    const state = await updateDemoState((s) => {
      if (s.profile) s.profile = { ...s.profile, ...patch, updated_at: new Date().toISOString() };
    });
    return state.profile!;
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error('Not signed in');
  const { data, error } = await supabase.from('users').update(patch).eq('id', user.id).select().single();
  if (error) throw error;
  return data;
}

export async function getMyStreak(): Promise<StreakRow> {
  if (!isSupabaseConfigured) {
    const state = await getDemoState();
    return state.streak;
  }
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error('Not signed in');
  const { data, error } = await supabase.from('streaks').select('*').eq('user_id', user.id).maybeSingle();
  if (error) throw error;
  return (
    data ?? { user_id: user.id, current_streak: 0, longest_streak: 0, last_completed_date: null, updated_at: new Date().toISOString() }
  );
}

export interface CategoryBreakdown {
  category: string;
  attempts: number;
  solved: number;
}

export interface PersonalStats {
  currentStreak: number;
  longestStreak: number;
  questionsPlayed: number;
  questionsSolved: number;
  puzzlesPlayed: number;
  puzzlesSolved: number;
  averageGuesses: number;
  winRate: number; // 0-1, across both question + puzzle attempts
  categoryBreakdown: CategoryBreakdown[];
  scoreHistory: { date: string; score: number }[];
}

export async function getMyStats(): Promise<PersonalStats> {
  const streak = await getMyStreak();

  if (!isSupabaseConfigured) {
    const state = await getDemoState();
    const questionAttempts = Object.values(state.questionAttempts).filter((a) => a.completed_at);
    const puzzleAttempts = Object.values(state.puzzleAttempts).filter((a) => a.completed_at);
    const categoryMap = new Map(demoQuestions.map((q) => [q.id, q.category]));

    const breakdown = new Map<string, CategoryBreakdown>();
    questionAttempts.forEach((a) => {
      const category = categoryMap.get(a.question_id) ?? 'other';
      const entry = breakdown.get(category) ?? { category, attempts: 0, solved: 0 };
      entry.attempts += 1;
      if (a.solved) entry.solved += 1;
      breakdown.set(category, entry);
    });

    const scoreHistory = [...questionAttempts, ...puzzleAttempts]
      .filter((a) => a.completed_at)
      .sort((a, b) => (a.completed_at! < b.completed_at! ? -1 : 1))
      .map((a) => ({ date: a.completed_at!.slice(0, 10), score: a.score }));

    const totalAttempts = questionAttempts.length + puzzleAttempts.length;
    const totalSolved = questionAttempts.filter((a) => a.solved).length + puzzleAttempts.filter((a) => a.solved).length;

    return {
      currentStreak: streak.current_streak,
      longestStreak: streak.longest_streak,
      questionsPlayed: questionAttempts.length,
      questionsSolved: questionAttempts.filter((a) => a.solved).length,
      puzzlesPlayed: puzzleAttempts.length,
      puzzlesSolved: puzzleAttempts.filter((a) => a.solved).length,
      averageGuesses: questionAttempts.length
        ? questionAttempts.reduce((sum, a) => sum + a.guess_count, 0) / questionAttempts.length
        : 0,
      winRate: totalAttempts ? totalSolved / totalAttempts : 0,
      categoryBreakdown: [...breakdown.values()],
      scoreHistory,
    };
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error('Not signed in');

  const [{ data: questionAttempts }, { data: puzzleAttempts }, { data: questions }] = await Promise.all([
    supabase.from('question_attempts').select('*').eq('user_id', user.id).not('completed_at', 'is', null),
    supabase.from('puzzle_attempts').select('*').eq('user_id', user.id).not('completed_at', 'is', null),
    supabase.from('daily_questions').select('id,category'),
  ]);

  const categoryMap = new Map((questions ?? []).map((q) => [q.id, q.category]));
  const qAttempts = questionAttempts ?? [];
  const pAttempts = puzzleAttempts ?? [];

  const breakdown = new Map<string, CategoryBreakdown>();
  qAttempts.forEach((a) => {
    const category = categoryMap.get(a.question_id) ?? 'other';
    const entry = breakdown.get(category) ?? { category, attempts: 0, solved: 0 };
    entry.attempts += 1;
    if (a.solved) entry.solved += 1;
    breakdown.set(category, entry);
  });

  const scoreHistory = [...qAttempts, ...pAttempts]
    .filter((a) => a.completed_at)
    .sort((a, b) => (a.completed_at! < b.completed_at! ? -1 : 1))
    .map((a) => ({ date: a.completed_at!.slice(0, 10), score: a.score }));

  const totalAttempts = qAttempts.length + pAttempts.length;
  const totalSolved = qAttempts.filter((a) => a.solved).length + pAttempts.filter((a) => a.solved).length;

  return {
    currentStreak: streak.current_streak,
    longestStreak: streak.longest_streak,
    questionsPlayed: qAttempts.length,
    questionsSolved: qAttempts.filter((a) => a.solved).length,
    puzzlesPlayed: pAttempts.length,
    puzzlesSolved: pAttempts.filter((a) => a.solved).length,
    averageGuesses: qAttempts.length ? qAttempts.reduce((sum, a) => sum + a.guess_count, 0) / qAttempts.length : 0,
    winRate: totalAttempts ? totalSolved / totalAttempts : 0,
    categoryBreakdown: [...breakdown.values()],
    scoreHistory,
  };
}
