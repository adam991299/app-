import { useEffect, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { XIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { NumericKeypad } from '@/components/keypad/NumericKeypad';
import { SequenceTiles } from '@/components/game/SequenceTiles';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { formatStopwatch, useStopwatch } from '@/hooks/useStopwatch';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { haptics } from '@/lib/haptics';
import { useGameStore } from '@/store/useGameStore';

export default function PlayPuzzleScreen() {
  const { colors } = useTheme();
  const today = useGameStore((s) => s.today);
  const submitPuzzle = useGameStore((s) => s.submitPuzzle);

  const puzzle = today?.puzzle;
  const [inputValue, setInputValue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const elapsed = useStopwatch(!submitting);
  const hasStartedTracking = useRef(false);

  useEffect(() => {
    if (puzzle && !hasStartedTracking.current) {
      hasStartedTracking.current = true;
      track(AnalyticsEvent.PuzzleStarted, { puzzle_type: puzzle.puzzle_type });
    }
  }, [puzzle]);

  if (!puzzle) {
    return (
      <Screen>
        <LoadingState />
      </Screen>
    );
  }

  const handleSubmit = async () => {
    if (inputValue.length === 0) return;
    setSubmitting(true);
    haptics.selectionChange();
    try {
      const result = await submitPuzzle([Number(inputValue)], elapsed);
      track(AnalyticsEvent.PuzzleCompleted, { solved: result.solved, time_seconds: elapsed });
      if (result.solved) haptics.success();
      else haptics.error();
      setTimeout(() => router.replace('/results/puzzle'), 900);
    } catch (err: any) {
      Alert.alert('Something went wrong', err?.message ?? 'Please try again.');
      setSubmitting(false);
    }
  };

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
        <Text variant="headline">Today's Puzzle</Text>
        <View style={{ width: 24 }} />
      </View>

      <View style={styles.content}>
        <View style={[styles.timerPill, { backgroundColor: colors.backgroundSecondary }]}>
          <Text variant="footnote" tone="secondary" style={styles.timerText}>
            {formatStopwatch(elapsed)}
          </Text>
        </View>

        <Text variant="title3" center style={styles.prompt}>
          What comes next in the pattern?
        </Text>

        <View style={styles.tilesWrap}>
          <SequenceTiles sequence={puzzle.puzzle_data.sequence} currentInput={inputValue} />
        </View>
      </View>

      <View style={styles.bottom}>
        <NumericKeypad value={inputValue} onChange={setInputValue} maxLength={9} />
        <Button onPress={handleSubmit} disabled={inputValue.length === 0} loading={submitting} style={styles.submitButton}>
          Submit
        </Button>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  content: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.lg, gap: spacing.lg },
  timerPill: { paddingHorizontal: spacing.sm, paddingVertical: spacing.xxs, borderRadius: 999 },
  timerText: { fontVariant: ['tabular-nums'] },
  prompt: {},
  tilesWrap: { width: '100%' },
  bottom: { paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, gap: spacing.md },
  submitButton: { marginTop: spacing.xxs },
});
