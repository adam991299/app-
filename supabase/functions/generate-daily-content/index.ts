// Supabase Edge Function: generate-daily-content
//
// The content pipeline for pushing a day's question + puzzle ahead of time (e.g. from an
// internal admin tool, a spreadsheet-driven script, or eventually an LLM-assisted generator).
// Protected by a shared admin secret — never exposed to the client app.
//
// Deploy:   supabase functions deploy generate-daily-content
// Secret:   supabase secrets set ADMIN_CONTENT_SECRET=<a-long-random-string>
//
// Request:
//   POST /functions/v1/generate-daily-content
//   Headers: { "x-admin-secret": "<ADMIN_CONTENT_SECRET>" }
//   Body (JSON):
//   {
//     "date": "2026-09-04",
//     "question": {
//       "question_text": "What year was the Suez Canal opened?",
//       "answer_number": 1869,
//       "unit": null,
//       "category": "history",
//       "source_note": "Opened November 17, 1869."
//     },
//     "puzzle": {
//       "puzzle_type": "sequence",
//       "title": "The gap grows by 4 each time",
//       "puzzle_data": { "sequence": [3, 7, 11, 15, null] },
//       "solution": { "values": [19] }
//     }
//   }
//
// Either `question` or `puzzle` may be omitted to update just one of the two for that date.

import { createClient } from 'jsr:@supabase/supabase-js@2';

interface QuestionPayload {
  question_text: string;
  answer_number: number;
  unit?: string | null;
  category: string;
  source_note?: string | null;
}

interface PuzzlePayload {
  puzzle_type: string;
  title: string;
  puzzle_data: { sequence: (number | null)[] };
  solution: { values: number[] };
}

interface RequestBody {
  date: string; // YYYY-MM-DD, UTC
  question?: QuestionPayload;
  puzzle?: PuzzlePayload;
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return json({ error: 'Method not allowed' }, 405);
  }

  const adminSecret = req.headers.get('x-admin-secret');
  const expectedSecret = Deno.env.get('ADMIN_CONTENT_SECRET');
  if (!expectedSecret || adminSecret !== expectedSecret) {
    return json({ error: 'Unauthorized' }, 401);
  }

  let body: RequestBody;
  try {
    body = await req.json();
  } catch {
    return json({ error: 'Invalid JSON body' }, 400);
  }

  if (!body.date || !DATE_RE.test(body.date)) {
    return json({ error: 'date must be an ISO date string, e.g. "2026-09-04"' }, 400);
  }
  if (!body.question && !body.puzzle) {
    return json({ error: 'Provide at least one of "question" or "puzzle"' }, 400);
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  const result: Record<string, unknown> = { date: body.date };

  if (body.question) {
    const q = body.question;
    if (typeof q.question_text !== 'string' || typeof q.answer_number !== 'number' || !q.category) {
      return json({ error: 'question requires question_text, answer_number, category' }, 400);
    }
    const { error } = await supabase
      .from('daily_questions')
      .upsert({ date: body.date, ...q, unit: q.unit ?? null }, { onConflict: 'date' });
    if (error) return json({ error: `question upsert failed: ${error.message}` }, 500);
    result.question = 'ok';
  }

  if (body.puzzle) {
    const p = body.puzzle;
    if (!p.title || !p.puzzle_data?.sequence || !p.solution?.values) {
      return json({ error: 'puzzle requires title, puzzle_data.sequence, solution.values' }, 400);
    }
    const { error } = await supabase
      .from('daily_puzzles')
      .upsert({ date: body.date, puzzle_type: p.puzzle_type ?? 'sequence', ...p }, { onConflict: 'date' });
    if (error) return json({ error: `puzzle upsert failed: ${error.message}` }, 500);
    result.puzzle = 'ok';
  }

  return json(result, 200);
});

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
