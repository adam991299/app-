import { create } from 'zustand';
import { getTodayContent, submitPuzzleAttempt, submitQuestionGuess } from '@/lib/api/content';
import { getMyStreak } from '@/lib/api/profile';
import type { PuzzleAttemptResult, QuestionGuessResult, StreakRow } from '@/types/database';
import type { TodayContent } from '@/types/game';

interface GameState {
  today: TodayContent | null;
  streak: StreakRow | null;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
  guessQuestion: (value: number, elapsedSeconds: number) => Promise<QuestionGuessResult>;
  submitPuzzle: (values: number[], elapsedSeconds: number) => Promise<PuzzleAttemptResult>;
}

export const useGameStore = create<GameState>()((set, get) => ({
  today: null,
  streak: null,
  loading: false,
  error: null,

  load: async () => {
    set({ loading: true, error: null });
    try {
      const [today, streak] = await Promise.all([getTodayContent(), getMyStreak()]);
      set({ today, streak, loading: false });
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err.message : 'Something went wrong.' });
    }
  },

  guessQuestion: async (value, elapsedSeconds) => {
    const { today } = get();
    if (!today?.question) throw new Error('No question loaded');
    const result = await submitQuestionGuess(today.question.id, value, elapsedSeconds);

    set((state) => {
      if (!state.today?.question) return state;
      const prev = state.today.questionAttempt;
      const guesses = [...(prev?.guesses ?? []), { value, direction: result.direction }];
      return {
        today: {
          ...state.today,
          questionAttempt: {
            id: prev?.id ?? `local-${state.today.question.id}`,
            user_id: prev?.user_id ?? '',
            question_id: state.today.question.id,
            guesses,
            guess_count: result.guess_count,
            time_seconds: elapsedSeconds,
            solved: result.solved,
            score: result.score,
            completed_at: result.completed_at,
            created_at: prev?.created_at ?? new Date().toISOString(),
          },
        },
      };
    });

    if (result.is_final) {
      const streak = await getMyStreak();
      set({ streak });
    }

    return result;
  },

  submitPuzzle: async (values, elapsedSeconds) => {
    const { today } = get();
    if (!today?.puzzle) throw new Error('No puzzle loaded');
    const result = await submitPuzzleAttempt(today.puzzle.id, values, elapsedSeconds);

    set((state) => {
      if (!state.today?.puzzle) return state;
      const prev = state.today.puzzleAttempt;
      return {
        today: {
          ...state.today,
          puzzleAttempt: {
            id: prev?.id ?? `local-${state.today.puzzle.id}`,
            user_id: prev?.user_id ?? '',
            puzzle_id: state.today.puzzle.id,
            answer: { values },
            time_seconds: elapsedSeconds,
            solved: result.solved,
            score: result.score,
            completed_at: result.completed_at,
            created_at: prev?.created_at ?? new Date().toISOString(),
          },
        },
      };
    });

    const streak = await getMyStreak();
    set({ streak });

    return result;
  },
}));
