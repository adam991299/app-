import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { XIcon } from 'lucide-react-native';
import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { DayCompareRow } from '@/components/friends/DayCompareRow';
import { StreakCompareBadge } from '@/components/friends/StreakCompareBadge';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { getFriendStreak, getHeadToHead, type HeadToHeadDay } from '@/lib/api/friends';
import { useAuthStore } from '@/store/useAuthStore';
import { useGameStore } from '@/store/useGameStore';

export default function HeadToHeadScreen() {
  const { colors } = useTheme();
  const { id, name, emoji, color } = useLocalSearchParams<{ id: string; name?: string; emoji?: string; color?: string }>();
  const profile = useAuthStore((s) => s.profile);
  const myStreak = useGameStore((s) => s.streak);
  const [friendStreak, setFriendStreak] = useState<number | null>(null);
  const [days, setDays] = useState<HeadToHeadDay[] | null>(null);

  useEffect(() => {
    if (!id) return;
    getFriendStreak(id).then((s) => setFriendStreak(s.current));
    getHeadToHead(id, 7).then(setDays);
  }, [id]);

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={styles.header}>
        <View style={{ width: 24 }} />
        <Text variant="headline">{name ?? 'Friend'}</Text>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
      </View>

      {friendStreak === null || days === null ? (
        <LoadingState />
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          <StreakCompareBadge
            myEmoji={profile?.avatar_emoji ?? '🙂'}
            myColor={profile?.avatar_color ?? colors.accent}
            myStreak={myStreak?.current_streak ?? 0}
            friendName={name ?? 'Friend'}
            friendEmoji={emoji ?? '🙂'}
            friendColor={color ?? colors.secondaryAccent}
            friendStreak={friendStreak}
          />

          <View style={styles.tableWrap}>
            <View style={styles.tableHeader}>
              <Text variant="caption1" tone="tertiary" style={styles.tableHeaderSide}>
                You
              </Text>
              <View style={{ width: 56 }} />
              <Text variant="caption1" tone="tertiary" style={styles.tableHeaderSide}>
                {name ?? 'Friend'}
              </Text>
            </View>
            {days.map((day) => (
              <DayCompareRow key={day.date} day={day} />
            ))}
          </View>

          <Text variant="caption1" tone="tertiary" center style={styles.legend}>
            Each row shows question guesses/3 and puzzle solve time — last 7 days.
          </Text>
        </ScrollView>
      )}
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
  content: { paddingHorizontal: spacing.md, paddingBottom: spacing.xl, gap: spacing.lg },
  tableWrap: { gap: spacing.xxs },
  tableHeader: { flexDirection: 'row', alignItems: 'center', paddingBottom: spacing.xxs },
  tableHeaderSide: { flex: 1, textAlign: 'center', textTransform: 'uppercase', letterSpacing: 0.5 },
  legend: { marginTop: spacing.xs },
});
