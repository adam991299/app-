import type {
  PublicDailyPuzzle,
  PublicDailyQuestion,
  PuzzleAttemptRow,
  QuestionAttemptRow,
} from './database';

export type CompletionState = 'not_started' | 'in_progress' | 'completed';

export interface TodayContent {
  question: PublicDailyQuestion | null;
  puzzle: PublicDailyPuzzle | null;
  questionAttempt: QuestionAttemptRow | null;
  puzzleAttempt: PuzzleAttemptRow | null;
}

export function questionState(attempt: QuestionAttemptRow | null): CompletionState {
  if (!attempt) return 'not_started';
  if (attempt.completed_at) return 'completed';
  return 'in_progress';
}

export function puzzleState(attempt: PuzzleAttemptRow | null): CompletionState {
  if (!attempt) return 'not_started';
  if (attempt.completed_at) return 'completed';
  return 'in_progress';
}
