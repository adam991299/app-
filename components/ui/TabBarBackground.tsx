import { StyleSheet } from 'react-native';
import { BlurView } from 'expo-blur';
import { useTheme } from '@/hooks/useTheme';

/** Translucent blur behind the tab bar, matching native iOS chrome — content scrolls
 * underneath it rather than stopping short. */
export function TabBarBackground() {
  const { isDark } = useTheme();
  return <BlurView intensity={80} tint={isDark ? 'dark' : 'light'} style={StyleSheet.absoluteFill} />;
}
