import { StyleSheet, View } from 'react-native';
import { AnimatePresence, MotiView } from 'moti';
import { ArrowDownIcon, ArrowUpIcon, CheckIcon } from 'lucide-react-native';
import { Text } from '@/components/ui/Text';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import type { QuestionGuess } from '@/types/database';

/** The animated "Higher!" / "Lower!" / "Correct!" banner shown after each guess. */
export function GuessFeedback({ direction }: { direction: QuestionGuess['direction'] | null }) {
  const { colors } = useTheme();
  if (!direction) return <View style={styles.placeholder} />;

  const config = {
    higher: { label: 'Higher', icon: ArrowUpIcon, color: colors.accent, bg: colors.accentSoft },
    lower: { label: 'Lower', icon: ArrowDownIcon, color: colors.warning, bg: colors.warningSoft },
    correct: { label: 'Correct!', icon: CheckIcon, color: colors.success, bg: colors.successSoft },
  }[direction];

  const Icon = config.icon;

  return (
    <View style={styles.placeholder}>
      <AnimatePresence>
        <MotiView
          key={direction}
          from={{ opacity: 0, scale: 0.85, translateY: 8 }}
          animate={{ opacity: 1, scale: 1, translateY: 0 }}
          exit={{ opacity: 0, scale: 0.9 }}
          transition={{ type: 'spring', damping: 14, stiffness: 200 }}
          style={[styles.banner, { backgroundColor: config.bg }]}
        >
          <Icon size={18} color={config.color} />
          <Text variant="headline" weight="600" style={{ color: config.color }}>
            {config.label}
          </Text>
        </MotiView>
      </AnimatePresence>
    </View>
  );
}

const styles = StyleSheet.create({
  placeholder: { height: 44, alignItems: 'center', justifyContent: 'center' },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xxs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.pill,
  },
});
