-- Närmast — initial schema
-- Daily content (questions & puzzles) resets at 00:00 UTC for every user, globally.
-- We chose a fixed UTC boundary over "midnight local time" so that the daily leaderboard,
-- friend activity feed and head-to-head comparisons are unambiguous and can be computed
-- server-side without per-user timezone math. The client still displays "today" using the
-- device's local date for copy purposes, but always fetches content for the current UTC date.
-- See lib/dateUtils.ts (`getContentDateUTC`) for the client-side implementation of this rule.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- users — one row per authenticated player, 1:1 with auth.users
-- ---------------------------------------------------------------------------
create table if not exists public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null default 'Player',
  avatar_emoji text not null default '🙂',
  avatar_color text not null default '#E4572E',
  avatar_url text,
  invite_code text not null unique,
  notification_time time not null default '09:00',
  notifications_enabled boolean not null default true,
  timezone text not null default 'UTC',
  is_premium boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.users is 'Public player profile. 1:1 with auth.users; created by handle_new_user() on signup.';

-- ---------------------------------------------------------------------------
-- daily_questions — one globally-shared numeric trivia question per UTC date
-- ---------------------------------------------------------------------------
create table if not exists public.daily_questions (
  id uuid primary key default gen_random_uuid(),
  date date not null unique,
  question_text text not null,
  answer_number numeric not null,
  unit text,
  category text not null,
  source_note text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- daily_puzzles — one globally-shared puzzle per UTC date
-- puzzle_type: 'sequence' at launch (numeric/pattern sequence completion),
-- designed so new types can be added later without a schema change.
-- ---------------------------------------------------------------------------
create table if not exists public.daily_puzzles (
  id uuid primary key default gen_random_uuid(),
  date date not null unique,
  puzzle_type text not null default 'sequence',
  title text not null,
  puzzle_data jsonb not null,
  solution jsonb not null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- question_attempts
-- ---------------------------------------------------------------------------
create table if not exists public.question_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  question_id uuid not null references public.daily_questions (id) on delete cascade,
  guesses jsonb not null default '[]'::jsonb, -- array of { value: number, direction: 'higher'|'lower'|'correct' }
  guess_count int not null default 0,
  time_seconds int not null default 0,
  solved boolean not null default false,
  score int not null default 0,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, question_id)
);

-- ---------------------------------------------------------------------------
-- puzzle_attempts
-- ---------------------------------------------------------------------------
create table if not exists public.puzzle_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  puzzle_id uuid not null references public.daily_puzzles (id) on delete cascade,
  answer jsonb,
  time_seconds int not null default 0,
  solved boolean not null default false,
  score int not null default 0,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, puzzle_id)
);

-- ---------------------------------------------------------------------------
-- friendships — directional rows; a mutual friendship is two 'accepted' rows.
-- status: 'pending' | 'accepted' | 'blocked'
-- ---------------------------------------------------------------------------
create table if not exists public.friendships (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  friend_id uuid not null references public.users (id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'accepted', 'blocked')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (user_id <> friend_id),
  unique (user_id, friend_id)
);

-- ---------------------------------------------------------------------------
-- streaks — one row per user
-- ---------------------------------------------------------------------------
create table if not exists public.streaks (
  user_id uuid primary key references public.users (id) on delete cascade,
  current_streak int not null default 0,
  longest_streak int not null default 0,
  last_completed_date date,
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- indexes
-- ---------------------------------------------------------------------------
create index if not exists idx_question_attempts_user on public.question_attempts (user_id);
create index if not exists idx_question_attempts_question on public.question_attempts (question_id);
create index if not exists idx_puzzle_attempts_user on public.puzzle_attempts (user_id);
create index if not exists idx_puzzle_attempts_puzzle on public.puzzle_attempts (puzzle_id);
create index if not exists idx_friendships_user on public.friendships (user_id, status);
create index if not exists idx_friendships_friend on public.friendships (friend_id, status);
create index if not exists idx_users_invite_code on public.users (invite_code);

-- ---------------------------------------------------------------------------
-- updated_at trigger helper
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger trg_users_updated_at
  before update on public.users
  for each row execute function public.set_updated_at();

create trigger trg_friendships_updated_at
  before update on public.friendships
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- invite code generator — 6 chars, unambiguous alphabet (no 0/O/1/I)
-- ---------------------------------------------------------------------------
create or replace function public.generate_invite_code()
returns text
language plpgsql
as $$
declare
  chars text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  code text := '';
  i int;
begin
  for i in 1..6 loop
    code := code || substr(chars, (floor(random() * length(chars)))::int + 1, 1);
  end loop;
  return code;
end;
$$;

-- ---------------------------------------------------------------------------
-- handle_new_user — creates the public.users row right after Supabase Auth
-- creates the auth.users row (Sign in with Apple / email).
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  new_code text;
  attempts int := 0;
begin
  loop
    new_code := public.generate_invite_code();
    attempts := attempts + 1;
    exit when not exists (select 1 from public.users where invite_code = new_code) or attempts > 10;
  end loop;

  insert into public.users (id, display_name, invite_code)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'display_name', 'Player'),
    new_code
  )
  on conflict (id) do nothing;

  insert into public.streaks (user_id) values (new.id)
  on conflict (user_id) do nothing;

  return new;
end;
$$;

create trigger trg_on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- recompute_streak — called after a question or puzzle attempt is completed.
-- A UTC day counts toward the streak once the user has *completed* (solved or
-- exhausted their guesses / submitted) both today's question and today's puzzle.
-- ---------------------------------------------------------------------------
create or replace function public.recompute_streak(p_user_id uuid, p_date date)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
  question_done boolean;
  puzzle_done boolean;
  prev_last date;
  prev_current int;
  prev_longest int;
  new_current int;
begin
  select exists (
    select 1 from public.question_attempts qa
    join public.daily_questions dq on dq.id = qa.question_id
    where qa.user_id = p_user_id and dq.date = p_date and qa.completed_at is not null
  ) into question_done;

  select exists (
    select 1 from public.puzzle_attempts pa
    join public.daily_puzzles dp on dp.id = pa.puzzle_id
    where pa.user_id = p_user_id and dp.date = p_date and pa.completed_at is not null
  ) into puzzle_done;

  if not (question_done and puzzle_done) then
    return; -- day isn't "complete" yet, nothing to recompute
  end if;

  select current_streak, longest_streak, last_completed_date
    into prev_current, prev_longest, prev_last
  from public.streaks where user_id = p_user_id
  for update;

  if prev_last = p_date then
    return; -- already counted today
  elsif prev_last = p_date - 1 then
    new_current := coalesce(prev_current, 0) + 1;
  else
    new_current := 1;
  end if;

  update public.streaks
  set current_streak = new_current,
      longest_streak = greatest(coalesce(prev_longest, 0), new_current),
      last_completed_date = p_date,
      updated_at = now()
  where user_id = p_user_id;
end;
$$;
