import PostHog from 'posthog-react-native';
import { env, isPostHogConfigured } from './env';

/**
 * Lightweight, privacy-respecting analytics. We only track product-usage events
 * needed to understand retention and the core loop (never gameplay *content*, never
 * contact-sync data). If PostHog isn't configured this becomes a no-op so the app
 * never depends on analytics being present.
 */
export const posthog = isPostHogConfigured
  ? new PostHog(env.posthogApiKey, {
      host: env.posthogHost,
      captureAppLifecycleEvents: true,
    })
  : null;

/** Central list of event names so call sites can't typo a name that silently drops. */
export const AnalyticsEvent = {
  OnboardingCompleted: 'onboarding_completed',
  SignedIn: 'signed_in',
  SignedOut: 'signed_out',
  QuestionStarted: 'question_started',
  QuestionGuessSubmitted: 'question_guess_submitted',
  QuestionCompleted: 'question_completed',
  PuzzleStarted: 'puzzle_started',
  PuzzleCompleted: 'puzzle_completed',
  ShareCardGenerated: 'share_card_generated',
  ShareSheetOpened: 'share_sheet_opened',
  FriendAdded: 'friend_added',
  PaywallViewed: 'paywall_viewed',
  PaywallPurchaseStarted: 'paywall_purchase_started',
  PaywallPurchaseCompleted: 'paywall_purchase_completed',
  PaywallRestoreTapped: 'paywall_restore_tapped',
  NotificationTimeChanged: 'notification_time_changed',
} as const;

export type AnalyticsEventName = (typeof AnalyticsEvent)[keyof typeof AnalyticsEvent];

type JsonProperties = Record<string, string | number | boolean | null>;

export function track(event: AnalyticsEventName, properties?: JsonProperties): void {
  posthog?.capture(event, properties);
}

export function identifyUser(userId: string, traits?: JsonProperties): void {
  posthog?.identify(userId, traits);
}

export function resetAnalyticsIdentity(): void {
  posthog?.reset();
}
