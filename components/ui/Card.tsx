import type { PropsWithChildren } from 'react';
import { Pressable, View, type ViewStyle } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { radius, spacing, springs } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { haptics } from '@/lib/haptics';

interface CardProps extends PropsWithChildren {
  onPress?: () => void;
  elevation?: 'sm' | 'md' | 'lg' | 'none';
  style?: ViewStyle;
  padded?: boolean;
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export function Card({ children, onPress, elevation = 'md', style, padded = true }: CardProps) {
  const { colors, shadows } = useTheme();
  const scale = useSharedValue(1);
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  const baseStyle: ViewStyle = {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    padding: padded ? spacing.md : 0,
    ...(elevation !== 'none' ? shadows[elevation] : {}),
  };

  if (!onPress) {
    return <View style={[baseStyle, style]}>{children}</View>;
  }

  return (
    <AnimatedPressable
      onPress={() => {
        haptics.cardSelect();
        onPress();
      }}
      onPressIn={() => {
        scale.value = withSpring(0.98, springs.snappy);
      }}
      onPressOut={() => {
        scale.value = withSpring(1, springs.snappy);
      }}
      style={[baseStyle, animatedStyle, style]}
    >
      {children}
    </AnimatedPressable>
  );
}
