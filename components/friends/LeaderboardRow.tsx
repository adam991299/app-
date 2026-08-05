import { Pressable, StyleSheet, View } from 'react-native';
import { Avatar } from '@/components/ui/Avatar';
import { Text } from '@/components/ui/Text';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import type { WeeklyLeaderboardRow } from '@/types/database';

const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };

export function LeaderboardRow({ row, isMe, onPress }: { row: WeeklyLeaderboardRow; isMe: boolean; onPress?: () => void }) {
  const { colors } = useTheme();

  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      style={[styles.row, isMe && { backgroundColor: colors.accentSoft, borderRadius: 14 }]}
    >
      <View style={styles.rankWrap}>
        {MEDALS[row.rank] ? (
          <Text style={styles.medal}>{MEDALS[row.rank]}</Text>
        ) : (
          <Text variant="subhead" tone="tertiary" weight="600">
            {row.rank}
          </Text>
        )}
      </View>
      <Avatar emoji={row.avatar_emoji} color={row.avatar_color} size={40} />
      <View style={styles.nameCol}>
        <Text variant="subhead" weight="600">
          {isMe ? 'You' : row.display_name}
        </Text>
        <Text variant="caption1" tone="secondary">
          {row.questions_solved + row.puzzles_solved} solved this week
        </Text>
      </View>
      <Text variant="headline" weight="700" style={{ color: colors.accent }}>
        {row.total_score.toLocaleString()}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  rankWrap: { width: 28, alignItems: 'center' },
  medal: { fontSize: 20 },
  nameCol: { flex: 1, gap: 1 },
});
