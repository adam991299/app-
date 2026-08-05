import { StyleSheet, View } from 'react-native';
import { Avatar } from '@/components/ui/Avatar';
import { Text } from '@/components/ui/Text';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import type { FriendActivityRow } from '@/types/database';

function describe(entry: FriendActivityRow): string {
  if (entry.kind === 'question') {
    if (!entry.solved) return `couldn't crack today's question`;
    const guesses = entry.guess_count ?? 1;
    return `solved today's question in ${guesses} guess${guesses === 1 ? '' : 'es'}`;
  }
  if (!entry.solved) return `didn't finish today's puzzle`;
  return `solved today's puzzle in ${entry.time_seconds}s`;
}

export function FriendActivityFeed({ entries }: { entries: FriendActivityRow[] }) {
  const { colors } = useTheme();

  if (entries.length === 0) return null;

  return (
    <View style={styles.wrap}>
      {entries.map((entry, i) => (
        <View key={`${entry.user_id}-${entry.kind}-${entry.completed_at}-${i}`} style={styles.row}>
          <Avatar emoji={entry.avatar_emoji} color={entry.avatar_color} size={32} />
          <Text variant="subhead" tone="secondary" style={styles.line}>
            <Text variant="subhead" weight="600">
              {entry.display_name}
            </Text>{' '}
            {describe(entry)}
          </Text>
        </View>
      ))}
      <View style={[styles.divider, { backgroundColor: colors.borderSubtle }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  line: { flex: 1 },
  divider: { height: 1, marginTop: spacing.xxs },
});
