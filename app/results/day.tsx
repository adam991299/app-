import { useEffect, useState } from 'react';
import { Pressable, ScrollView, Share, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { LinkIcon, ShareIcon, XIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { ShareCard } from '@/components/share/ShareCard';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { useShareCard } from '@/hooks/useShareCard';
import { getRevealedAnswer, getRevealedSolution } from '@/lib/api/content';
import { formatFriendlyDate } from '@/lib/dateUtils';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { buildChallengeLink } from '@/lib/share';
import { puzzleShareGrid, questionShareGrid } from '@/lib/shareGrid';
import { useAuthStore } from '@/store/useAuthStore';
import { useGameStore } from '@/store/useGameStore';

/** Combined day summary — reached from Home's "You're done for today" state. */
export default function DayResultsScreen() {
  const { colors } = useTheme();
  const today = useGameStore((s) => s.today);
  const streak = useGameStore((s) => s.streak);
  const profile = useAuthStore((s) => s.profile);
  const [answer, setAnswer] = useState<number | null>(null);
  const [solution, setSolution] = useState<number[] | null>(null);
  const { cardRef, sharing, triggerShare } = useShareCard();

  const question = today?.question;
  const puzzle = today?.puzzle;
  const qAttempt = today?.questionAttempt;
  const pAttempt = today?.puzzleAttempt;

  useEffect(() => {
    if (question) getRevealedAnswer(question.id).then(setAnswer).catch(() => {});
    if (puzzle) getRevealedSolution(puzzle.id).then((s) => setSolution(s.values)).catch(() => {});
  }, [question, puzzle]);

  if (!question || !puzzle || !qAttempt?.completed_at || !pAttempt?.completed_at) {
    return (
      <Screen>
        <LoadingState />
      </Screen>
    );
  }

  const totalScore = qAttempt.score + pAttempt.score;
  const questionGrid = answer !== null ? questionShareGrid(qAttempt.guesses, answer) : ['⬜', '⬜', '⬜'];
  const puzzleGrid = puzzleShareGrid(pAttempt.solved, pAttempt.time_seconds);

  const sections = [
    {
      label: "Today's Question",
      grid: questionGrid,
      detail: qAttempt.solved ? `Solved in ${qAttempt.guess_count}/3` : 'Not solved',
    },
    {
      label: "Today's Puzzle",
      grid: puzzleGrid,
      detail: pAttempt.solved ? `Solved in ${pAttempt.time_seconds}s` : 'Not solved',
    },
  ];

  const handleShareImage = async () => {
    track(AnalyticsEvent.ShareSheetOpened, { source: 'day_results' });
    await triggerShare('Share your day');
  };

  const handleChallenge = async () => {
    if (!profile) return;
    track(AnalyticsEvent.ShareSheetOpened, { source: 'challenge_friend' });
    const link = buildChallengeLink(profile.invite_code);
    await Share.share({
      message: `I scored ${totalScore} on today's Närmast 🔥 ${streak?.current_streak ?? 0}-day streak. Think you can beat me? ${link}`,
    });
  };

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={styles.header}>
        <View style={{ width: 24 }} />
        <Text variant="headline">Today's Recap</Text>
        <Pressable onPress={() => router.replace('/(tabs)')} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <ShareCard ref={cardRef} date={formatFriendlyDate()} streak={streak?.current_streak ?? 0} sections={sections} />

        <View style={styles.statsRow}>
          <Stat label="Total score" value={String(totalScore)} />
          <Stat label="Streak" value={`🔥 ${streak?.current_streak ?? 0}`} />
        </View>
      </ScrollView>

      <View style={styles.bottom}>
        <Button icon={<ShareIcon size={18} color={colors.onAccent} />} onPress={handleShareImage} loading={sharing}>
          Share today's results
        </Button>
        <Button variant="secondary" icon={<LinkIcon size={18} color={colors.accent} />} onPress={handleChallenge}>
          Challenge a friend
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
  content: { alignItems: 'center', paddingHorizontal: spacing.lg, gap: spacing.lg, paddingBottom: spacing.lg },
  statsRow: { flexDirection: 'row', gap: spacing.xl },
  stat: { alignItems: 'center', gap: 2 },
  bottom: { paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, gap: spacing.sm },
});
