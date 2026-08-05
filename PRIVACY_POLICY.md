# Privacy Policy

**Last updated:** [DATE]

> **This is a scaffold, not finished legal text.** It's written to accurately describe
> what the Närmast app in this repository actually collects and does today, so you have
> an honest starting point — but it hasn't been reviewed by a lawyer. Fill in every
> `[BRACKETED]` placeholder and have it reviewed before shipping to the App Store.

Närmast ("**we**", "**us**") makes this Privacy Policy available to explain what
information the Närmast app ("**the App**") collects, how it's used, and the choices
you have.

## Information we collect

**Account information.** When you sign in with Apple, we receive your Apple-provided
user identifier and, if you choose to share it, your name and email address (which may
be a private Apple relay address). If you sign in with email instead, we collect the
email address you provide. We store your chosen **display name** and **avatar**
(an emoji + color, not a photo) as shown to friends on the leaderboard.

**Gameplay data.** We store your daily question and puzzle attempts (guesses made,
whether you solved it, time taken), your streak, and your weekly score, so the app can
show your stats and leaderboard standing.

**Friends.** If you add a friend by invite code, we store that connection so you can
see each other's activity and compare streaks. If you use "Find contacts to invite,"
your device contacts are read **on-device only** — inviting a contact opens the native
share sheet with a message you control; we never upload or store your contact list.

**Purchase information.** Subscription purchases are processed by Apple and RevenueCat.
We receive confirmation of your subscription status (active/expired) but never your
payment details.

**Analytics.** We use PostHog to understand product usage (e.g. which screens are
visited, whether the daily loop is completed) — see "Analytics" below for what we do
and don't send.

**Notifications.** If you enable the daily reminder, your device's local notification
permission is used to schedule a reminder at the time you choose. This is a local
notification — Närmast does not currently operate a push notification server.

## How we use this information

- To operate the core game loop, streaks, and leaderboard.
- To personalize the app with your display name and avatar.
- To process and validate subscription purchases via RevenueCat.
- To understand aggregate product usage and improve the app.
- To respond to support requests.

We do not sell your personal information, and we do not use your data for third-party
advertising.

## Third-party services

| Service | Purpose | What it receives |
|---|---|---|
| Supabase | Database, authentication, backend logic | Account info, gameplay data (see above) |
| Apple (Sign in with Apple) | Authentication | Apple user identifier, optionally name/email |
| RevenueCat | Subscription management | Purchase/subscription status, an anonymous or Supabase-derived user identifier |
| PostHog | Product analytics | Anonymized usage events — see below |

Each of these providers has its own privacy policy governing how they handle data on
our behalf: [Supabase](https://supabase.com/privacy), [Apple](https://www.apple.com/legal/privacy/),
[RevenueCat](https://www.revenuecat.com/privacy), [PostHog](https://posthog.com/privacy).

## Analytics

Analytics events (see `lib/analytics.ts`) are limited to product-usage events — e.g.
"question started," "puzzle completed," "paywall viewed" — tagged with your user ID
so we can measure retention. We do not send the *content* of your guesses, your
friends' identities, or your contacts to our analytics provider.

## Your choices

- **Notifications** can be turned off at any time in Settings.
- **Contacts access** is optional and can be denied or revoked in iOS Settings without
  affecting core functionality.
- **Delete your account** at any time from Settings → Delete Account. This permanently
  removes your profile, streak, attempt history, and friend connections. This action
  cannot be undone.
- **Restore purchases** and manage or cancel your subscription any time via
  Settings → Apple ID → Subscriptions on your device.

## Data retention

We retain your account and gameplay data for as long as your account is active.
Deleting your account permanently removes this data from our production database
within [X days], except where retained longer to comply with legal obligations.

## Children's privacy

Närmast is not directed at children under 13 (or the relevant age of digital consent
in your jurisdiction), and we do not knowingly collect personal information from them.

## Changes to this policy

We may update this policy from time to time. Material changes will be reflected here
with an updated "Last updated" date, and, where required, notified in-app.

## Contact us

[COMPANY NAME]
[ADDRESS]
[SUPPORT EMAIL]
