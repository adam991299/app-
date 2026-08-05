import 'react-native-reanimated';
import { useEffect } from 'react';
import { View } from 'react-native';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { Stack } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { LoadingState } from '@/components/ui/StateViews';
import { useTheme } from '@/hooks/useTheme';
import { useAuthStore } from '@/store/useAuthStore';
import { useSettingsStore } from '@/store/useSettingsStore';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const { colors, isDark } = useTheme();
  const authStatus = useAuthStore((s) => s.status);
  const needsProfileSetup = useAuthStore((s) => s.needsProfileSetup);
  const bootstrap = useAuthStore((s) => s.bootstrap);
  const hasCompletedOnboarding = useSettingsStore((s) => s.hasCompletedOnboarding);
  const hasHydrated = useSettingsStore((s) => s.hasHydrated);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const ready = hasHydrated && authStatus !== 'loading';

  useEffect(() => {
    if (ready) SplashScreen.hideAsync().catch(() => {});
  }, [ready]);

  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background }}>
        <LoadingState />
      </View>
    );
  }

  const signedInAndReady = authStatus === 'signedIn' && !needsProfileSetup;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar style={isDark ? 'light' : 'dark'} />
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }}>
          <Stack.Protected guard={!hasCompletedOnboarding}>
            <Stack.Screen name="(onboarding)" />
          </Stack.Protected>

          <Stack.Protected guard={hasCompletedOnboarding && authStatus === 'signedOut'}>
            <Stack.Screen name="(auth)" />
          </Stack.Protected>

          <Stack.Protected guard={hasCompletedOnboarding && authStatus === 'signedIn' && needsProfileSetup}>
            <Stack.Screen name="profile-setup" options={{ presentation: 'modal' }} />
          </Stack.Protected>

          <Stack.Protected guard={signedInAndReady}>
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="play/question" options={{ animation: 'slide_from_bottom' }} />
            <Stack.Screen name="play/puzzle" options={{ animation: 'slide_from_bottom' }} />
            <Stack.Screen name="results/question" options={{ animation: 'fade' }} />
            <Stack.Screen name="results/puzzle" options={{ animation: 'fade' }} />
            <Stack.Screen name="friends/add" options={{ presentation: 'modal' }} />
            <Stack.Screen name="friends/[id]" />
            <Stack.Screen name="archive" />
            <Stack.Screen name="settings" />
            <Stack.Screen name="paywall" options={{ presentation: 'modal' }} />
          </Stack.Protected>

          <Stack.Screen name="+not-found" />
        </Stack>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
