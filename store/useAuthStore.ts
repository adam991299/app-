import { create } from 'zustand';
import { deleteAccount as apiDeleteAccount, getSession, onAuthStateChange, signInWithApple, signOut as apiSignOut } from '@/lib/api/auth';
import { addPremiumStatusListener, configurePurchases, logOutPurchases } from '@/lib/revenuecat';
import { getMyProfile, updateProfile, type ProfilePatch } from '@/lib/api/profile';
import { identifyUser, resetAnalyticsIdentity } from '@/lib/analytics';
import { isSupabaseConfigured } from '@/lib/env';
import type { UserRow } from '@/types/database';

export type AuthStatus = 'loading' | 'signedOut' | 'signedIn';

interface AuthState {
  status: AuthStatus;
  profile: UserRow | null;
  /** True right after a brand-new account's first sign-in — display_name is still the
   * server default, so onboarding should show the "pick a name & avatar" step. */
  needsProfileSetup: boolean;
  bootstrap: () => Promise<void>;
  signInApple: () => Promise<void>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  saveProfileSetup: (patch: ProfilePatch) => Promise<void>;
}

let subscribed = false;
let premiumListenerAttached = false;

export const useAuthStore = create<AuthState>()((set, get) => ({
  status: 'loading',
  profile: null,
  needsProfileSetup: false,

  bootstrap: async () => {
    const session = isSupabaseConfigured ? await getSession() : null;
    const hasIdentity = isSupabaseConfigured ? Boolean(session) : await hasDemoIdentity();

    if (!hasIdentity) {
      set({ status: 'signedOut', profile: null });
    } else {
      await get().refreshProfile();
    }

    if (!subscribed) {
      subscribed = true;
      onAuthStateChange((session) => {
        if (session) {
          get().refreshProfile();
        } else {
          set({ status: 'signedOut', profile: null });
        }
      });
    }
  },

  signInApple: async () => {
    await signInWithApple();
    await get().refreshProfile();
  },

  signOut: async () => {
    await apiSignOut();
    await logOutPurchases();
    resetAnalyticsIdentity();
    set({ status: 'signedOut', profile: null, needsProfileSetup: false });
  },

  deleteAccount: async () => {
    await apiDeleteAccount();
    resetAnalyticsIdentity();
    set({ status: 'signedOut', profile: null, needsProfileSetup: false });
  },

  refreshProfile: async () => {
    try {
      const profile = await getMyProfile();
      identifyUser(profile.id, { display_name: profile.display_name });
      await configurePurchases(profile.id);
      set({
        status: 'signedIn',
        profile,
        needsProfileSetup: profile.display_name === 'Player',
      });

      if (!premiumListenerAttached) {
        premiumListenerAttached = true;
        // RevenueCat's local cache updates instantly on purchase/restore; the DB's
        // is_premium (the actual gate — see 0008_users_column_privileges.sql) catches
        // up shortly after via the revenuecat-webhook Edge Function. Nudge a re-fetch
        // so the UI doesn't feel stuck waiting on the webhook round trip.
        addPremiumStatusListener(() => {
          setTimeout(() => get().refreshProfile(), 1500);
        });
      }
    } catch {
      set({ status: 'signedOut', profile: null });
    }
  },

  saveProfileSetup: async (patch) => {
    const profile = await updateProfile(patch);
    set({ profile, needsProfileSetup: false });
  },
}));

async function hasDemoIdentity(): Promise<boolean> {
  const { getDemoState } = await import('@/lib/demo/store');
  const state = await getDemoState();
  return Boolean(state.profile);
}
