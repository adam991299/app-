import questionsSeed from '@/supabase/seed/content/questions.json';
import puzzlesSeed from '@/supabase/seed/content/puzzles.json';
import type { DailyPuzzleRow, DailyQuestionRow } from '@/types/database';

interface RawQuestion {
  date: string;
  question_text: string;
  answer_number: number;
  unit: string | null;
  category: string;
  source_note: string;
}

interface RawPuzzle {
  date: string;
  puzzle_type: 'sequence';
  title: string;
  puzzle_data: { sequence: (number | null)[] };
  solution: { values: number[] };
}

const rawQuestions = questionsSeed as RawQuestion[];
const rawPuzzles = puzzlesSeed as RawPuzzle[];

function toQuestionRow(raw: RawQuestion): DailyQuestionRow {
  return {
    id: `q-${raw.date}`,
    date: raw.date,
    question_text: raw.question_text,
    answer_number: raw.answer_number,
    unit: raw.unit,
    category: raw.category,
    source_note: raw.source_note,
    created_at: `${raw.date}T00:00:00.000Z`,
  };
}

function toPuzzleRow(raw: RawPuzzle): DailyPuzzleRow {
  return {
    id: `p-${raw.date}`,
    date: raw.date,
    puzzle_type: raw.puzzle_type,
    title: raw.title,
    puzzle_data: raw.puzzle_data,
    solution: raw.solution,
    created_at: `${raw.date}T00:00:00.000Z`,
  };
}

export const demoQuestions: DailyQuestionRow[] = rawQuestions.map(toQuestionRow);
export const demoPuzzles: DailyPuzzleRow[] = rawPuzzles.map(toPuzzleRow);

const questionByDate = new Map(demoQuestions.map((q) => [q.date, q]));
const puzzleByDate = new Map(demoPuzzles.map((p) => [p.date, p]));

const firstDate = demoQuestions[0].date;
const lastDate = demoQuestions[demoQuestions.length - 1].date;

/** Seed content only covers a fixed 30-day launch window. Outside of it (demo mode run
 * long after the seed range, or before it) we deterministically cycle back into the
 * range so the demo never shows "no content today". */
function resolveDemoDate(date: string): string {
  if (questionByDate.has(date)) return date;
  const dayMs = 24 * 60 * 60 * 1000;
  const offsetDays = Math.floor(
    (new Date(`${date}T00:00:00Z`).getTime() - new Date(`${firstDate}T00:00:00Z`).getTime()) / dayMs
  );
  const cycled = ((offsetDays % demoQuestions.length) + demoQuestions.length) % demoQuestions.length;
  return demoQuestions[cycled].date;
}

export function getDemoQuestionForDate(date: string): DailyQuestionRow {
  const resolved = resolveDemoDate(date);
  return questionByDate.get(resolved)!;
}

export function getDemoPuzzleForDate(date: string): DailyPuzzleRow {
  const resolved = resolveDemoDate(date);
  return puzzleByDate.get(resolved)!;
}

export function isDateWithinSeedRange(date: string): boolean {
  return date >= firstDate && date <= lastDate;
}

export { firstDate as demoFirstDate, lastDate as demoLastDate };
