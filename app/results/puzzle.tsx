import { useEffect, useState } from 'react';
import { Pressable, ScrollView, Share, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { MotiView } from 'moti';
import { ShareIcon, XIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { SequenceTiles } from '@/components/game/SequenceTiles';
import { formatStopwatch } from '@/hooks/useStopwatch';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { getRevealedSolution } from '@/lib/api/content';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { useGameStore } from '@/store/useGameStore';

export default function PuzzleResultsScreen() {
  const { colors } = useTheme();
  const today = useGameStore((s) => s.today);
  const streak = useGameStore((s) => s.streak);
  const [solution, setSolution] = useState<number[] | null>(null);

  const puzzle = today?.puzzle;
  const attempt = today?.puzzleAttempt;

  useEffect(() => {
    if (puzzle) getRevealedSolution(puzzle.id).then((s) => setSolution(s.values)).catch(() => {});
  }, [puzzle]);

  if (!puzzle || !attempt) {
    return (
      <Screen>
        <LoadingState />
      </Screen>
    );
  }

  const solved = attempt.solved;
  const displayedValue = solved ? (solution?.[0] ?? null) : (attempt.answer?.values?.[0] ?? null);
  const filledSequence = puzzle.puzzle_data.sequence.map((v) => (v === null ? displayedValue : v));

  const handleShare = async () => {
    track(AnalyticsEvent.ShareSheetOpened, { source: 'puzzle_results' });
    const message = solved
      ? `I solved today's Närmast puzzle in ${formatStopwatch(attempt.time_seconds)} 🧩 ${streak?.current_streak ?? 0}-day streak. Beat my time?`
      : `Today's Närmast puzzle got me. Think you can crack it?`;
    await Share.share({ message });
  };

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={styles.header}>
        <View style={{ width: 24 }} />
        <Text variant="headline">Result</Text>
        <Pressable onPress={() => router.replace('/(tabs)')} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <MotiView
          from={{ scale: 0.7, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', damping: 12, stiffness: 160 }}
          style={[styles.badge, { backgroundColor: solved ? colors.successSoft : colors.errorSoft }]}
        >
          <Text style={styles.badgeEmoji}>{solved ? '🧩' : '🤔'}</Text>
        </MotiView>

        <Text variant="title1" center style={styles.headline}>
          {solved ? 'Solved!' : 'Not quite'}
        </Text>
        <Text variant="body" tone="secondary" center style={styles.subhead}>
          {solved
            ? `You cracked it in ${formatStopwatch(attempt.time_seconds)}.`
            : `The answer was ${solution?.[0] ?? '…'}.`}
        </Text>

        <SequenceTiles sequence={filledSequence} currentInput={String(displayedValue ?? '')} outcome={solved ? 'correct' : 'incorrect'} />

        <Text variant="footnote" tone="secondary" style={styles.patternNote}>
          {puzzle.title}
        </Text>

        <View style={styles.statsRow}>
          <Stat label="Time" value={formatStopwatch(attempt.time_seconds)} />
          <Stat label="Score" value={String(attempt.score)} />
          <Stat label="Streak" value={`🔥 ${streak?.current_streak ?? 0}`} />
        </View>
      </ScrollView>

      <View style={styles.bottom}>
        <Button icon={<ShareIcon size={18} color={colors.onAccent} />} onPress={handleShare}>
          Share result
        </Button>
        <Button variant="tertiary" onPress={() => router.replace('/(tabs)')}>
          Back to Home
        </Button>
      </View>
    </Screen>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text variant="title3">{value}</Text>
      <Text variant="caption1" tone="secondary">
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  content: { alignItems: 'center', paddingHorizontal: spacing.lg, gap: spacing.sm, paddingBottom: spacing.lg },
  badge: { width: 80, height: 80, borderRadius: 40, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.xs },
  badgeEmoji: { fontSize: 40 },
  headline: {},
  subhead: { marginBottom: spacing.sm, maxWidth: 300 },
  patternNote: { marginTop: -spacing.xs },
  statsRow: { flexDirection: 'row', gap: spacing.xl, marginTop: spacing.md },
  stat: { alignItems: 'center', gap: 2 },
  bottom: { paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, gap: spacing.sm },
});
