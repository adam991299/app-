import 'react-native-get-random-values';
import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { env, isSupabaseConfigured } from './env';

/**
 * A single shared Supabase client. Deliberately *not* parameterized with a generic
 * `Database` type — supabase-js's generic requires every table to declare Row/Insert/
 * Update/Relationships, which is more ceremony than this project's hand-written
 * types/database.ts needs to carry. Every call site in lib/api instead annotates its
 * own return type against types/database.ts, which stays the single source of truth
 * for the schema shape.
 *
 * When Supabase isn't configured (see lib/env.ts) this still constructs a client
 * against placeholder values so importing this module never throws — every real call
 * site goes through lib/api, which checks `isSupabaseConfigured` first and routes to
 * the local demo backend otherwise.
 */
export const supabase = createClient(
  isSupabaseConfigured ? env.supabaseUrl : 'https://placeholder.supabase.co',
  isSupabaseConfigured ? env.supabaseAnonKey : 'placeholder-anon-key',
  {
    auth: {
      storage: AsyncStorage,
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  }
);
