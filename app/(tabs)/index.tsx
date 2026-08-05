import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { FlameIcon, PuzzleIcon, ShareIcon, TargetIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Screen } from '@/components/ui/Screen';
import { ErrorState, LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { FriendActivityFeed } from '@/components/home/FriendActivityFeed';
import { TodayCard } from '@/components/home/TodayCard';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { getFriendActivityFeed } from '@/lib/api/friends';
import { formatCountdown, formatFriendlyDate, msUntilNextContentDay } from '@/lib/dateUtils';
import { useAuthStore } from '@/store/useAuthStore';
import { useGameStore } from '@/store/useGameStore';
import { puzzleState, questionState } from '@/types/game';
import type { FriendActivityRow } from '@/types/database';

export default function HomeScreen() {
  const { colors } = useTheme();
  const profile = useAuthStore((s) => s.profile);
  const { today, streak, loading, error, load } = useGameStore();
  const [refreshing, setRefreshing] = useState(false);
  const [activity, setActivity] = useState<FriendActivityRow[]>([]);
  const [countdown, setCountdown] = useState(msUntilNextContentDay());

  useFocusEffect(
    useCallback(() => {
      load();
      getFriendActivityFeed(5).then(setActivity).catch(() => {});
    }, [load])
  );

  useEffect(() => {
    const interval = setInterval(() => setCountdown(msUntilNextContentDay()), 1000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  if (loading && !today) {
    return (
      <Screen>
        <LoadingState label="Loading today's Närmast…" />
      </Screen>
    );
  }

  if (error && !today) {
    return (
      <Screen>
        <ErrorState message={error} onRetry={load} />
      </Screen>
    );
  }

  const qState = questionState(today?.questionAttempt ?? null);
  const pState = puzzleState(today?.puzzleAttempt ?? null);
  const bothDone = qState === 'completed' && pState === 'completed';

  return (
    <Screen edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />}
      >
        <View style={styles.header}>
          <View>
            <Text variant="footnote" tone="secondary">
              {formatFriendlyDate()}
            </Text>
            <Text variant="largeTitle" style={styles.hello}>
              Hej, {profile?.display_name ?? 'there'}
            </Text>
          </View>
          <View style={[styles.streakPill, { backgroundColor: colors.accentSoft }]}>
            <FlameIcon size={16} color={colors.accent} />
            <Text variant="footnote" weight="600" style={{ color: colors.accent }}>
              {streak?.current_streak ?? 0}
            </Text>
          </View>
        </View>

        {bothDone ? (
          <Card elevation="lg" style={styles.doneCard}>
            <View style={[styles.doneIconWrap, { backgroundColor: colors.accentSoft }]}>
              <FlameIcon size={28} color={colors.accent} />
            </View>
            <Text variant="title2" center style={styles.doneTitle}>
              You're done for today
            </Text>
            <Text variant="subhead" tone="secondary" center style={styles.doneBody}>
              Next question and puzzle in {formatCountdown(countdown)}
            </Text>
            <Button icon={<ShareIcon size={18} color={colors.onAccent} />} onPress={() => router.push('/results/day')}>
              Share today's results
            </Button>
          </Card>
        ) : (
          <View style={styles.cards}>
            <TodayCard
              sfSymbol="number"
              fallback={TargetIcon}
              accent={colors.accent}
              title="Today's Question"
              subtitle={today?.question?.question_text ?? 'Loading…'}
              resultLabel={
                today?.questionAttempt?.solved
                  ? `Solved in ${today.questionAttempt.guess_count} guess${today.questionAttempt.guess_count === 1 ? '' : 'es'}`
                  : today?.questionAttempt?.completed_at
                    ? 'Not quite — see the answer'
                    : undefined
              }
              state={qState}
              onPress={() => router.push(qState === 'completed' ? '/results/question' : '/play/question')}
            />
            <TodayCard
              sfSymbol="puzzlepiece.fill"
              fallback={PuzzleIcon}
              accent={colors.secondaryAccent}
              title="Today's Puzzle"
              subtitle={today?.puzzle?.title ?? 'Loading…'}
              resultLabel={
                today?.puzzleAttempt?.completed_at
                  ? today.puzzleAttempt.solved
                    ? `Solved in ${today.puzzleAttempt.time_seconds}s`
                    : 'Not quite — see the answer'
                  : undefined
              }
              state={pState}
              onPress={() => router.push(pState === 'completed' ? '/results/puzzle' : '/play/puzzle')}
            />
          </View>
        )}

        {activity.length > 0 ? (
          <View style={styles.activitySection}>
            <Text variant="footnote" tone="secondary" style={styles.sectionLabel}>
              FRIEND ACTIVITY
            </Text>
            <FriendActivityFeed entries={activity} />
          </View>
        ) : null}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: spacing.md, paddingBottom: spacing.xxl, gap: spacing.lg },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  hello: { marginTop: 2 },
  streakPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.xs,
    paddingVertical: 6,
    borderRadius: 999,
    marginTop: spacing.xs,
  },
  cards: { gap: spacing.sm },
  doneCard: { alignItems: 'center', paddingVertical: spacing.xl, gap: spacing.xs },
  doneIconWrap: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.xs },
  doneTitle: {},
  doneBody: { marginBottom: spacing.md },
  activitySection: { gap: spacing.sm },
  sectionLabel: { letterSpacing: 0.5 },
});
