import AsyncStorage from '@react-native-async-storage/async-storage';
import type {
  PuzzleAttemptRow,
  QuestionAttemptRow,
  QuestionGuess,
  StreakRow,
  UserRow,
} from '@/types/database';

const STORAGE_KEY = 'narmast.demo.v1';

export interface DemoState {
  profile: UserRow | null;
  streak: StreakRow;
  questionAttempts: Record<string, QuestionAttemptRow>;
  puzzleAttempts: Record<string, PuzzleAttemptRow>;
  friendIds: string[];
  isPremium: boolean;
}

function defaultState(): DemoState {
  return {
    profile: null,
    streak: { user_id: 'demo-me', current_streak: 0, longest_streak: 0, last_completed_date: null, updated_at: new Date().toISOString() },
    questionAttempts: {},
    puzzleAttempts: {},
    friendIds: [],
    isPremium: false,
  };
}

let cache: DemoState | null = null;
let loadPromise: Promise<DemoState> | null = null;

async function load(): Promise<DemoState> {
  if (cache) return cache;
  if (!loadPromise) {
    loadPromise = AsyncStorage.getItem(STORAGE_KEY).then((raw) => {
      const loaded: DemoState = raw ? { ...defaultState(), ...JSON.parse(raw) } : defaultState();
      cache = loaded;
      return loaded;
    });
  }
  return loadPromise;
}

async function persist(): Promise<void> {
  if (!cache) return;
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
}

export async function getDemoState(): Promise<DemoState> {
  return load();
}

export async function updateDemoState(mutator: (state: DemoState) => void): Promise<DemoState> {
  const state = await load();
  mutator(state);
  await persist();
  return state;
}

export async function resetDemoState(): Promise<void> {
  cache = defaultState();
  loadPromise = null;
  await AsyncStorage.removeItem(STORAGE_KEY);
}

function makeInviteCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let out = '';
  for (let i = 0; i < 6; i++) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}

export async function ensureDemoProfile(): Promise<UserRow> {
  const state = await load();
  if (state.profile) return state.profile;
  const profile: UserRow = {
    id: 'demo-me',
    display_name: 'You',
    avatar_emoji: '🙂',
    avatar_color: '#E4572E',
    avatar_url: null,
    invite_code: makeInviteCode(),
    notification_time: '09:00:00',
    notifications_enabled: true,
    timezone: 'UTC',
    is_premium: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  await updateDemoState((s) => {
    s.profile = profile;
  });
  return profile;
}

/** Mirrors supabase/migrations/0001_init.sql `recompute_streak` so demo mode and the
 * real backend behave identically. */
export function recomputeDemoStreak(state: DemoState, date: string): void {
  const questionDone = Object.values(state.questionAttempts).some(
    (a) => a.completed_at && a.completed_at.slice(0, 10) === date
  );
  const puzzleDone = Object.values(state.puzzleAttempts).some(
    (a) => a.completed_at && a.completed_at.slice(0, 10) === date
  );
  if (!questionDone || !puzzleDone) return;

  const { last_completed_date, current_streak, longest_streak } = state.streak;
  if (last_completed_date === date) return;

  const yesterday = new Date(new Date(`${date}T00:00:00Z`).getTime() - 86400000)
    .toISOString()
    .slice(0, 10);

  const newCurrent = last_completed_date === yesterday ? current_streak + 1 : 1;
  state.streak = {
    ...state.streak,
    current_streak: newCurrent,
    longest_streak: Math.max(longest_streak, newCurrent),
    last_completed_date: date,
    updated_at: new Date().toISOString(),
  };
}

export function scoreQuestion(answer: number, finalGuess: number, guessCount: number, solved: boolean): number {
  if (!solved) return 0;
  const proximityRatio = Math.abs(finalGuess - answer) / Math.max(Math.abs(answer), 1);
  const score = 1000 - Math.max(guessCount - 1, 0) * 300 - Math.min(proximityRatio * 500, 400);
  return Math.max(Math.round(score), 100);
}

export function scorePuzzle(timeSeconds: number, solved: boolean): number {
  if (!solved) return 0;
  return Math.max(1000 - Math.floor(timeSeconds / 10) * 50, 100);
}

export type { QuestionGuess };
