-- RPCs used by the client for friend lookup/adding, the weekly leaderboard and the
-- home-screen friend activity feed. Grouped separately from RLS so the security-definer
-- boundary each function crosses is easy to audit in one place.

-- ---------------------------------------------------------------------------
-- find_user_by_invite_code — lets a user preview who a code belongs to before
-- adding them. Deliberately returns only public-facing fields.
-- ---------------------------------------------------------------------------
create or replace function public.find_user_by_invite_code(p_code text)
returns table (id uuid, display_name text, avatar_emoji text, avatar_color text)
language sql
stable
security definer set search_path = public
as $$
  select u.id, u.display_name, u.avatar_emoji, u.avatar_color
  from public.users u
  where u.invite_code = upper(trim(p_code));
$$;

grant execute on function public.find_user_by_invite_code(text) to authenticated;

-- ---------------------------------------------------------------------------
-- add_friend_by_code — knowing someone's code is treated as consent, so this
-- creates an immediately-accepted friendship (no pending/approve step, mirroring
-- how the invite code was shared out-of-band in the first place).
-- ---------------------------------------------------------------------------
create or replace function public.add_friend_by_code(p_code text)
returns public.users
language plpgsql
security definer set search_path = public
as $$
declare
  target public.users;
begin
  select * into target from public.users where invite_code = upper(trim(p_code));

  if target.id is null then
    raise exception 'No player found for that code.';
  end if;

  if target.id = auth.uid() then
    raise exception 'You can''t add yourself as a friend.';
  end if;

  insert into public.friendships (user_id, friend_id, status)
  values (auth.uid(), target.id, 'accepted')
  on conflict (user_id, friend_id) do update set status = 'accepted';

  return target;
end;
$$;

grant execute on function public.add_friend_by_code(text) to authenticated;

-- ---------------------------------------------------------------------------
-- my_friend_ids — the caller's accepted friends, either direction.
-- ---------------------------------------------------------------------------
create or replace function public.my_friend_ids()
returns setof uuid
language sql
stable
security definer set search_path = public
as $$
  select case when user_id = auth.uid() then friend_id else user_id end
  from public.friendships
  where status = 'accepted' and (user_id = auth.uid() or friend_id = auth.uid());
$$;

grant execute on function public.my_friend_ids() to authenticated;

-- ---------------------------------------------------------------------------
-- weekly_leaderboard — caller + accepted friends, ranked by cumulative score
-- for the current ISO week (Mon 00:00 UTC – Sun 23:59:59 UTC), ties broken by
-- total time (faster wins).
-- ---------------------------------------------------------------------------
create or replace function public.weekly_leaderboard()
returns table (
  user_id uuid,
  display_name text,
  avatar_emoji text,
  avatar_color text,
  total_score bigint,
  total_time_seconds bigint,
  questions_solved bigint,
  puzzles_solved bigint,
  rank bigint
)
language sql
stable
security definer set search_path = public
as $$
  with week_bounds as (
    select date_trunc('week', (now() at time zone 'utc'))::date as week_start
  ),
  cohort as (
    select auth.uid() as id
    union
    select id from public.my_friend_ids() as id
  ),
  q as (
    select qa.user_id,
           sum(qa.score) as score,
           sum(qa.time_seconds) as time_seconds,
           count(*) filter (where qa.solved) as solved_count
    from public.question_attempts qa
    join public.daily_questions dq on dq.id = qa.question_id
    join week_bounds wb on dq.date >= wb.week_start and dq.date < wb.week_start + 7
    where qa.user_id in (select id from cohort)
    group by qa.user_id
  ),
  p as (
    select pa.user_id,
           sum(pa.score) as score,
           sum(pa.time_seconds) as time_seconds,
           count(*) filter (where pa.solved) as solved_count
    from public.puzzle_attempts pa
    join public.daily_puzzles dp on dp.id = pa.puzzle_id
    join week_bounds wb on dp.date >= wb.week_start and dp.date < wb.week_start + 7
    where pa.user_id in (select id from cohort)
    group by pa.user_id
  )
  select
    u.id as user_id,
    u.display_name,
    u.avatar_emoji,
    u.avatar_color,
    coalesce(q.score, 0) + coalesce(p.score, 0) as total_score,
    coalesce(q.time_seconds, 0) + coalesce(p.time_seconds, 0) as total_time_seconds,
    coalesce(q.solved_count, 0) as questions_solved,
    coalesce(p.solved_count, 0) as puzzles_solved,
    rank() over (
      order by coalesce(q.score, 0) + coalesce(p.score, 0) desc,
               coalesce(q.time_seconds, 0) + coalesce(p.time_seconds, 0) asc
    ) as rank
  from cohort c
  join public.users u on u.id = c.id
  left join q on q.user_id = c.id
  left join p on p.user_id = c.id
  order by rank asc;
$$;

grant execute on function public.weekly_leaderboard() to authenticated;

-- ---------------------------------------------------------------------------
-- friend_activity_feed — recent completions among the caller's friends, for
-- the Home screen activity feed ("Anna solved today's puzzle in 2 guesses").
-- ---------------------------------------------------------------------------
create or replace function public.friend_activity_feed(p_limit int default 20)
returns table (
  user_id uuid,
  display_name text,
  avatar_emoji text,
  avatar_color text,
  kind text,
  solved boolean,
  guess_count int,
  time_seconds int,
  completed_at timestamptz
)
language sql
stable
security definer set search_path = public
as $$
  select u.id, u.display_name, u.avatar_emoji, u.avatar_color,
         'question' as kind, qa.solved, qa.guess_count, qa.time_seconds, qa.completed_at
  from public.question_attempts qa
  join public.users u on u.id = qa.user_id
  where qa.completed_at is not null
    and qa.user_id in (select id from public.my_friend_ids() as id)
  union all
  select u.id, u.display_name, u.avatar_emoji, u.avatar_color,
         'puzzle' as kind, pa.solved, null as guess_count, pa.time_seconds, pa.completed_at
  from public.puzzle_attempts pa
  join public.users u on u.id = pa.user_id
  where pa.completed_at is not null
    and pa.user_id in (select id from public.my_friend_ids() as id)
  order by completed_at desc
  limit p_limit;
$$;

grant execute on function public.friend_activity_feed(int) to authenticated;
