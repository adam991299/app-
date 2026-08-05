import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export type ThemePreference = 'system' | 'light' | 'dark';

interface SettingsState {
  themePreference: ThemePreference;
  hasCompletedOnboarding: boolean;
  /** True once the persisted value has been read back from AsyncStorage — gates the
   * root layout's routing decision so we never flash onboarding for a returning user. */
  hasHydrated: boolean;
  setThemePreference: (pref: ThemePreference) => void;
  completeOnboarding: () => void;
  _setHasHydrated: () => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      themePreference: 'system',
      hasCompletedOnboarding: false,
      hasHydrated: false,
      setThemePreference: (themePreference) => set({ themePreference }),
      completeOnboarding: () => set({ hasCompletedOnboarding: true }),
      _setHasHydrated: () => set({ hasHydrated: true }),
    }),
    {
      name: 'narmast.settings',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        themePreference: state.themePreference,
        hasCompletedOnboarding: state.hasCompletedOnboarding,
      }),
      onRehydrateStorage: () => (state) => {
        state?._setHasHydrated();
      },
    }
  )
);
