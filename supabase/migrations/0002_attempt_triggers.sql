-- Triggers that keep streaks in sync whenever an attempt is completed, plus the
-- server-side scoring functions so score computation can never be spoofed by the client.

-- ---------------------------------------------------------------------------
-- Scoring
--  Question: starts at 1000, -300 per guess used beyond the first, minus a
--  proximity penalty scaled by how far the final guess was from the answer
--  (relative to the answer's magnitude). Unsolved (3 wrong guesses) => 0.
--  Puzzle: starts at 1000, -50 per 10s elapsed, minimum 100 if solved.
-- ---------------------------------------------------------------------------
create or replace function public.score_question_attempt(
  p_answer numeric,
  p_final_guess numeric,
  p_guess_count int,
  p_solved boolean
) returns int
language plpgsql
immutable
as $$
declare
  proximity_ratio numeric;
  score numeric;
begin
  if not p_solved then
    return 0;
  end if;

  proximity_ratio := abs(p_final_guess - p_answer) / greatest(abs(p_answer), 1);
  score := 1000 - (greatest(p_guess_count - 1, 0) * 300) - least(proximity_ratio * 500, 400);
  return greatest(round(score)::int, 100);
end;
$$;

create or replace function public.score_puzzle_attempt(
  p_time_seconds int,
  p_solved boolean
) returns int
language plpgsql
immutable
as $$
begin
  if not p_solved then
    return 0;
  end if;
  return greatest(1000 - (p_time_seconds / 10) * 50, 100);
end;
$$;

-- ---------------------------------------------------------------------------
-- Streak-sync triggers
-- ---------------------------------------------------------------------------
create or replace function public.trg_question_attempt_completed()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  d date;
begin
  if new.completed_at is not null then
    select date into d from public.daily_questions where id = new.question_id;
    perform public.recompute_streak(new.user_id, d);
  end if;
  return new;
end;
$$;

create trigger trg_after_question_attempt
  after insert or update on public.question_attempts
  for each row execute function public.trg_question_attempt_completed();

create or replace function public.trg_puzzle_attempt_completed()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  d date;
begin
  if new.completed_at is not null then
    select date into d from public.daily_puzzles where id = new.puzzle_id;
    perform public.recompute_streak(new.user_id, d);
  end if;
  return new;
end;
$$;

create trigger trg_after_puzzle_attempt
  after insert or update on public.puzzle_attempts
  for each row execute function public.trg_puzzle_attempt_completed();
