import { Platform } from 'react-native';
import { Tabs } from 'expo-router';
import { HouseIcon, TrophyIcon, UserIcon } from 'lucide-react-native';
import { IconSymbol } from '@/components/ui/IconSymbol';
import { TabBarBackground } from '@/components/ui/TabBarBackground';
import { useTheme } from '@/hooks/useTheme';

export default function TabsLayout() {
  const { colors } = useTheme();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarBackground: () => <TabBarBackground />,
        tabBarStyle: Platform.select({
          ios: { position: 'absolute', borderTopWidth: 0 },
          default: { backgroundColor: colors.card, borderTopColor: colors.border },
        }),
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Today',
          tabBarIcon: ({ color, size }) => <IconSymbol sfSymbol="house.fill" fallback={HouseIcon} color={color as string} size={size} />,
        }}
      />
      <Tabs.Screen
        name="friends"
        options={{
          title: 'Friends',
          tabBarIcon: ({ color, size }) => <IconSymbol sfSymbol="trophy.fill" fallback={TrophyIcon} color={color as string} size={size} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, size }) => <IconSymbol sfSymbol="person.crop.circle.fill" fallback={UserIcon} color={color as string} size={size} />,
        }}
      />
    </Tabs>
  );
}
