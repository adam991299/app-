/**
 * Närmast design tokens.
 *
 * One shared source of truth for color, type, spacing, radius and elevation so every
 * screen stays visually consistent. Styling throughout the app is plain StyleSheet
 * built on top of these tokens (see components/ui) rather than NativeWind — with a
 * design-token file this small and a component library on top of it, StyleSheet gives
 * us full TypeScript autocomplete on every token and one less native build dependency,
 * with no real loss of expressiveness.
 */
import { Platform } from 'react-native';

// ---------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------

/** Warm coral — Närmast's accent. Deliberately not the default iOS blue. */
const coral = {
  50: '#FFF1EC',
  100: '#FFE0D5',
  200: '#FFC1AC',
  300: '#FF9C7D',
  400: '#F17A54',
  500: '#E4572E', // primary
  600: '#C8451F',
  700: '#A33718',
  800: '#7E2B14',
  900: '#5C2010',
};

/** Deep teal — secondary accent used sparingly for links / secondary CTAs. */
const teal = {
  100: '#D8F3EE',
  300: '#7FCFC0',
  500: '#2A9D8F',
  700: '#1D6E64',
};

const warmNeutral = {
  0: '#FFFFFF',
  25: '#FFFDF9',
  50: '#FBF7F1',
  100: '#F4EDE3',
  200: '#E7DDD0',
  300: '#D6C9B8',
  400: '#B0A28E',
  500: '#8A7D6B',
  600: '#6B6052',
  700: '#4D453A',
  800: '#332D25',
  900: '#211D17',
  950: '#161512',
  1000: '#0D0C0A',
};

const semantic = {
  success: '#2F9E5B',
  successBg: '#E4F5EA',
  warning: '#D68A1E',
  warningBg: '#FBF0DC',
  error: '#D64545',
  errorBg: '#FAE4E4',
};

export const palette = { coral, teal, warmNeutral, semantic };

// ---------------------------------------------------------------------------
// Light / dark themes
// ---------------------------------------------------------------------------

export type ColorScheme = 'light' | 'dark';

export interface ThemeColors {
  background: string;
  backgroundSecondary: string;
  card: string;
  cardElevated: string;
  border: string;
  borderSubtle: string;
  text: string;
  textSecondary: string;
  textTertiary: string;
  inverseText: string;
  accent: string;
  accentPressed: string;
  onAccent: string;
  accentSoft: string;
  secondaryAccent: string;
  secondaryAccentSoft: string;
  success: string;
  successSoft: string;
  warning: string;
  warningSoft: string;
  error: string;
  errorSoft: string;
  overlay: string;
  skeleton: string;
  tabBarBackground: string;
}

const light: ThemeColors = {
  background: warmNeutral[25],
  backgroundSecondary: warmNeutral[50],
  card: warmNeutral[0],
  cardElevated: warmNeutral[0],
  border: warmNeutral[200],
  borderSubtle: warmNeutral[100],
  text: warmNeutral[900],
  textSecondary: warmNeutral[600],
  textTertiary: warmNeutral[500],
  inverseText: warmNeutral[0],
  accent: coral[500],
  accentPressed: coral[600],
  onAccent: warmNeutral[0],
  accentSoft: coral[50],
  secondaryAccent: teal[500],
  secondaryAccentSoft: teal[100],
  success: semantic.success,
  successSoft: semantic.successBg,
  warning: semantic.warning,
  warningSoft: semantic.warningBg,
  error: semantic.error,
  errorSoft: semantic.errorBg,
  overlay: 'rgba(33,29,23,0.45)',
  skeleton: warmNeutral[100],
  tabBarBackground: 'rgba(255,253,249,0.8)',
};

const dark: ThemeColors = {
  background: warmNeutral[950],
  backgroundSecondary: warmNeutral[900],
  card: warmNeutral[900],
  cardElevated: '#2A2620',
  border: warmNeutral[800],
  borderSubtle: '#241F1A',
  text: warmNeutral[50],
  textSecondary: warmNeutral[300],
  textTertiary: warmNeutral[400],
  inverseText: warmNeutral[950],
  accent: coral[400],
  accentPressed: coral[300],
  onAccent: warmNeutral[950],
  accentSoft: 'rgba(228,87,46,0.16)',
  secondaryAccent: teal[300],
  secondaryAccentSoft: 'rgba(42,157,143,0.18)',
  success: '#4CB578',
  successSoft: 'rgba(47,158,91,0.16)',
  warning: '#E4A63D',
  warningSoft: 'rgba(214,138,30,0.16)',
  error: '#E5726B',
  errorSoft: 'rgba(214,69,69,0.18)',
  overlay: 'rgba(0,0,0,0.6)',
  skeleton: '#241F1A',
  tabBarBackground: 'rgba(22,21,18,0.75)',
};

export const themes: Record<ColorScheme, ThemeColors> = { light, dark };

// ---------------------------------------------------------------------------
// Typography — matches the iOS type scale (SF Pro / system font)
// ---------------------------------------------------------------------------

export interface TypeStyle {
  fontSize: number;
  lineHeight: number;
  fontWeight: '400' | '500' | '600' | '700';
  letterSpacing?: number;
}

export const typography: Record<string, TypeStyle> = {
  largeTitle: { fontSize: 34, lineHeight: 41, fontWeight: '700', letterSpacing: 0.37 },
  title1: { fontSize: 28, lineHeight: 34, fontWeight: '700', letterSpacing: 0.36 },
  title2: { fontSize: 22, lineHeight: 28, fontWeight: '700', letterSpacing: 0.35 },
  title3: { fontSize: 20, lineHeight: 25, fontWeight: '600', letterSpacing: 0.38 },
  headline: { fontSize: 17, lineHeight: 22, fontWeight: '600', letterSpacing: -0.41 },
  body: { fontSize: 17, lineHeight: 22, fontWeight: '400', letterSpacing: -0.41 },
  bodyEmphasized: { fontSize: 17, lineHeight: 22, fontWeight: '600', letterSpacing: -0.41 },
  callout: { fontSize: 16, lineHeight: 21, fontWeight: '400', letterSpacing: -0.32 },
  subhead: { fontSize: 15, lineHeight: 20, fontWeight: '400', letterSpacing: -0.24 },
  footnote: { fontSize: 13, lineHeight: 18, fontWeight: '400', letterSpacing: -0.08 },
  caption1: { fontSize: 12, lineHeight: 16, fontWeight: '400', letterSpacing: 0 },
  caption2: { fontSize: 11, lineHeight: 13, fontWeight: '500', letterSpacing: 0.07 },
};

export const fontFamily = Platform.select({
  ios: 'System',
  android: 'sans-serif',
  default: 'System',
});

// Rounded/monospaced numeral style used for big score & guess digits.
export const numericFontFamily = Platform.select({
  ios: 'System',
  default: 'System',
});

// ---------------------------------------------------------------------------
// Spacing / radius
// ---------------------------------------------------------------------------

export const spacing = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  pill: 999,
} as const;

// ---------------------------------------------------------------------------
// Elevation — soft, native-feeling shadows per scheme
// ---------------------------------------------------------------------------

export interface ShadowToken {
  shadowColor: string;
  shadowOffset: { width: number; height: number };
  shadowOpacity: number;
  shadowRadius: number;
  elevation: number;
}

export function getShadows(scheme: ColorScheme): Record<'sm' | 'md' | 'lg', ShadowToken> {
  const shadowColor = scheme === 'light' ? '#332D25' : '#000000';
  const base = scheme === 'light' ? 0.08 : 0.5;
  return {
    sm: {
      shadowColor,
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: base,
      shadowRadius: 3,
      elevation: 2,
    },
    md: {
      shadowColor,
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: base + 0.02,
      shadowRadius: 12,
      elevation: 6,
    },
    lg: {
      shadowColor,
      shadowOffset: { width: 0, height: 10 },
      shadowOpacity: base + 0.05,
      shadowRadius: 24,
      elevation: 12,
    },
  };
}

// ---------------------------------------------------------------------------
// Motion — shared spring configs (Reanimated). Nothing in the app should
// animate on a linear/ease timing curve; everything springs.
// ---------------------------------------------------------------------------

export const springs = {
  snappy: { damping: 18, stiffness: 220, mass: 0.9 },
  gentle: { damping: 20, stiffness: 140, mass: 1 },
  bouncy: { damping: 12, stiffness: 180, mass: 1 },
} as const;

export const durations = {
  fast: 150,
  normal: 250,
  slow: 400,
} as const;
