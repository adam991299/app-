/// <reference types="node" />
/**
 * Bulk-imports the starter content pipeline: 30 days of daily questions + daily puzzles.
 *
 * Usage:
 *   SUPABASE_URL=https://xxxx.supabase.co SUPABASE_SERVICE_ROLE_KEY=xxxx npm run seed
 *
 * This uses the service role key (server-only — never ship it in the app bundle) so it
 * bypasses Row Level Security and can upsert directly into daily_questions/daily_puzzles.
 * Safe to re-run: it upserts on the unique `date` column, so it won't create duplicates.
 */
import { createClient } from '@supabase/supabase-js';
import { readFileSync } from 'node:fs';
import path from 'node:path';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
  console.error(
    '✗ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.\n' +
      '  Find both in your Supabase project → Settings → API, then re-run:\n' +
      '  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... npm run seed'
  );
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

type QuestionSeed = {
  date: string;
  question_text: string;
  answer_number: number;
  unit: string | null;
  category: string;
  source_note: string;
};

type PuzzleSeed = {
  date: string;
  puzzle_type: string;
  title: string;
  puzzle_data: { sequence: (number | null)[] };
  solution: { values: number[] };
};

async function main() {
  const questions: QuestionSeed[] = JSON.parse(
    readFileSync(path.join(__dirname, 'content/questions.json'), 'utf8')
  );
  const puzzles: PuzzleSeed[] = JSON.parse(
    readFileSync(path.join(__dirname, 'content/puzzles.json'), 'utf8')
  );

  console.log(`Seeding ${questions.length} daily questions...`);
  const { error: qError, count: qCount } = await supabase
    .from('daily_questions')
    .upsert(questions, { onConflict: 'date', count: 'exact' });
  if (qError) throw qError;
  console.log(`  ✓ upserted ${qCount ?? questions.length} questions`);

  console.log(`Seeding ${puzzles.length} daily puzzles...`);
  const { error: pError, count: pCount } = await supabase
    .from('daily_puzzles')
    .upsert(puzzles, { onConflict: 'date', count: 'exact' });
  if (pError) throw pError;
  console.log(`  ✓ upserted ${pCount ?? puzzles.length} puzzles`);

  console.log('\nDone. Content is live for', questions[0].date, '→', questions.at(-1)!.date);
}

main().catch((err) => {
  console.error('✗ Seed failed:', err.message ?? err);
  process.exit(1);
});
