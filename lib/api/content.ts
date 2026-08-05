import { getContentDateUTC } from '@/lib/dateUtils';
import { isSupabaseConfigured } from '@/lib/env';
import { supabase } from '@/lib/supabase';
import {
  demoPuzzles,
  demoQuestions,
  getDemoPuzzleForDate,
  getDemoQuestionForDate,
  isDateWithinSeedRange,
} from '@/lib/demo/content';
import { getDemoState, scorePuzzle, scoreQuestion, recomputeDemoStreak, updateDemoState } from '@/lib/demo/store';
import type {
  DailyPuzzleRow,
  DailyQuestionRow,
  PublicDailyPuzzle,
  PublicDailyQuestion,
  PuzzleAttemptResult,
  PuzzleAttemptRow,
  QuestionAttemptRow,
  QuestionGuessResult,
} from '@/types/database';
import type { TodayContent } from '@/types/game';

export async function getTodayContent(): Promise<TodayContent> {
  const date = getContentDateUTC();

  if (!isSupabaseConfigured) {
    const question = getDemoQuestionForDate(date);
    const puzzle = getDemoPuzzleForDate(date);
    const state = await getDemoState();
    return {
      question: toPublicQuestion(question),
      puzzle: toPublicPuzzle(puzzle),
      questionAttempt: state.questionAttempts[question.id] ?? null,
      puzzleAttempt: state.puzzleAttempts[puzzle.id] ?? null,
    };
  }

  const [{ data: question }, { data: puzzle }] = await Promise.all([
    supabase
      .from('daily_questions')
      .select('id,date,question_text,unit,category,source_note,created_at')
      .eq('date', date)
      .maybeSingle(),
    supabase
      .from('daily_puzzles')
      .select('id,date,puzzle_type,title,puzzle_data,created_at')
      .eq('date', date)
      .maybeSingle(),
  ]);

  const {
    data: { user },
  } = await supabase.auth.getUser();

  let questionAttempt: QuestionAttemptRow | null = null;
  let puzzleAttempt: PuzzleAttemptRow | null = null;

  if (user && question) {
    const { data } = await supabase
      .from('question_attempts')
      .select('*')
      .eq('user_id', user.id)
      .eq('question_id', question.id)
      .maybeSingle();
    questionAttempt = data;
  }
  if (user && puzzle) {
    const { data } = await supabase
      .from('puzzle_attempts')
      .select('*')
      .eq('user_id', user.id)
      .eq('puzzle_id', puzzle.id)
      .maybeSingle();
    puzzleAttempt = data;
  }

  return {
    question: question as PublicDailyQuestion | null,
    puzzle: puzzle as unknown as PublicDailyPuzzle | null,
    questionAttempt,
    puzzleAttempt,
  };
}

export async function submitQuestionGuess(
  questionId: string,
  value: number,
  timeSeconds: number
): Promise<QuestionGuessResult> {
  if (!isSupabaseConfigured) {
    const question = demoQuestions.find((q) => q.id === questionId);
    if (!question) throw new Error('Unknown question');

    const state = await getDemoState();
    const existing = state.questionAttempts[questionId];
    if (existing?.completed_at) {
      const last = existing.guesses[existing.guesses.length - 1];
      return {
        guess_count: existing.guess_count,
        direction: last.direction,
        solved: existing.solved,
        is_final: true,
        answer_number: question.answer_number,
        score: existing.score,
        completed_at: existing.completed_at,
      };
    }

    const guesses = existing?.guesses ? [...existing.guesses] : [];
    const solved = value === question.answer_number;
    const direction: 'higher' | 'lower' | 'correct' = solved ? 'correct' : value < question.answer_number ? 'higher' : 'lower';
    guesses.push({ value, direction });
    const guessCount = guesses.length;
    const isFinal = solved || guessCount >= 3;
    const completedAt = isFinal ? new Date().toISOString() : null;
    const score = isFinal ? scoreQuestion(question.answer_number, value, guessCount, solved) : 0;

    await updateDemoState((s) => {
      s.questionAttempts[questionId] = {
        id: `qa-${questionId}`,
        user_id: 'demo-me',
        question_id: questionId,
        guesses,
        guess_count: guessCount,
        time_seconds: timeSeconds,
        solved,
        score,
        completed_at: completedAt,
        created_at: existing?.created_at ?? new Date().toISOString(),
      };
      if (isFinal) recomputeDemoStreak(s, question.date);
    });

    return {
      guess_count: guessCount,
      direction,
      solved,
      is_final: isFinal,
      answer_number: isFinal ? question.answer_number : null,
      score,
      completed_at: completedAt,
    };
  }

  const { data, error } = await supabase.rpc('submit_question_guess', {
    p_question_id: questionId,
    p_value: value,
    p_time_seconds: timeSeconds,
  });
  if (error) throw error;
  return data as unknown as QuestionGuessResult;
}

export async function submitPuzzleAttempt(
  puzzleId: string,
  values: number[],
  timeSeconds: number
): Promise<PuzzleAttemptResult> {
  if (!isSupabaseConfigured) {
    const puzzle = demoPuzzles.find((p) => p.id === puzzleId);
    if (!puzzle) throw new Error('Unknown puzzle');

    const state = await getDemoState();
    const existing = state.puzzleAttempts[puzzleId];
    if (existing?.completed_at) {
      return {
        solved: existing.solved,
        score: existing.score,
        solution: puzzle.solution,
        completed_at: existing.completed_at,
      };
    }

    const solved = JSON.stringify(values) === JSON.stringify(puzzle.solution.values);
    const score = scorePuzzle(timeSeconds, solved);
    const completedAt = new Date().toISOString();

    await updateDemoState((s) => {
      s.puzzleAttempts[puzzleId] = {
        id: `pa-${puzzleId}`,
        user_id: 'demo-me',
        puzzle_id: puzzleId,
        answer: { values },
        time_seconds: timeSeconds,
        solved,
        score,
        completed_at: completedAt,
        created_at: existing?.created_at ?? new Date().toISOString(),
      };
      recomputeDemoStreak(s, puzzle.date);
    });

    return { solved, score, solution: puzzle.solution, completed_at: completedAt };
  }

  const { data, error } = await supabase.rpc('submit_puzzle_attempt', {
    p_puzzle_id: puzzleId,
    p_answer: { values },
    p_time_seconds: timeSeconds,
  });
  if (error) throw error;
  return data as unknown as PuzzleAttemptResult;
}

export interface ArchiveDay {
  question: PublicDailyQuestion;
  puzzle: PublicDailyPuzzle;
  questionAttempt: QuestionAttemptRow | null;
  puzzleAttempt: PuzzleAttemptRow | null;
}

/** Past 30 days (excluding today), newest first. Requires premium — the backend RLS
 * enforces this for real Supabase; demo mode enforces the same rule client-side. */
export async function getArchive(isPremium: boolean): Promise<ArchiveDay[]> {
  if (!isPremium) return [];
  const today = getContentDateUTC();

  if (!isSupabaseConfigured) {
    const state = await getDemoState();
    return demoQuestions
      .filter((q) => q.date !== today && isDateWithinSeedRange(q.date))
      .sort((a, b) => (a.date < b.date ? 1 : -1))
      .map((question) => {
        const puzzle = getDemoPuzzleForDate(question.date);
        return {
          question: toPublicQuestion(question),
          puzzle: toPublicPuzzle(puzzle),
          questionAttempt: state.questionAttempts[question.id] ?? null,
          puzzleAttempt: state.puzzleAttempts[puzzle.id] ?? null,
        };
      });
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return [];

  const [{ data: questions }, { data: puzzles }, { data: questionAttempts }, { data: puzzleAttempts }] =
    await Promise.all([
      supabase
        .from('daily_questions')
        .select('id,date,question_text,unit,category,source_note,created_at')
        .lt('date', today)
        .order('date', { ascending: false }),
      supabase
        .from('daily_puzzles')
        .select('id,date,puzzle_type,title,puzzle_data,created_at')
        .lt('date', today)
        .order('date', { ascending: false }),
      supabase.from('question_attempts').select('*').eq('user_id', user.id),
      supabase.from('puzzle_attempts').select('*').eq('user_id', user.id),
    ]);

  const qaByQuestion = new Map((questionAttempts ?? []).map((a) => [a.question_id, a]));
  const paByPuzzle = new Map((puzzleAttempts ?? []).map((a) => [a.puzzle_id, a]));
  const puzzleByDate = new Map((puzzles ?? []).map((p) => [p.date, p]));

  return (questions ?? [])
    .filter((q) => puzzleByDate.has(q.date))
    .map((question) => {
      const puzzle = puzzleByDate.get(question.date)!;
      return {
        question: question as PublicDailyQuestion,
        puzzle: puzzle as unknown as PublicDailyPuzzle,
        questionAttempt: qaByQuestion.get(question.id) ?? null,
        puzzleAttempt: paByPuzzle.get(puzzle.id) ?? null,
      };
    });
}

function toPublicQuestion(q: DailyQuestionRow): PublicDailyQuestion {
  const { id, date, question_text, unit, category, source_note, created_at } = q;
  return { id, date, question_text, unit, category, source_note, created_at };
}

function toPublicPuzzle(p: DailyPuzzleRow): PublicDailyPuzzle {
  const { id, date, puzzle_type, title, puzzle_data, created_at } = p;
  return { id, date, puzzle_type, title, puzzle_data, created_at };
}
