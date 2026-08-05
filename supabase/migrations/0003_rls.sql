-- Row Level Security — users can only read/write their own attempt data, but can read
-- aggregate/leaderboard-relevant data for their accepted friends.

alter table public.users enable row level security;
alter table public.daily_questions enable row level security;
alter table public.daily_puzzles enable row level security;
alter table public.question_attempts enable row level security;
alter table public.puzzle_attempts enable row level security;
alter table public.friendships enable row level security;
alter table public.streaks enable row level security;

-- Helper: are two users friends (accepted, either direction)?
create or replace function public.are_friends(a uuid, b uuid)
returns boolean
language sql
stable
security definer set search_path = public
as $$
  select exists (
    select 1 from public.friendships
    where status = 'accepted'
      and ((user_id = a and friend_id = b) or (user_id = b and friend_id = a))
  );
$$;

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
create policy "users can read own profile"
  on public.users for select
  using (id = auth.uid());

create policy "users can read friends' profiles"
  on public.users for select
  using (public.are_friends(auth.uid(), id));

create policy "users can update own profile"
  on public.users for update
  using (id = auth.uid())
  with check (id = auth.uid());

create policy "users can delete own profile"
  on public.users for delete
  using (id = auth.uid());

-- ---------------------------------------------------------------------------
-- daily_questions / daily_puzzles
-- Today's content is free for everyone. Past dates (the archive) require
-- is_premium = true — enforced here, not just in the client paywall UI.
-- ---------------------------------------------------------------------------
create policy "today's question is free, archive requires premium"
  on public.daily_questions for select
  using (
    date = (now() at time zone 'utc')::date
    or exists (select 1 from public.users u where u.id = auth.uid() and u.is_premium)
  );

create policy "today's puzzle is free, archive requires premium"
  on public.daily_puzzles for select
  using (
    date = (now() at time zone 'utc')::date
    or exists (select 1 from public.users u where u.id = auth.uid() and u.is_premium)
  );

-- ---------------------------------------------------------------------------
-- question_attempts / puzzle_attempts
-- Read-only from the client's perspective: rows are written exclusively through
-- the security-definer submit_question_attempt / submit_puzzle_attempt RPCs
-- (see 0005_submit_rpc.sql), which compute the score server-side. There is no
-- insert/update policy here on purpose — the client cannot write these tables
-- directly, so it can't submit a fabricated score to the leaderboard.
-- ---------------------------------------------------------------------------
create policy "users read own question attempts"
  on public.question_attempts for select
  using (user_id = auth.uid());

create policy "users read friends' question attempts"
  on public.question_attempts for select
  using (public.are_friends(auth.uid(), user_id));

create policy "users read own puzzle attempts"
  on public.puzzle_attempts for select
  using (user_id = auth.uid());

create policy "users read friends' puzzle attempts"
  on public.puzzle_attempts for select
  using (public.are_friends(auth.uid(), user_id));

-- ---------------------------------------------------------------------------
-- friendships
-- ---------------------------------------------------------------------------
create policy "users read friendships they're party to"
  on public.friendships for select
  using (user_id = auth.uid() or friend_id = auth.uid());

create policy "users create outgoing friend requests"
  on public.friendships for insert
  with check (user_id = auth.uid());

create policy "users update friendships they're party to"
  on public.friendships for update
  using (user_id = auth.uid() or friend_id = auth.uid())
  with check (user_id = auth.uid() or friend_id = auth.uid());

create policy "users delete friendships they're party to"
  on public.friendships for delete
  using (user_id = auth.uid() or friend_id = auth.uid());

-- ---------------------------------------------------------------------------
-- streaks
-- ---------------------------------------------------------------------------
create policy "users read own streak"
  on public.streaks for select
  using (user_id = auth.uid());

create policy "users read friends' streaks"
  on public.streaks for select
  using (public.are_friends(auth.uid(), user_id));

-- streaks are written only by the security-definer recompute_streak() function,
-- which runs with elevated privileges — no direct client write policy is granted.
