import { StyleSheet, View } from 'react-native';
import { MotiView } from 'moti';
import { ArrowDownIcon, ArrowUpIcon, CheckIcon } from 'lucide-react-native';
import { Text } from '@/components/ui/Text';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import type { QuestionGuess } from '@/types/database';

export function GuessHistory({ guesses, unit }: { guesses: QuestionGuess[]; unit?: string | null }) {
  const { colors } = useTheme();
  if (guesses.length === 0) return null;

  return (
    <View style={styles.wrap}>
      {guesses.map((g, i) => {
        const config = {
          higher: { icon: ArrowUpIcon, color: colors.accent },
          lower: { icon: ArrowDownIcon, color: colors.warning },
          correct: { icon: CheckIcon, color: colors.success },
        }[g.direction];
        const Icon = config.icon;
        return (
          <MotiView
            key={i}
            from={{ opacity: 0, translateX: -8 }}
            animate={{ opacity: 1, translateX: 0 }}
            transition={{ type: 'timing', duration: 200 }}
            style={[styles.row, { borderColor: colors.borderSubtle }]}
          >
            <Text variant="subhead" tone="secondary">
              {g.value.toLocaleString()}
              {unit ? ` ${unit}` : ''}
            </Text>
            <Icon size={16} color={config.color} />
          </MotiView>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.xxs },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
    borderWidth: 1,
  },
});
