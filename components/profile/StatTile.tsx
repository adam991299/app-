import { StyleSheet, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';
import type { SFSymbol } from 'expo-symbols';
import { Card } from '@/components/ui/Card';
import { IconSymbol } from '@/components/ui/IconSymbol';
import { Text } from '@/components/ui/Text';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';

interface StatTileProps {
  sfSymbol: SFSymbol;
  fallback: LucideIcon;
  label: string;
  value: string;
  tint: string;
}

export function StatTile({ sfSymbol, fallback, label, value, tint }: StatTileProps) {
  const { colors } = useTheme();
  return (
    <Card style={styles.card} elevation="sm">
      <View style={[styles.iconWrap, { backgroundColor: `${tint}1F` }]}>
        <IconSymbol sfSymbol={sfSymbol} fallback={fallback} size={18} color={tint} />
      </View>
      <Text variant="title2" weight="700">
        {value}
      </Text>
      <Text variant="caption1" tone="secondary">
        {label}
      </Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { flex: 1, gap: spacing.xxs, alignItems: 'flex-start' },
  iconWrap: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.xxs },
});
