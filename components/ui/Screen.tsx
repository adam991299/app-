import type { PropsWithChildren } from 'react';
import { StyleSheet, View, type ViewStyle } from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';
import { useTheme } from '@/hooks/useTheme';

interface ScreenProps extends PropsWithChildren {
  edges?: Edge[];
  style?: ViewStyle;
  padded?: boolean;
}

/** Base screen wrapper: themed background + safe-area handling. Every top-level
 * screen renders inside this so safe areas are respected everywhere (per the brief). */
export function Screen({ children, edges = ['top', 'bottom'], style, padded = false }: ScreenProps) {
  const { colors } = useTheme();
  return (
    <SafeAreaView
      edges={edges}
      style={[styles.flex, { backgroundColor: colors.background }, padded && styles.padded, style]}
    >
      {children}
    </SafeAreaView>
  );
}

/** Non-safe-area flex container in the theme background — for content that lives
 * inside a Screen but needs its own nested layout (e.g. inside a ScrollView). */
export function ScreenBody({ children, style }: PropsWithChildren<{ style?: ViewStyle }>) {
  const { colors } = useTheme();
  return <View style={[styles.flex, { backgroundColor: colors.background }, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  padded: { paddingHorizontal: 16 },
});
