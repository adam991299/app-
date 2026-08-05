import { StyleSheet, View } from 'react-native';
import { MotiView } from 'moti';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { Text } from '@/components/ui/Text';

interface SequenceTilesProps {
  sequence: (number | null)[];
  /** What to show in the blank slot while the player is typing. */
  currentInput: string;
  /** Non-null once submitted, to render the tile as correct/incorrect. */
  outcome?: 'correct' | 'incorrect' | null;
}

export function SequenceTiles({ sequence, currentInput, outcome }: SequenceTilesProps) {
  const { colors } = useTheme();

  return (
    <View style={styles.row}>
      {sequence.map((value, i) => {
        const isBlank = value === null;
        const tone = isBlank
          ? outcome === 'correct'
            ? { bg: colors.successSoft, border: colors.success, fg: colors.success }
            : outcome === 'incorrect'
              ? { bg: colors.errorSoft, border: colors.error, fg: colors.error }
              : { bg: colors.accentSoft, border: colors.accent, fg: colors.accent }
          : { bg: colors.card, border: colors.borderSubtle, fg: colors.text };

        return (
          <MotiView
            key={i}
            from={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', damping: 14, stiffness: 180, delay: i * 40 }}
            style={[styles.tile, { backgroundColor: tone.bg, borderColor: tone.border }]}
          >
            <Text variant="title3" weight="700" style={{ color: tone.fg }}>
              {isBlank ? currentInput || '?' : value}
            </Text>
          </MotiView>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, justifyContent: 'center' },
  tile: {
    minWidth: 52,
    height: 52,
    paddingHorizontal: spacing.xs,
    borderRadius: radius.md,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
