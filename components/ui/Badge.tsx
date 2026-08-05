import { StyleSheet, View } from 'react-native';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { Text } from './Text';

interface BadgeProps {
  label: string;
  tone?: 'accent' | 'success' | 'warning' | 'error' | 'neutral';
}

export function Badge({ label, tone = 'neutral' }: BadgeProps) {
  const { colors } = useTheme();
  const map = {
    accent: { bg: colors.accentSoft, fg: colors.accent },
    success: { bg: colors.successSoft, fg: colors.success },
    warning: { bg: colors.warningSoft, fg: colors.warning },
    error: { bg: colors.errorSoft, fg: colors.error },
    neutral: { bg: colors.backgroundSecondary, fg: colors.textSecondary },
  } as const;
  const { bg, fg } = map[tone];

  return (
    <View style={[styles.base, { backgroundColor: bg }]}>
      <Text variant="caption2" weight="600" style={{ color: fg }}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    paddingHorizontal: spacing.xs,
    paddingVertical: 4,
    borderRadius: radius.pill,
    alignSelf: 'flex-start',
  },
});
