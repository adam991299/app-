-- get_revealed_answer / get_revealed_solution — lets a results screen show the correct
-- answer/solution for a question or puzzle the caller has already finished, even after
-- navigating away and back (e.g. reopening a completed day from Home or the archive).
-- Security-definer so it can read the otherwise column-restricted answer_number/solution,
-- but only after confirming *this* user has a completed attempt for that content.

create or replace function public.get_revealed_answer(p_question_id uuid)
returns numeric
language plpgsql
security definer set search_path = public
as $$
declare
  v_answer numeric;
begin
  if not exists (
    select 1 from public.question_attempts
    where user_id = auth.uid() and question_id = p_question_id and completed_at is not null
  ) then
    raise exception 'No completed attempt for this question';
  end if;

  select answer_number into v_answer from public.daily_questions where id = p_question_id;
  return v_answer;
end;
$$;

grant execute on function public.get_revealed_answer(uuid) to authenticated;

create or replace function public.get_revealed_solution(p_puzzle_id uuid)
returns jsonb
language plpgsql
security definer set search_path = public
as $$
declare
  v_solution jsonb;
begin
  if not exists (
    select 1 from public.puzzle_attempts
    where user_id = auth.uid() and puzzle_id = p_puzzle_id and completed_at is not null
  ) then
    raise exception 'No completed attempt for this puzzle';
  end if;

  select solution into v_solution from public.daily_puzzles where id = p_puzzle_id;
  return v_solution;
end;
$$;

grant execute on function public.get_revealed_solution(uuid) to authenticated;
