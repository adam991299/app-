-- submit_question_guess / submit_puzzle_attempt — the *only* way attempt rows get
-- written, and the only way a client learns the real answer/solution.
--
-- Both are security-definer: they run with the function owner's privileges, so unlike
-- a normal client query they CAN read daily_questions.answer_number and
-- daily_puzzles.solution (which 0006_column_privileges.sql hides from direct client
-- select). They reveal that value in their response only once the attempt is actually
-- finished — never while a question attempt is still in progress.

-- ---------------------------------------------------------------------------
-- submit_question_guess — call once per guess (up to 3). The server derives
-- "higher"/"lower"/"correct" and appends it to the authoritative guesses array;
-- the client never sends (and never needs) the full history itself.
-- ---------------------------------------------------------------------------
create type public.question_guess_result as (
  guess_count int,
  direction text, -- 'higher' | 'lower' | 'correct'
  solved boolean,
  is_final boolean,
  answer_number numeric, -- only populated once is_final = true
  score int,
  completed_at timestamptz
);

create or replace function public.submit_question_guess(
  p_question_id uuid,
  p_value numeric,
  p_time_seconds int
)
returns public.question_guess_result
language plpgsql
security definer set search_path = public
as $$
declare
  v_answer numeric;
  v_existing public.question_attempts;
  v_guesses jsonb;
  v_guess_count int;
  v_direction text;
  v_solved boolean;
  v_is_final boolean;
  v_score int;
  v_completed_at timestamptz;
  v_result public.question_guess_result;
begin
  select answer_number into v_answer from public.daily_questions where id = p_question_id;
  if v_answer is null then
    raise exception 'Unknown question_id';
  end if;

  select * into v_existing
  from public.question_attempts
  where user_id = auth.uid() and question_id = p_question_id;

  if v_existing.completed_at is not null then
    -- Idempotent: replay the final state instead of accepting a new guess.
    v_result.guess_count := v_existing.guess_count;
    v_result.direction := (v_existing.guesses -> (v_existing.guess_count - 1) ->> 'direction');
    v_result.solved := v_existing.solved;
    v_result.is_final := true;
    v_result.answer_number := v_answer;
    v_result.score := v_existing.score;
    v_result.completed_at := v_existing.completed_at;
    return v_result;
  end if;

  v_guesses := coalesce(v_existing.guesses, '[]'::jsonb);
  v_guess_count := jsonb_array_length(v_guesses);

  if v_guess_count >= 3 then
    raise exception 'No guesses remaining';
  end if;

  v_solved := p_value = v_answer;
  v_direction := case when v_solved then 'correct' when p_value < v_answer then 'higher' else 'lower' end;
  v_guesses := v_guesses || jsonb_build_array(jsonb_build_object('value', p_value, 'direction', v_direction));
  v_guess_count := v_guess_count + 1;
  v_is_final := v_solved or v_guess_count >= 3;
  v_completed_at := case when v_is_final then now() else null end;
  v_score := case when v_is_final then
    public.score_question_attempt(v_answer, p_value, v_guess_count, v_solved)
  else 0 end;

  insert into public.question_attempts (
    user_id, question_id, guesses, guess_count, time_seconds, solved, score, completed_at
  )
  values (auth.uid(), p_question_id, v_guesses, v_guess_count, p_time_seconds, v_solved, v_score, v_completed_at)
  on conflict (user_id, question_id) do update set
    guesses = excluded.guesses,
    guess_count = excluded.guess_count,
    time_seconds = excluded.time_seconds,
    solved = excluded.solved,
    score = excluded.score,
    completed_at = excluded.completed_at;

  v_result.guess_count := v_guess_count;
  v_result.direction := v_direction;
  v_result.solved := v_solved;
  v_result.is_final := v_is_final;
  v_result.answer_number := case when v_is_final then v_answer else null end;
  v_result.score := v_score;
  v_result.completed_at := v_completed_at;
  return v_result;
end;
$$;

grant execute on function public.submit_question_guess(uuid, numeric, int) to authenticated;

-- ---------------------------------------------------------------------------
-- submit_puzzle_attempt — single submission (no multi-guess concept for the
-- launch puzzle type), but still validated server-side against `solution`.
-- ---------------------------------------------------------------------------
create type public.puzzle_attempt_result as (
  solved boolean,
  score int,
  solution jsonb, -- revealed now that the attempt is finished
  completed_at timestamptz
);

create or replace function public.submit_puzzle_attempt(
  p_puzzle_id uuid,
  p_answer jsonb, -- { "values": number[] } — the values the player placed in the blanks
  p_time_seconds int
)
returns public.puzzle_attempt_result
language plpgsql
security definer set search_path = public
as $$
declare
  v_solution jsonb;
  v_existing public.puzzle_attempts;
  v_solved boolean;
  v_score int;
  v_result public.puzzle_attempt_result;
begin
  select solution into v_solution from public.daily_puzzles where id = p_puzzle_id;
  if v_solution is null then
    raise exception 'Unknown puzzle_id';
  end if;

  select * into v_existing
  from public.puzzle_attempts
  where user_id = auth.uid() and puzzle_id = p_puzzle_id;

  if v_existing.completed_at is not null then
    v_result.solved := v_existing.solved;
    v_result.score := v_existing.score;
    v_result.solution := v_solution;
    v_result.completed_at := v_existing.completed_at;
    return v_result;
  end if;

  v_solved := (p_answer -> 'values') = (v_solution -> 'values');
  v_score := public.score_puzzle_attempt(p_time_seconds, v_solved);

  insert into public.puzzle_attempts (
    user_id, puzzle_id, answer, time_seconds, solved, score, completed_at
  )
  values (auth.uid(), p_puzzle_id, p_answer, p_time_seconds, v_solved, v_score, now())
  on conflict (user_id, puzzle_id) do update set
    answer = excluded.answer,
    time_seconds = excluded.time_seconds,
    solved = excluded.solved,
    score = excluded.score,
    completed_at = excluded.completed_at;

  v_result.solved := v_solved;
  v_result.score := v_score;
  v_result.solution := v_solution;
  v_result.completed_at := now();
  return v_result;
end;
$$;

grant execute on function public.submit_puzzle_attempt(uuid, jsonb, int) to authenticated;
