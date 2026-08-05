import { Text as RNText, type TextProps as RNTextProps } from 'react-native';
import { typography, type TypeStyle } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';

type Variant = keyof typeof typography;
type Tone = 'primary' | 'secondary' | 'tertiary' | 'accent' | 'inverse' | 'success' | 'warning' | 'error';

export interface TextProps extends RNTextProps {
  variant?: Variant;
  tone?: Tone;
  weight?: TypeStyle['fontWeight'];
  center?: boolean;
}

/** The one Text component every screen should use — guarantees every string in the app
 * comes from the shared iOS type scale (constants/theme.ts) instead of a one-off size. */
export function Text({ variant = 'body', tone = 'primary', weight, center, style, ...rest }: TextProps) {
  const { colors } = useTheme();
  const typeStyle = typography[variant];

  const color = {
    primary: colors.text,
    secondary: colors.textSecondary,
    tertiary: colors.textTertiary,
    accent: colors.accent,
    inverse: colors.inverseText,
    success: colors.success,
    warning: colors.warning,
    error: colors.error,
  }[tone];

  return (
    <RNText
      style={[
        {
          fontSize: typeStyle.fontSize,
          lineHeight: typeStyle.lineHeight,
          fontWeight: weight ?? typeStyle.fontWeight,
          letterSpacing: typeStyle.letterSpacing,
          color,
          textAlign: center ? 'center' : undefined,
        },
        style,
      ]}
      {...rest}
    />
  );
}
