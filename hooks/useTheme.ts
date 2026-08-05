import { useMemo } from 'react';
import { getShadows, themes, type ColorScheme, type ThemeColors } from '@/constants/theme';
import { useColorScheme } from './useColorScheme';

export interface Theme {
  scheme: ColorScheme;
  colors: ThemeColors;
  shadows: ReturnType<typeof getShadows>;
  isDark: boolean;
}

export function useTheme(): Theme {
  const scheme = useColorScheme();
  return useMemo(
    () => ({
      scheme,
      colors: themes[scheme],
      shadows: getShadows(scheme),
      isDark: scheme === 'dark',
    }),
    [scheme]
  );
}
