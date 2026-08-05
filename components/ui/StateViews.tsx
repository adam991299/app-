import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { CircleAlert, type LucideIcon } from 'lucide-react-native';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { Button } from './Button';
import { IconSymbol } from './IconSymbol';
import { Text } from './Text';

/** Empty, loading and error states — every screen that fetches data must render one
 * of these instead of a blank view, per the brief. */

interface EmptyStateProps {
  icon?: LucideIcon;
  sfSymbol?: string;
  title: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ icon: Icon = CircleAlert, title, message, actionLabel, onAction }: EmptyStateProps) {
  const { colors } = useTheme();
  return (
    <View style={styles.center}>
      <View style={[styles.iconWrap, { backgroundColor: colors.accentSoft }]}>
        <Icon size={28} color={colors.accent} />
      </View>
      <Text variant="headline" center style={styles.title}>
        {title}
      </Text>
      {message ? (
        <Text variant="subhead" tone="secondary" center style={styles.message}>
          {message}
        </Text>
      ) : null}
      {actionLabel && onAction ? (
        <Button variant="secondary" fullWidth={false} onPress={onAction} style={styles.action}>
          {actionLabel}
        </Button>
      ) : null}
    </View>
  );
}

export function LoadingState({ label }: { label?: string }) {
  const { colors } = useTheme();
  return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color={colors.accent} />
      {label ? (
        <Text variant="subhead" tone="secondary" style={{ marginTop: spacing.sm }}>
          {label}
        </Text>
      ) : null}
    </View>
  );
}

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }: ErrorStateProps) {
  const { colors } = useTheme();
  return (
    <View style={styles.center}>
      <View style={[styles.iconWrap, { backgroundColor: colors.errorSoft }]}>
        <IconSymbol sfSymbol="exclamationmark.triangle.fill" fallback={CircleAlert} size={26} color={colors.error} />
      </View>
      <Text variant="headline" center style={styles.title}>
        {title}
      </Text>
      {message ? (
        <Text variant="subhead" tone="secondary" center style={styles.message}>
          {message}
        </Text>
      ) : null}
      {onRetry ? (
        <Button variant="secondary" fullWidth={false} onPress={onRetry} style={styles.action}>
          Try again
        </Button>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  title: { marginBottom: spacing.xxs },
  message: { maxWidth: 280 },
  action: { marginTop: spacing.lg },
});
