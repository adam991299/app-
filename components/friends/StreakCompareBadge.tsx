import { StyleSheet, View } from 'react-native';
import { Avatar } from '@/components/ui/Avatar';
import { Text } from '@/components/ui/Text';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';

interface StreakCompareBadgeProps {
  myEmoji: string;
  myColor: string;
  myStreak: number;
  friendName: string;
  friendEmoji: string;
  friendColor: string;
  friendStreak: number;
}

export function StreakCompareBadge({
  myEmoji,
  myColor,
  myStreak,
  friendName,
  friendEmoji,
  friendColor,
  friendStreak,
}: StreakCompareBadgeProps) {
  const { colors } = useTheme();
  const winning = myStreak > friendStreak;

  return (
    <View style={[styles.wrap, { backgroundColor: colors.card, borderColor: colors.borderSubtle }]}>
      <View style={styles.side}>
        <Avatar emoji={myEmoji} color={myColor} size={52} />
        <Text variant="title2" weight="700" style={{ color: winning ? colors.success : colors.text }}>
          🔥 {myStreak}
        </Text>
        <Text variant="caption1" tone="secondary">
          You
        </Text>
      </View>
      <Text variant="headline" tone="tertiary">
        vs
      </Text>
      <View style={styles.side}>
        <Avatar emoji={friendEmoji} color={friendColor} size={52} />
        <Text variant="title2" weight="700" style={{ color: !winning && friendStreak > myStreak ? colors.warning : colors.text }}>
          🔥 {friendStreak}
        </Text>
        <Text variant="caption1" tone="secondary" numberOfLines={1}>
          {friendName}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    borderRadius: radius.xl,
    borderWidth: 1,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.md,
  },
  side: { alignItems: 'center', gap: spacing.xxs, flex: 1 },
});
