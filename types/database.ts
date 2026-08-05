/**
 * Hand-written types mirroring supabase/migrations/*.sql. If you have the Supabase CLI
 * linked, you can regenerate an authoritative version with:
 *   supabase gen types typescript --linked > types/database.ts
 */

export interface UserRow {
  id: string;
  display_name: string;
  avatar_emoji: string;
  avatar_color: string;
  avatar_url: string | null;
  invite_code: string;
  notification_time: string; // "HH:MM:SS"
  notifications_enabled: boolean;
  timezone: string;
  is_premium: boolean;
  created_at: string;
  updated_at: string;
}

export interface DailyQuestionRow {
  id: string;
  date: string; // YYYY-MM-DD
  question_text: string;
  answer_number: number;
  unit: string | null;
  category: string;
  source_note: string | null;
  created_at: string;
}

export type PuzzleType = 'sequence';

export interface SequencePuzzleData {
  sequence: (number | null)[];
}

export interface SequencePuzzleSolution {
  values: number[];
}

export interface DailyPuzzleRow {
  id: string;
  date: string;
  puzzle_type: PuzzleType;
  title: string;
  puzzle_data: SequencePuzzleData;
  solution: SequencePuzzleSolution;
  created_at: string;
}

export interface QuestionGuess {
  value: number;
  direction: 'higher' | 'lower' | 'correct';
}

export interface QuestionAttemptRow {
  id: string;
  user_id: string;
  question_id: string;
  guesses: QuestionGuess[];
  guess_count: number;
  time_seconds: number;
  solved: boolean;
  score: number;
  completed_at: string | null;
  created_at: string;
}

export interface PuzzleAttemptRow {
  id: string;
  user_id: string;
  puzzle_id: string;
  answer: SequencePuzzleSolution | null;
  time_seconds: number;
  solved: boolean;
  score: number;
  completed_at: string | null;
  created_at: string;
}

export type FriendshipStatus = 'pending' | 'accepted' | 'blocked';

export interface FriendshipRow {
  id: string;
  user_id: string;
  friend_id: string;
  status: FriendshipStatus;
  created_at: string;
  updated_at: string;
}

export interface StreakRow {
  user_id: string;
  current_streak: number;
  longest_streak: number;
  last_completed_date: string | null;
  updated_at: string;
}

export interface WeeklyLeaderboardRow {
  user_id: string;
  display_name: string;
  avatar_emoji: string;
  avatar_color: string;
  total_score: number;
  total_time_seconds: number;
  questions_solved: number;
  puzzles_solved: number;
  rank: number;
}

export interface FriendActivityRow {
  user_id: string;
  display_name: string;
  avatar_emoji: string;
  avatar_color: string;
  kind: 'question' | 'puzzle';
  solved: boolean;
  guess_count: number | null;
  time_seconds: number;
  completed_at: string;
}

export interface FindUserByCodeRow {
  id: string;
  display_name: string;
  avatar_emoji: string;
  avatar_color: string;
}

export interface QuestionGuessResult {
  guess_count: number;
  direction: 'higher' | 'lower' | 'correct';
  solved: boolean;
  is_final: boolean;
  answer_number: number | null;
  score: number;
  completed_at: string | null;
}

export interface PuzzleAttemptResult {
  solved: boolean;
  score: number;
  solution: SequencePuzzleSolution;
  completed_at: string;
}

/** Client-safe projections — the columns 0006_column_privileges.sql actually grants. */
export type PublicDailyQuestion = Pick<
  DailyQuestionRow,
  'id' | 'date' | 'question_text' | 'unit' | 'category' | 'source_note' | 'created_at'
>;

export type PublicDailyPuzzle = Pick<
  DailyPuzzleRow,
  'id' | 'date' | 'puzzle_type' | 'title' | 'puzzle_data' | 'created_at'
>;

/** Minimal typed surface of the schema, enough to keep supabase-js calls type-safe. */
export interface Database {
  public: {
    Tables: {
      users: { Row: UserRow };
      daily_questions: { Row: DailyQuestionRow };
      daily_puzzles: { Row: DailyPuzzleRow };
      question_attempts: { Row: QuestionAttemptRow };
      puzzle_attempts: { Row: PuzzleAttemptRow };
      friendships: { Row: FriendshipRow };
      streaks: { Row: StreakRow };
    };
    Functions: {
      find_user_by_invite_code: { Args: { p_code: string }; Returns: FindUserByCodeRow[] };
      add_friend_by_code: { Args: { p_code: string }; Returns: UserRow };
      weekly_leaderboard: { Args: Record<string, never>; Returns: WeeklyLeaderboardRow[] };
      friend_activity_feed: { Args: { p_limit?: number }; Returns: FriendActivityRow[] };
      submit_question_guess: {
        Args: { p_question_id: string; p_value: number; p_time_seconds: number };
        Returns: QuestionGuessResult;
      };
      submit_puzzle_attempt: {
        Args: { p_puzzle_id: string; p_answer: SequencePuzzleSolution; p_time_seconds: number };
        Returns: PuzzleAttemptResult;
      };
      get_revealed_answer: { Args: { p_question_id: string }; Returns: number };
      get_revealed_solution: { Args: { p_puzzle_id: string }; Returns: SequencePuzzleSolution };
    };
  };
}
