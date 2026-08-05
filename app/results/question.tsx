import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { MotiView } from 'moti';
import { ShareIcon, XIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { GuessHistory } from '@/components/game/GuessHistory';
import { ShareCard } from '@/components/share/ShareCard';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { useShareCard } from '@/hooks/useShareCard';
import { formatFriendlyDate } from '@/lib/dateUtils';
import { getRevealedAnswer } from '@/lib/api/content';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { questionShareGrid } from '@/lib/shareGrid';
import { useGameStore } from '@/store/useGameStore';

export default function QuestionResultsScreen() {
  const { colors } = useTheme();
  const today = useGameStore((s) => s.today);
  const streak = useGameStore((s) => s.streak);
  const [answer, setAnswer] = useState<number | null>(null);
  const { cardRef, sharing, triggerShare } = useShareCard();

  const question = today?.question;
  const attempt = today?.questionAttempt;

  useEffect(() => {
    if (question) getRevealedAnswer(question.id).then(setAnswer).catch(() => {});
  }, [question]);

  if (!question || !attempt) {
    return (
      <Screen>
        <LoadingState />
      </Screen>
    );
  }

  const solved = attempt.solved;
  const grid = answer !== null ? questionShareGrid(attempt.guesses, answer) : ['⬜', '⬜', '⬜'];

  const handleShare = async () => {
    track(AnalyticsEvent.ShareSheetOpened, { source: 'question_results' });
    await triggerShare('Share your result');
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
          <Text style={styles.badgeEmoji}>{solved ? '🎯' : '🤔'}</Text>
        </MotiView>

        <Text variant="title1" center style={styles.headline}>
          {solved ? (attempt.guess_count === 1 ? 'Nailed it!' : 'Got it!') : 'So close!'}
        </Text>
        <Text variant="body" tone="secondary" center style={styles.subhead}>
          {solved
            ? `You solved it in ${attempt.guess_count} guess${attempt.guess_count === 1 ? '' : 'es'}.`
            : `The answer was ${answer !== null ? answer.toLocaleString() : '…'}${question.unit ? ` ${question.unit}` : ''}.`}
        </Text>

        <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.borderSubtle }]}>
          <Text variant="footnote" tone="secondary">
            {question.question_text}
          </Text>
          {question.source_note ? (
            <Text variant="caption1" tone="tertiary" style={styles.sourceNote}>
              {question.source_note}
            </Text>
          ) : null}
        </View>

        <GuessHistory guesses={attempt.guesses} unit={question.unit} />

        <View style={styles.statsRow}>
          <Stat label="Score" value={String(attempt.score)} />
          <Stat label="Streak" value={`🔥 ${streak?.current_streak ?? 0}`} />
        </View>
      </ScrollView>

      <View style={styles.offscreen} pointerEvents="none">
        <ShareCard
          ref={cardRef}
          date={formatFriendlyDate()}
          streak={streak?.current_streak ?? 0}
          sections={[
            {
              label: "Today's Question",
              grid,
              detail: solved ? `Solved in ${attempt.guess_count}/3` : 'Not solved',
            },
          ]}
        />
      </View>

      <View style={styles.bottom}>
        <Button icon={<ShareIcon size={18} color={colors.onAccent} />} onPress={handleShare} loading={sharing}>
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
  card: { width: '100%', borderRadius: 16, borderWidth: 1, padding: spacing.sm, gap: spacing.xxs },
  sourceNote: {},
  statsRow: { flexDirection: 'row', gap: spacing.xl, marginTop: spacing.md },
  stat: { alignItems: 'center', gap: 2 },
  bottom: { paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, gap: spacing.sm },
  offscreen: { position: 'absolute', top: -9999, left: -9999 },
});
