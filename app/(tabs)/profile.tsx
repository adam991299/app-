import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { ArchiveIcon, ChevronRightIcon, FlameIcon, LockIcon, SettingsIcon, TargetIcon, TrophyIcon } from 'lucide-react-native';
import { Avatar } from '@/components/ui/Avatar';
import { Card } from '@/components/ui/Card';
import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { CategoryBarChart } from '@/components/charts/CategoryBarChart';
import { ScoreSparkline } from '@/components/charts/ScoreSparkline';
import { StatTile } from '@/components/profile/StatTile';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { getMyStats, type PersonalStats } from '@/lib/api/profile';
import { useAuthStore } from '@/store/useAuthStore';

export default function ProfileScreen() {
  const { colors } = useTheme();
  const profile = useAuthStore((s) => s.profile);
  const [stats, setStats] = useState<PersonalStats | null>(null);

  useFocusEffect(
    useCallback(() => {
      getMyStats().then(setStats).catch(() => {});
    }, [])
  );

  const isPremium = profile?.is_premium ?? false;

  return (
    <Screen edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.header}>
          <View style={styles.identity}>
            <Avatar emoji={profile?.avatar_emoji ?? '🙂'} color={profile?.avatar_color ?? colors.accent} size={56} />
            <View>
              <Text variant="title2">{profile?.display_name ?? 'Player'}</Text>
              <Text variant="footnote" tone="secondary">
                Code: {profile?.invite_code}
              </Text>
            </View>
          </View>
          <Pressable onPress={() => router.push('/settings')} hitSlop={12}>
            <SettingsIcon size={24} color={colors.textSecondary} />
          </Pressable>
        </View>

        {!stats ? (
          <LoadingState />
        ) : (
          <>
            <View style={styles.statGrid}>
              <StatTile sfSymbol="flame.fill" fallback={FlameIcon} label="Current streak" value={String(stats.currentStreak)} tint={colors.accent} />
              <StatTile sfSymbol="trophy.fill" fallback={TrophyIcon} label="Longest streak" value={String(stats.longestStreak)} tint={colors.warning} />
            </View>
            <View style={styles.statGrid}>
              <StatTile sfSymbol="target" fallback={TargetIcon} label="Avg. guesses" value={stats.averageGuesses ? stats.averageGuesses.toFixed(1) : '—'} tint={colors.secondaryAccent} />
              <StatTile sfSymbol="percent" fallback={TrophyIcon} label="Win rate" value={`${Math.round(stats.winRate * 100)}%`} tint={colors.success} />
            </View>

            <Pressable onPress={() => router.push('/archive')}>
              <Card style={styles.archiveRow}>
                <View style={[styles.archiveIconWrap, { backgroundColor: colors.accentSoft }]}>
                  <ArchiveIcon size={20} color={colors.accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text variant="headline">Archive</Text>
                  <Text variant="footnote" tone="secondary">
                    Browse past questions & puzzles
                  </Text>
                </View>
                {!isPremium ? <LockIcon size={16} color={colors.textTertiary} /> : <ChevronRightIcon size={20} color={colors.textTertiary} />}
              </Card>
            </Pressable>

            <Text variant="footnote" tone="secondary" style={styles.sectionLabel}>
              EXTENDED STATS
            </Text>

            {isPremium ? (
              <Card style={styles.chartCard}>
                <Text variant="subhead" weight="600">
                  Score history
                </Text>
                <ScoreSparkline values={stats.scoreHistory.slice(-14).map((s) => s.score)} width={280} />
                <Text variant="subhead" weight="600" style={styles.chartTitle}>
                  By category
                </Text>
                <CategoryBarChart data={stats.categoryBreakdown} />
              </Card>
            ) : (
              <Card style={styles.lockedCard} onPress={() => router.push('/paywall')}>
                <LockIcon size={22} color={colors.accent} />
                <Text variant="headline" style={styles.lockedTitle}>
                  Unlock extended stats
                </Text>
                <Text variant="footnote" tone="secondary" center>
                  Category breakdowns, score history and the full archive with Närmast Premium.
                </Text>
              </Card>
            )}
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: spacing.md, paddingBottom: spacing.xxl, gap: spacing.sm },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm },
  identity: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  statGrid: { flexDirection: 'row', gap: spacing.sm },
  archiveRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  archiveIconWrap: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  sectionLabel: { letterSpacing: 0.5, marginTop: spacing.sm },
  chartCard: { gap: spacing.sm, alignItems: 'center' },
  chartTitle: { alignSelf: 'flex-start', marginTop: spacing.xs },
  lockedCard: { alignItems: 'center', gap: spacing.xxs, paddingVertical: spacing.lg },
  lockedTitle: {},
});
