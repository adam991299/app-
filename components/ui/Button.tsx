import type { PropsWithChildren } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View, type ViewStyle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { radius, spacing, springs } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { haptics } from '@/lib/haptics';
import { Text } from './Text';

type Variant = 'primary' | 'secondary' | 'tertiary' | 'destructive';
type Size = 'large' | 'medium';

interface ButtonProps extends PropsWithChildren {
  onPress?: () => void;
  variant?: Variant;
  size?: Size;
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  icon?: React.ReactNode;
  style?: ViewStyle;
  haptic?: 'tap' | 'buttonPress' | 'none';
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/** Full-width primary buttons with haptic feedback on press, per the brief. Every
 * button in the app should be this component rather than a bespoke Pressable. */
export function Button({
  children,
  onPress,
  variant = 'primary',
  size = 'large',
  disabled = false,
  loading = false,
  fullWidth = true,
  icon,
  style,
  haptic = 'buttonPress',
}: ButtonProps) {
  const { colors } = useTheme();
  const scale = useSharedValue(1);

  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  const palette: Record<Variant, { bg: string; fg: string; border?: string }> = {
    primary: { bg: colors.accent, fg: colors.onAccent },
    secondary: { bg: colors.accentSoft, fg: colors.accent },
    tertiary: { bg: 'transparent', fg: colors.accent, border: colors.border },
    destructive: { bg: colors.errorSoft, fg: colors.error },
  };
  const { bg, fg, border } = palette[variant];
  const isDisabled = disabled || loading;

  return (
    <AnimatedPressable
      disabled={isDisabled}
      onPressIn={() => {
        scale.value = withSpring(0.96, springs.snappy);
      }}
      onPressOut={() => {
        scale.value = withSpring(1, springs.snappy);
      }}
      onPress={() => {
        if (haptic !== 'none') haptics[haptic]();
        onPress?.();
      }}
      style={[
        styles.base,
        size === 'large' ? styles.large : styles.medium,
        {
          backgroundColor: bg,
          borderWidth: border ? 1 : 0,
          borderColor: border,
          opacity: isDisabled ? 0.5 : 1,
          alignSelf: fullWidth ? 'stretch' : 'flex-start',
        },
        animatedStyle,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <View style={styles.content}>
          {icon}
          <Text variant="headline" weight="600" style={{ color: fg }}>
            {children}
          </Text>
        </View>
      )}
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  large: { paddingVertical: spacing.sm + 2, paddingHorizontal: spacing.lg },
  medium: { paddingVertical: spacing.xs + 2, paddingHorizontal: spacing.md },
  content: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
});
