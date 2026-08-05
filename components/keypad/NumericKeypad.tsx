import { Pressable, StyleSheet, View } from 'react-native';
import { Delete } from 'lucide-react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { radius, spacing, springs } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { haptics } from '@/lib/haptics';
import { Text } from '@/components/ui/Text';

interface NumericKeypadProps {
  value: string;
  onChange: (value: string) => void;
  maxLength?: number;
}

const KEYS = [
  ['1', '2', '3'],
  ['4', '5', '6'],
  ['7', '8', '9'],
  ['', '0', 'delete'],
];

/**
 * A polished, custom-built numeric keypad — deliberately not the system keyboard, so
 * the guessing screen feels like a bespoke game surface rather than a form field.
 */
export function NumericKeypad({ value, onChange, maxLength = 9 }: NumericKeypadProps) {
  const press = (key: string) => {
    haptics.tap();
    if (key === 'delete') {
      onChange(value.slice(0, -1));
      return;
    }
    if (value.length >= maxLength) return;
    if (value === '0' && key === '0') return;
    onChange(value === '0' ? key : value + key);
  };

  return (
    <View style={styles.grid}>
      {KEYS.map((row, i) => (
        <View key={i} style={styles.row}>
          {row.map((key, j) =>
            key === '' ? (
              <View key={j} style={styles.key} />
            ) : (
              <KeypadKey key={j} label={key} onPress={() => press(key)} />
            )
          )}
        </View>
      ))}
    </View>
  );
}

function KeypadKey({ label, onPress }: { label: string; onPress: () => void }) {
  const { colors } = useTheme();
  const scale = useSharedValue(1);
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  return (
    <Animated.View style={[styles.key, animatedStyle]}>
      <Pressable
        onPressIn={() => {
          scale.value = withSpring(0.92, springs.snappy);
        }}
        onPressOut={() => {
          scale.value = withSpring(1, springs.snappy);
        }}
        onPress={onPress}
        style={({ pressed }) => [
          styles.keyInner,
          { backgroundColor: pressed ? colors.backgroundSecondary : colors.card, borderColor: colors.borderSubtle },
        ]}
      >
        {label === 'delete' ? (
          <Delete size={24} color={colors.textSecondary} />
        ) : (
          <Text variant="title1" weight="600">
            {label}
          </Text>
        )}
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  grid: { gap: spacing.sm },
  row: { flexDirection: 'row', gap: spacing.sm },
  key: { flex: 1, aspectRatio: 1.6 },
  keyInner: {
    flex: 1,
    borderRadius: radius.lg,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
