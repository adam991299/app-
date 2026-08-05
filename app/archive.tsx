import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { CheckIcon, LockIcon, XIcon } from 'lucide-react-native';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { getArchive, type ArchiveDay } from '@/lib/api/content';
import { useAuthStore } from '@/store/useAuthStore';

export default function ArchiveScreen() {
  const { colors } = useTheme();
  const profile = useAuthStore((s) => s.profile);
  const [days, setDays] = useState<ArchiveDay[] | null>(null);
  const isPremium = profile?.is_premium ?? false;

  useEffect(() => {
    if (isPremium) getArchive(true).then(setDays);
  }, [isPremium]);

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={styles.header}>
        <Text variant="title2">Archive</Text>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
      </View>

      {!isPremium ? (
        <View style={styles.lockedWrap}>
          <View style={[styles.lockIconWrap, { backgroundColor: colors.accentSoft }]}>
            <LockIcon size={28} color={colors.accent} />
          </View>
          <Text variant="title3" center>
            Premium unlocks the archive
          </Text>
          <Text variant="subhead" tone="secondary" center style={styles.lockedBody}>
            Browse every past question and puzzle, with your results, once you upgrade.
          </Text>
          <Button onPress={() => router.push('/paywall')} style={styles.upgradeButton}>
            See Premium
          </Button>
        </View>
      ) : days === null ? (
        <LoadingState />
      ) : (
        <ScrollView contentContainerStyle={styles.scroll}>
          {days.map((day) => (
            <Card key={day.question.id} style={styles.dayCard}>
              <View style={styles.dayHeader}>
                <Text variant="footnote" tone="secondary">
                  {new Date(`${day.question.date}T00:00:00Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                </Text>
                <Badge label={day.question.category} tone="accent" />
              </View>
              <Text variant="subhead" numberOfLines={2}>
                {day.question.question_text}
              </Text>
              <View style={styles.dayStatusRow}>
                <StatusPill
                  label="Question"
                  solved={day.questionAttempt?.completed_at ? day.questionAttempt.solved : null}
                />
                <StatusPill label="Puzzle" solved={day.puzzleAttempt?.completed_at ? day.puzzleAttempt.solved : null} />
              </View>
            </Card>
          ))}
        </ScrollView>
      )}
    </Screen>
  );
}

function StatusPill({ label, solved }: { label: string; solved: boolean | null }) {
  const { colors } = useTheme();
  const tone = solved === null ? { bg: colors.backgroundSecondary, fg: colors.textTertiary, text: 'Missed' } : solved
    ? { bg: colors.successSoft, fg: colors.success, text: 'Solved' }
    : { bg: colors.errorSoft, fg: colors.error, text: 'Attempted' };

  return (
    <View style={[styles.pill, { backgroundColor: tone.bg }]}>
      {solved ? <CheckIcon size={12} color={tone.fg} /> : null}
      <Text variant="caption2" weight="600" style={{ color: tone.fg }}>
        {label} · {tone.text}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  lockedWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.xl },
  lockIconWrap: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.md },
  lockedBody: { marginTop: spacing.xxs, marginBottom: spacing.lg, maxWidth: 280 },
  upgradeButton: { minWidth: 200 },
  scroll: { padding: spacing.md, gap: spacing.sm, paddingBottom: spacing.xxl },
  dayCard: { gap: spacing.xxs },
  dayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  dayStatusRow: { flexDirection: 'row', gap: spacing.xs, marginTop: spacing.xxs },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: spacing.xs, paddingVertical: 4, borderRadius: 999 },
});
