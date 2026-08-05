import { useState } from 'react';
import { Alert, Linking, Platform, Pressable, ScrollView, StyleSheet, Switch, View } from 'react-native';
import { router } from 'expo-router';
import DateTimePicker from '@react-native-community/datetimepicker';
import { ChevronRightIcon, XIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { SettingsRow, SettingsSection } from '@/components/settings/SettingsSection';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { cancelDailyReminder, requestNotificationPermission, scheduleDailyReminder } from '@/lib/notifications';
import { restorePurchases } from '@/lib/revenuecat';
import { useAuthStore } from '@/store/useAuthStore';
import { useSettingsStore, type ThemePreference } from '@/store/useSettingsStore';

const THEME_OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

export default function SettingsScreen() {
  const { colors } = useTheme();
  const profile = useAuthStore((s) => s.profile);
  const saveProfileSetup = useAuthStore((s) => s.saveProfileSetup);
  const signOut = useAuthStore((s) => s.signOut);
  const deleteAccount = useAuthStore((s) => s.deleteAccount);
  const themePreference = useSettingsStore((s) => s.themePreference);
  const setThemePreference = useSettingsStore((s) => s.setThemePreference);
  const [showTimePicker, setShowTimePicker] = useState(false);
  const [busy, setBusy] = useState(false);

  const notificationTime = parseTime(profile?.notification_time ?? '09:00:00');

  const handleToggleNotifications = async (enabled: boolean) => {
    if (enabled) {
      const granted = await requestNotificationPermission();
      if (!granted) {
        Alert.alert('Notifications disabled', 'Enable notifications for Närmast in Settings to get a daily reminder.');
        return;
      }
      await scheduleDailyReminder(notificationTime.getHours(), notificationTime.getMinutes());
    } else {
      await cancelDailyReminder();
    }
    await saveProfileSetup({ notifications_enabled: enabled });
    track(AnalyticsEvent.NotificationTimeChanged, { enabled });
  };

  const handleTimeChange = async (_event: unknown, date?: Date) => {
    setShowTimePicker(Platform.OS === 'ios');
    if (!date) return;
    const hh = String(date.getHours()).padStart(2, '0');
    const mm = String(date.getMinutes()).padStart(2, '0');
    await saveProfileSetup({ notification_time: `${hh}:${mm}:00` });
    if (profile?.notifications_enabled) {
      await scheduleDailyReminder(date.getHours(), date.getMinutes());
    }
    track(AnalyticsEvent.NotificationTimeChanged, { time: `${hh}:${mm}` });
  };

  const handleRestore = async () => {
    setBusy(true);
    try {
      await restorePurchases();
      Alert.alert('Restored', 'Your purchases have been restored.');
    } catch (err: any) {
      Alert.alert('Restore failed', err?.message ?? 'Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const handleManageSubscription = () => {
    if (Platform.OS === 'ios') {
      Linking.openURL('itms-apps://apps.apple.com/account/subscriptions');
    }
  };

  const handleSignOut = () => {
    Alert.alert('Sign out?', 'You can sign back in any time.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: () => signOut() },
    ]);
  };

  const handleDeleteAccount = () => {
    Alert.alert(
      'Delete account?',
      'This permanently deletes your account, streak and history. This can’t be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            setBusy(true);
            try {
              await deleteAccount();
            } catch (err: any) {
              Alert.alert('Could not delete account', err?.message ?? 'Please try again.');
            } finally {
              setBusy(false);
            }
          },
        },
      ]
    );
  };

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={styles.header}>
        <Text variant="title2">Settings</Text>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <SettingsSection title="Notifications">
          <SettingsRow>
            <View style={styles.rowBetween}>
              <Text variant="body">Daily reminder</Text>
              <Switch
                value={profile?.notifications_enabled ?? true}
                onValueChange={handleToggleNotifications}
                trackColor={{ true: colors.accent }}
              />
            </View>
          </SettingsRow>
          <SettingsRow last>
            <Pressable style={styles.rowBetween} onPress={() => setShowTimePicker(true)} disabled={!profile?.notifications_enabled}>
              <Text variant="body" tone={profile?.notifications_enabled ? 'primary' : 'tertiary'}>
                Reminder time
              </Text>
              <View style={styles.rowValue}>
                <Text variant="body" tone="secondary">
                  {notificationTime.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
                </Text>
                <ChevronRightIcon size={18} color={colors.textTertiary} />
              </View>
            </Pressable>
          </SettingsRow>
        </SettingsSection>

        {showTimePicker ? (
          <DateTimePicker mode="time" value={notificationTime} onChange={handleTimeChange} display={Platform.OS === 'ios' ? 'spinner' : 'default'} />
        ) : null}

        <SettingsSection title="Appearance">
          <SettingsRow last>
            <View style={styles.segmented}>
              {THEME_OPTIONS.map((opt) => (
                <Pressable
                  key={opt.value}
                  onPress={() => setThemePreference(opt.value)}
                  style={[
                    styles.segment,
                    themePreference === opt.value && { backgroundColor: colors.accent },
                  ]}
                >
                  <Text
                    variant="footnote"
                    weight="600"
                    style={{ color: themePreference === opt.value ? colors.onAccent : colors.textSecondary }}
                  >
                    {opt.label}
                  </Text>
                </Pressable>
              ))}
            </View>
          </SettingsRow>
        </SettingsSection>

        <SettingsSection title="Subscription">
          <SettingsRow>
            <Pressable style={styles.rowBetween} onPress={() => router.push('/paywall')}>
              <Text variant="body">{profile?.is_premium ? 'Närmast Premium' : 'Upgrade to Premium'}</Text>
              <ChevronRightIcon size={18} color={colors.textTertiary} />
            </Pressable>
          </SettingsRow>
          {profile?.is_premium ? (
            <SettingsRow>
              <Pressable style={styles.rowBetween} onPress={handleManageSubscription}>
                <Text variant="body">Manage subscription</Text>
                <ChevronRightIcon size={18} color={colors.textTertiary} />
              </Pressable>
            </SettingsRow>
          ) : null}
          <SettingsRow last>
            <Pressable style={styles.rowBetween} onPress={handleRestore}>
              <Text variant="body">Restore purchases</Text>
              <ChevronRightIcon size={18} color={colors.textTertiary} />
            </Pressable>
          </SettingsRow>
        </SettingsSection>

        <SettingsSection title="About">
          <SettingsRow>
            <Pressable style={styles.rowBetween} onPress={() => Linking.openURL('https://narmast.app/privacy')}>
              <Text variant="body">Privacy Policy</Text>
              <ChevronRightIcon size={18} color={colors.textTertiary} />
            </Pressable>
          </SettingsRow>
          <SettingsRow last>
            <Pressable style={styles.rowBetween} onPress={() => Linking.openURL('https://narmast.app/terms')}>
              <Text variant="body">Terms of Service</Text>
              <ChevronRightIcon size={18} color={colors.textTertiary} />
            </Pressable>
          </SettingsRow>
        </SettingsSection>

        <Button variant="secondary" onPress={handleSignOut} style={styles.signOutButton}>
          Sign Out
        </Button>
        <Button variant="destructive" onPress={handleDeleteAccount} loading={busy}>
          Delete Account
        </Button>
      </ScrollView>
    </Screen>
  );
}

function parseTime(hhmmss: string): Date {
  const [h, m] = hhmmss.split(':').map(Number);
  const d = new Date();
  d.setHours(h || 9, m || 0, 0, 0);
  return d;
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  scroll: { paddingHorizontal: spacing.md, paddingBottom: spacing.xxl, gap: spacing.lg },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  rowValue: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  segmented: { flexDirection: 'row', gap: 4, width: '100%' },
  segment: { flex: 1, paddingVertical: spacing.xs, borderRadius: 10, alignItems: 'center' },
  signOutButton: { marginTop: spacing.sm },
});
