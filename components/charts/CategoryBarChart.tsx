import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui/Text';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import type { CategoryBreakdown } from '@/lib/api/profile';

const CATEGORY_LABELS: Record<string, string> = {
  history: 'History',
  nature: 'Nature',
  sports: 'Sports',
  'pop-culture': 'Pop Culture',
};

/** Minimal horizontal bar chart — solve rate per trivia category, Apple Health–style. */
export function CategoryBarChart({ data }: { data: CategoryBreakdown[] }) {
  const { colors } = useTheme();
  if (data.length === 0) return null;

  return (
    <View style={styles.wrap}>
      {data.map((row) => {
        const rate = row.attempts > 0 ? row.solved / row.attempts : 0;
        return (
          <View key={row.category} style={styles.row}>
            <Text variant="footnote" style={styles.label} numberOfLines={1}>
              {CATEGORY_LABELS[row.category] ?? row.category}
            </Text>
            <View style={[styles.track, { backgroundColor: colors.backgroundSecondary }]}>
              <View style={[styles.fill, { width: `${Math.max(rate * 100, 4)}%`, backgroundColor: colors.accent }]} />
            </View>
            <Text variant="caption1" tone="secondary" style={styles.value}>
              {row.solved}/{row.attempts}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  label: { width: 84 },
  track: { flex: 1, height: 8, borderRadius: radius.pill, overflow: 'hidden' },
  fill: { height: 8, borderRadius: radius.pill },
  value: { width: 40, textAlign: 'right' },
});
