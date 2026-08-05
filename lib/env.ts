/**
 * Central place to read build-time config. Expo inlines any `EXPO_PUBLIC_*` variable
 * from `.env` (see `.env.example`) into the JS bundle at build time — see
 * https://docs.expo.dev/versions/v57.0.0/guides/environment-variables/.
 *
 * If Supabase isn't configured yet, the app deliberately falls back to a fully
 * functional local "demo mode" (lib/demo) instead of crashing — see
 * lib/api/index.ts. That keeps the whole game loop runnable and screenshot-able
 * with zero setup, which matters for reviewing this project before you've wired up
 * your own Supabase/RevenueCat/PostHog projects.
 */

export const env = {
  supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL ?? '',
  supabaseAnonKey: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '',
  revenueCatApiKeyIOS: process.env.EXPO_PUBLIC_REVENUECAT_API_KEY_IOS ?? '',
  posthogApiKey: process.env.EXPO_PUBLIC_POSTHOG_API_KEY ?? '',
  posthogHost: process.env.EXPO_PUBLIC_POSTHOG_HOST ?? 'https://us.i.posthog.com',
};

export const isSupabaseConfigured = Boolean(env.supabaseUrl && env.supabaseAnonKey);
export const isRevenueCatConfigured = Boolean(env.revenueCatApiKeyIOS);
export const isPostHogConfigured = Boolean(env.posthogApiKey);
