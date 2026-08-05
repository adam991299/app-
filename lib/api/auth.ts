import * as AppleAuthentication from 'expo-apple-authentication';
import { Platform } from 'react-native';
import type { Session } from '@supabase/supabase-js';
import { ensureDemoProfile, resetDemoState } from '@/lib/demo/store';
import { isSupabaseConfigured } from '@/lib/env';
import { supabase } from '@/lib/supabase';

export async function getSession(): Promise<Session | null> {
  if (!isSupabaseConfigured) return null;
  const { data } = await supabase.auth.getSession();
  return data.session;
}

export function onAuthStateChange(callback: (session: Session | null) => void) {
  if (!isSupabaseConfigured) {
    return { data: { subscription: { unsubscribe() {} } } };
  }
  return supabase.auth.onAuthStateChange((_event, session) => callback(session));
}

export async function isAppleSignInAvailable(): Promise<boolean> {
  if (Platform.OS !== 'ios') return false;
  return AppleAuthentication.isAvailableAsync();
}

/** Sign in (or register — Apple returns the same flow for both) with Apple. */
export async function signInWithApple(): Promise<void> {
  if (!isSupabaseConfigured) {
    await ensureDemoProfile();
    return;
  }

  const credential = await AppleAuthentication.signInAsync({
    requestedScopes: [
      AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
      AppleAuthentication.AppleAuthenticationScope.EMAIL,
    ],
  });

  if (!credential.identityToken) {
    throw new Error('Apple Sign In did not return an identity token.');
  }

  const { data, error } = await supabase.auth.signInWithIdToken({
    provider: 'apple',
    token: credential.identityToken,
  });
  if (error) throw error;

  // Apple only ever provides the user's name on the very first authorization. If we
  // got one, seed display_name now — the handle_new_user() trigger otherwise defaults
  // to "Player".
  const givenName = credential.fullName?.givenName;
  if (givenName && data.user) {
    await supabase.from('users').update({ display_name: givenName }).eq('id', data.user.id);
  }
}

export async function signInWithEmailOtp(email: string): Promise<void> {
  if (!isSupabaseConfigured) {
    throw new Error('Email sign-in needs a configured Supabase project.');
  }
  const { error } = await supabase.auth.signInWithOtp({ email });
  if (error) throw error;
}

export async function verifyEmailOtp(email: string, token: string): Promise<void> {
  if (!isSupabaseConfigured) {
    throw new Error('Email sign-in needs a configured Supabase project.');
  }
  const { error } = await supabase.auth.verifyOtp({ email, token, type: 'email' });
  if (error) throw error;
}

export async function signOut(): Promise<void> {
  if (!isSupabaseConfigured) {
    await resetDemoState();
    return;
  }
  await supabase.auth.signOut();
}

/** Calls the delete-account Edge Function (runs with the service role to actually
 * remove the auth.users row, which cascades to every table via FK on delete cascade),
 * then signs out locally. */
export async function deleteAccount(): Promise<void> {
  if (!isSupabaseConfigured) {
    await resetDemoState();
    return;
  }
  const { error } = await supabase.functions.invoke('delete-account');
  if (error) throw error;
  await supabase.auth.signOut();
}
