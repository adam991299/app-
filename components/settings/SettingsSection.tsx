import type { PropsWithChildren } from 'react';
import { StyleSheet, View } from 'react-native';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';
import { spacing } from '@/constants/theme';

export function SettingsSection({ title, children }: PropsWithChildren<{ title: string }>) {
  return (
    <View style={styles.wrap}>
      <Text variant="footnote" tone="secondary" style={styles.title}>
        {title.toUpperCase()}
      </Text>
      <Card padded={false} style={styles.card}>
        {children}
      </Card>
    </View>
  );
}

export function SettingsRow({ children, last }: PropsWithChildren<{ last?: boolean }>) {
  return <View style={[styles.row, !last && styles.rowBorder]}>{children}</View>;
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.xxs },
  title: { letterSpacing: 0.5, marginLeft: spacing.xs },
  card: { overflow: 'hidden' },
  row: { paddingHorizontal: spacing.sm, paddingVertical: spacing.sm },
  rowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: 'rgba(128,128,128,0.2)' },
});
