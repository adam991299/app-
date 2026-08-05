import { StyleSheet, View } from 'react-native';
import { CheckIcon, XIcon } from 'lucide-react-native';
import { Text } from '@/components/ui/Text';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import type { HeadToHeadDay } from '@/lib/api/friends';

function Side({ solvedQuestion, questionGuesses, solvedPuzzle, puzzleTime }: { solvedQuestion: boolean; questionGuesses: number; solvedPuzzle: boolean; puzzleTime: number }) {
  const { colors } = useTheme();
  return (
    <View style={styles.side}>
      <View style={styles.pill}>
        {solvedQuestion ? <CheckIcon size={13} color={colors.success} /> : <XIcon size={13} color={colors.textTertiary} />}
        <Text variant="caption2" tone="secondary">
          {solvedQuestion ? `${questionGuesses}/3` : '—'}
        </Text>
      </View>
      <View style={styles.pill}>
        {solvedPuzzle ? <CheckIcon size={13} color={colors.success} /> : <XIcon size={13} color={colors.textTertiary} />}
        <Text variant="caption2" tone="secondary">
          {solvedPuzzle ? `${puzzleTime}s` : '—'}
        </Text>
      </View>
    </View>
  );
}

export function DayCompareRow({ day }: { day: HeadToHeadDay }) {
  const { colors } = useTheme();
  const date = new Date(`${day.date}T00:00:00Z`);
  const label = date.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' });

  return (
    <View style={[styles.row, { borderColor: colors.borderSubtle }]}>
      <Side solvedQuestion={day.me.questionSolved} questionGuesses={day.me.questionGuesses} solvedPuzzle={day.me.puzzleSolved} puzzleTime={day.me.puzzleTimeSeconds} />
      <Text variant="caption1" tone="tertiary" style={styles.dateLabel}>
        {label}
      </Text>
      <Side solvedQuestion={day.friend.questionSolved} questionGuesses={day.friend.questionGuesses} solvedPuzzle={day.friend.puzzleSolved} puzzleTime={day.friend.puzzleTimeSeconds} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.xs,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  side: { flex: 1, flexDirection: 'row', justifyContent: 'center', gap: spacing.sm },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 3, minWidth: 40, justifyContent: 'center' },
  dateLabel: { width: 56, textAlign: 'center' },
});
