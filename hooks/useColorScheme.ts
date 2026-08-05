import { useColorScheme as useSystemColorScheme } from 'react-native';
import { useSettingsStore } from '@/store/useSettingsStore';
import type { ColorScheme } from '@/constants/theme';

/** Resolves the effective color scheme: the user's explicit light/dark override, or
 * the system setting when they've chosen "system" (the default). */
export function useColorScheme(): ColorScheme {
  const preference = useSettingsStore((s) => s.themePreference);
  const system = useSystemColorScheme();
  if (preference === 'system') return system === 'dark' ? 'dark' : 'light';
  return preference;
}
