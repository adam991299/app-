import { StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { springs } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';

interface ProgressDotsProps {
  total: number;
  filled: number;
  /** Tint for filled dots at each index — lets guess dots turn red/green per attempt. */
  filledColors?: string[];
}

/** Remaining-guesses indicator used on the number-guess screen. */
export function ProgressDots({ total, filled, filledColors }: ProgressDotsProps) {
  const { colors } = useTheme();
  return (
    <View style={styles.row}>
      {Array.from({ length: total }).map((_, i) => (
        <Dot key={i} active={i < filled} color={filledColors?.[i] ?? colors.accent} inactiveColor={colors.border} />
      ))}
    </View>
  );
}

function Dot({ active, color, inactiveColor }: { active: boolean; color: string; inactiveColor: string }) {
  const style = useAnimatedStyle(() => ({
    backgroundColor: withSpring(active ? color : inactiveColor, springs.gentle),
    transform: [{ scale: withSpring(active ? 1 : 0.85, springs.bouncy) }],
  }));
  return <Animated.View style={[styles.dot, style]} />;
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8 },
  dot: { width: 10, height: 10, borderRadius: 5 },
});
