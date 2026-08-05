import { StyleSheet, View } from 'react-native';
import { CheckIcon, ChevronRightIcon, LockIcon, type LucideIcon } from 'lucide-react-native';
import type { SFSymbol } from 'expo-symbols';
import { Card } from '@/components/ui/Card';
import { IconSymbol } from '@/components/ui/IconSymbol';
import { Text } from '@/components/ui/Text';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import type { CompletionState } from '@/types/game';

interface TodayCardProps {
  sfSymbol: SFSymbol;
  fallback: LucideIcon;
  accent: string;
  title: string;
  subtitle: string;
  state: CompletionState;
  resultLabel?: string;
  locked?: boolean;
  onPress: () => void;
}

export function TodayCard({
  sfSymbol,
  fallback,
  accent,
  title,
  subtitle,
  state,
  resultLabel,
  locked,
  onPress,
}: TodayCardProps) {
  return (
    <Card onPress={locked ? undefined : onPress} elevation="md" style={styles.card}>
      <View style={styles.row}>
        <View style={[styles.iconWrap, { backgroundColor: `${accent}1F` }]}>
          <IconSymbol sfSymbol={sfSymbol} fallback={fallback} color={accent} size={26} />
        </View>
        <View style={styles.textCol}>
          <Text variant="headline">{title}</Text>
          <Text variant="subhead" tone="secondary" numberOfLines={2} style={styles.subtitle}>
            {state === 'completed' && resultLabel ? resultLabel : subtitle}
          </Text>
        </View>
        <StatusBadge state={state} locked={locked} />
      </View>
    </Card>
  );
}

function StatusBadge({ state, locked }: { state: CompletionState; locked?: boolean }) {
  const { colors } = useTheme();
  if (locked) {
    return (
      <View style={[styles.statusIcon, { backgroundColor: colors.backgroundSecondary }]}>
        <LockIcon size={16} color={colors.textTertiary} />
      </View>
    );
  }
  if (state === 'completed') {
    return (
      <View style={[styles.statusIcon, { backgroundColor: colors.successSoft }]}>
        <CheckIcon size={16} color={colors.success} />
      </View>
    );
  }
  if (state === 'in_progress') {
    return (
      <View style={[styles.statusIcon, { backgroundColor: colors.warningSoft }]}>
        <Text variant="caption2" weight="600" style={{ color: colors.warning }}>
          •••
        </Text>
      </View>
    );
  }
  return <ChevronRightIcon size={20} color={colors.textTertiary} />;
}

const styles = StyleSheet.create({
  card: { width: '100%' },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  iconWrap: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  textCol: { flex: 1, gap: 2 },
  subtitle: {},
  statusIcon: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
});
