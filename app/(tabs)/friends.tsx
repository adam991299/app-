import { useCallback, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { UserPlusIcon, UsersIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Screen } from '@/components/ui/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { LeaderboardRow } from '@/components/friends/LeaderboardRow';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { getWeeklyLeaderboard } from '@/lib/api/friends';
import { useAuthStore } from '@/store/useAuthStore';
import type { WeeklyLeaderboardRow } from '@/types/database';

export default function FriendsScreen() {
  const { colors } = useTheme();
  const profile = useAuthStore((s) => s.profile);
  const [rows, setRows] = useState<WeeklyLeaderboardRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getWeeklyLeaderboard();
      setRows(data);
      setError(null);
    } catch (err: any) {
      setError(err?.message ?? 'Could not load the leaderboard.');
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const handleRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const hasFriends = (rows?.length ?? 0) > 1;

  return (
    <Screen edges={['top']}>
      <View style={styles.header}>
        <Text variant="largeTitle">Friends</Text>
        <Button
          variant="secondary"
          fullWidth={false}
          size="medium"
          icon={<UserPlusIcon size={16} color={colors.accent} />}
          onPress={() => router.push('/friends/add')}
        >
          Add
        </Button>
      </View>

      {rows === null && !error ? (
        <LoadingState label="Loading leaderboard…" />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} tintColor={colors.accent} />}
        >
          <Text variant="footnote" tone="secondary" style={styles.sectionLabel}>
            THIS WEEK
          </Text>
          <Card style={styles.leaderboardCard}>
            {rows!.map((row) => (
              <LeaderboardRow
                key={row.user_id}
                row={row}
                isMe={row.user_id === profile?.id}
                onPress={
                  row.user_id === profile?.id
                    ? undefined
                    : () =>
                        router.push({
                          pathname: '/friends/[id]',
                          params: {
                            id: row.user_id,
                            name: row.display_name,
                            emoji: row.avatar_emoji,
                            color: row.avatar_color,
                          },
                        })
                }
              />
            ))}
          </Card>

          {!hasFriends ? (
            <EmptyState
              icon={UsersIcon}
              title="No friends yet"
              message="Add a friend by invite code to start a weekly leaderboard and compare streaks."
              actionLabel="Add a friend"
              onAction={() => router.push('/friends/add')}
            />
          ) : null}
        </ScrollView>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
    paddingBottom: spacing.sm,
  },
  scroll: { paddingHorizontal: spacing.md, paddingBottom: spacing.xxl, gap: spacing.sm },
  sectionLabel: { letterSpacing: 0.5, marginBottom: spacing.xxs },
  leaderboardCard: { gap: spacing.xxs },
});
