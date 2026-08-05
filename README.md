# Närmast

A daily number-guessing game and daily logic puzzle, with streaks and a friends
leaderboard. Built with Expo (React Native) + TypeScript, targeting iOS.

*"Närmast" is Swedish for "nearest" / "closest" — fitting for a higher/lower guessing game.*

## Play it right now, with zero setup

The app runs fully standalone out of the box: with no Supabase/RevenueCat/PostHog
environment variables set, `lib/api/*` transparently falls back to a local **demo
backend** (`lib/demo/`) seeded from the same 30 days of content used to seed the real
database. The entire game loop — questions, puzzles, streaks, a friends leaderboard
with four canned friends, sharing, the paywall UI — is playable immediately:

```bash
npm install
npm run ios     # or: npm start, then press i
```

Wire up your own Supabase/RevenueCat/PostHog projects (below) and set the matching
`EXPO_PUBLIC_*` env vars whenever you're ready to go live — no code changes needed,
`lib/api/*` switches over automatically.

## Tech stack

- **Framework:** Expo (managed workflow) + React Native 0.86, New Architecture
- **Language:** TypeScript throughout
- **Navigation:** Expo Router (file-based, `app/`)
- **Backend:** Supabase (Postgres, Auth, Row Level Security, Edge Functions)
- **State:** Zustand
- **Styling:** Plain `StyleSheet` on top of a shared design-token file
  (`constants/theme.ts`) rather than NativeWind — with a token file this small and a
  component library on top of it (`components/ui/`), this gives full TypeScript
  autocomplete on every token with one less native build dependency.
- **Animation:** React Native Reanimated **4** + Moti. (The brief mentions Reanimated
  3; SDK 57 / RN 0.86's mandatory New Architecture requires Reanimated 4 — its
  worklet-based API is functionally what "Reanimated 3" support means here.)
- **Push notifications:** Expo Notifications — currently local/scheduled only (a daily
  reminder at a user-set time). No push server is wired up yet.
- **Payments:** RevenueCat SDK (`react-native-purchases`)
- **Analytics:** PostHog (`posthog-react-native`)
- **Icons:** SF Symbols via `expo-symbols` on iOS, Lucide as the cross-platform
  fallback — see `components/ui/IconSymbol.tsx`.

This is an **iOS-first** build: `react-dom`/`react-native-web` aren't installed, and
Sign in with Apple / RevenueCat require a custom dev client or EAS build (they don't
run in Expo Go).

## Project structure

```
app/                     Expo Router screens (file-based routing)
  (onboarding)/           first-run swipeable intro + sign-in
  (auth)/                 "welcome back" re-sign-in (after sign-out)
  (tabs)/                 Home, Friends, Profile
  play/                   question & puzzle gameplay
  results/                per-game results + combined day summary
  friends/                add friend, head-to-head
  profile-setup.tsx, settings.tsx, paywall.tsx, archive.tsx, challenge.tsx
components/               ui/ (design-system primitives), game/, share/, charts/, ...
constants/theme.ts        design tokens: color, type scale, spacing, radius, shadow, motion
lib/
  api/                     data layer — talks to Supabase, or falls back to demo mode
  demo/                    local demo backend (AsyncStorage-backed)
  supabase.ts, revenuecat.ts, notifications.ts, analytics.ts, share.ts, ...
store/                    Zustand stores (auth, settings, game)
supabase/
  migrations/              SQL schema, RLS, RPCs (run in order, 0001 → 0008)
  seed/                    30 days of starter content + bulk import script
  functions/               Edge Functions (content pipeline, RevenueCat webhook, delete account)
```

## Running against a real Supabase project

1. Create a project at [supabase.com](https://supabase.com).
2. Run the migrations in `supabase/migrations/` **in order** — either paste each file
   into the SQL Editor, or with the Supabase CLI:
   ```bash
   supabase link --project-ref <your-project-ref>
   supabase db push
   ```
3. Seed 30 days of starter content so the app isn't empty on launch:
   ```bash
   SUPABASE_URL=https://<ref>.supabase.co \
   SUPABASE_SERVICE_ROLE_KEY=<service-role-key> \
   npm run seed
   ```
4. Deploy the Edge Functions:
   ```bash
   supabase functions deploy generate-daily-content --no-verify-jwt
   supabase functions deploy revenuecat-webhook --no-verify-jwt
   supabase functions deploy delete-account
   supabase secrets set ADMIN_CONTENT_SECRET=<a-long-random-string>
   supabase secrets set REVENUECAT_WEBHOOK_SECRET=<matches what you set in RevenueCat>
   ```
5. Copy `.env.example` to `.env` and fill in `EXPO_PUBLIC_SUPABASE_URL` /
   `EXPO_PUBLIC_SUPABASE_ANON_KEY` from Project → Settings → API.
6. In Supabase Auth settings, enable the **Apple** provider (Sign in with Apple) and
   the **Email OTP** flow.

### Content pipeline (keeping the app stocked with new days)

`npm run seed` bulk-imports the initial 30 days. After that, push one day at a time
with the `generate-daily-content` Edge Function:

```bash
curl -X POST https://<ref>.functions.supabase.co/generate-daily-content \
  -H "x-admin-secret: <ADMIN_CONTENT_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-09-04",
    "question": { "question_text": "...", "answer_number": 1869, "category": "history", "source_note": "..." },
    "puzzle": { "title": "...", "puzzle_data": { "sequence": [3,7,11,15,null] }, "solution": { "values": [19] } }
  }'
```

### Security model, briefly

- **RLS everywhere.** Users can only read/write their own attempt data; friends' data
  is readable only once a `friendships` row is `accepted`.
- **Answers/solutions are never sent to the client early.** Column-level `GRANT`s
  (`0006_column_privileges.sql`) hide `daily_questions.answer_number` and
  `daily_puzzles.solution` from direct client reads. Guessing goes through
  `submit_question_guess` / `submit_puzzle_attempt`, `SECURITY DEFINER` RPCs that
  validate server-side and reveal the answer/solution only once an attempt is
  actually finished (`get_revealed_answer` / `get_revealed_solution`).
- **Scores are computed server-side**, never trusted from the client, so the
  leaderboard can't be gamed by a modified client.
- **`is_premium` is not client-writable at all** (`0008_users_column_privileges.sql`)
  — the only writer is the `revenuecat-webhook` Edge Function, invoked server-to-server
  by RevenueCat and checked against a shared secret.

## RevenueCat setup

1. Create a RevenueCat project, add your iOS app, and set up **monthly** and
   **yearly** subscription products with an entitlement called `premium` (this
   identifier is hardcoded as `PREMIUM_ENTITLEMENT_ID` in `lib/revenuecat.ts`).
2. Copy your iOS API key into `EXPO_PUBLIC_REVENUECAT_API_KEY_IOS`.
3. Add a webhook (Project Settings → Integrations → Webhooks) pointing at your
   deployed `revenuecat-webhook` function URL, with an Authorization header value —
   set that same value as the `REVENUECAT_WEBHOOK_SECRET` Supabase secret (see above).
4. Sandbox-test with a [Sandbox Apple ID](https://developer.apple.com/apple-pay/sandbox-testing/)
   on a real device or simulator via a development build (RevenueCat doesn't work in
   Expo Go — see "Building for a device" below).

## PostHog (optional)

Set `EXPO_PUBLIC_POSTHOG_API_KEY` (and `EXPO_PUBLIC_POSTHOG_HOST` if self-hosting).
Event names are centralized in `lib/analytics.ts`. Without a key, `track()` calls are
silent no-ops.

## Building for a device / EAS Build

Sign in with Apple, RevenueCat, and Apple contacts access all require native code that
isn't present in Expo Go, so you need a development build or an EAS build to test the
full app on a device:

```bash
npx eas-cli login
npx eas-cli init                      # creates your EAS project, fills in EAS_PROJECT_ID
npx eas-cli build --profile development --platform ios   # dev client, for local testing
npx eas-cli build --profile production --platform ios    # release build
```

`eas.json` has `development` (dev client), `preview` (internal TestFlight-style
distribution) and `production` profiles.

### Submitting to the App Store

```bash
npm run build:ios     # eas build --platform ios --profile production
npm run submit:ios     # eas submit --platform ios --latest
```

Fill in your Apple ID / App Store Connect app ID / team ID in `eas.json`'s `submit`
section first. Before submitting, also:

- Replace the placeholder icon/splash assets in `assets/` with real artwork.
- Finalize `PRIVACY_POLICY.md` and `TERMS.md` (they're scaffolds — see the notice at
  the top of each) and host them at the URLs referenced in `app/paywall.tsx` and
  `app/settings.tsx` (currently `https://narmast.app/privacy` and `/terms`).
- Double-check the permission strings in `app.config.ts` still match what the app
  actually does.

## Known scope decisions worth knowing about

- **Daily reset is a fixed 00:00 UTC boundary**, not local midnight — see the comment
  in `supabase/migrations/0001_init.sql` and `lib/dateUtils.ts` for why (it's what
  makes the weekly leaderboard and friend comparisons well-defined without per-user
  timezone math).
- **Contact sync invites rather than auto-matches.** We don't collect phone numbers
  anywhere in the schema, so "contact sync" (`app/friends/add.tsx`) requests contacts
  permission and lets you invite people from your address book via the share sheet —
  it doesn't silently detect which contacts already have accounts, since that would
  require a phone-number-matching backend this build doesn't include.
- **The archive is browse-only in this build** (`app/archive.tsx`) — it shows past
  content and your attempt status, but doesn't yet let you play a missed day for
  score/streak credit. The `play/*` screens are wired to "today" via `useGameStore`;
  parameterizing them to accept an arbitrary date is a natural next step.
- **Notifications are local only.** "Push notifications" in the brief is implemented
  as a scheduled local notification (`expo-notifications`), configurable per user —
  there's no push-notification server component.

## Typecheck / sanity

```bash
npm run typecheck   # tsc --noEmit
npx expo export -p ios   # full Metro bundle, catches import/runtime issues tsc won't
```
