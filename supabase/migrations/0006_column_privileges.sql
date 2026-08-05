-- Column-level privileges — belt-and-suspenders on top of RLS.
--
-- RLS controls *which rows* a role can see, not which *columns*. Without this, any
-- authenticated client could call `.from('daily_questions').select('*')` and read
-- answer_number directly out of the network response, or read `solution` off
-- daily_puzzles — trivially defeating the whole guessing game. We revoke the
-- table-wide SELECT that Supabase grants by default on every public table and
-- re-grant only the columns that are safe for a player to see directly. The real
-- answer/solution are only ever readable inside the security-definer RPCs in
-- 0005_submit_rpc.sql, which reveal them in their response only once an attempt
-- is actually finished.

revoke select on public.daily_questions from authenticated, anon;
grant select (id, date, question_text, unit, category, source_note, created_at)
  on public.daily_questions to authenticated;

revoke select on public.daily_puzzles from authenticated, anon;
grant select (id, date, puzzle_type, title, puzzle_data, created_at)
  on public.daily_puzzles to authenticated;
