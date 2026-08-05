import { useEffect, useState } from 'react';
import { Alert, Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import type { PurchasesPackage } from 'react-native-purchases';
import { ArchiveIcon, BarChart3Icon, CheckIcon, LayersIcon, XIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { isRevenueCatConfigured } from '@/lib/env';
import { haptics } from '@/lib/haptics';
import { getCurrentOffering, purchasePackage, restorePurchases } from '@/lib/revenuecat';
import { useAuthStore } from '@/store/useAuthStore';

const BENEFITS = [
  { icon: ArchiveIcon, title: 'Full archive access', body: 'Every past question and puzzle, unlocked.' },
  { icon: BarChart3Icon, title: 'Extended stats', body: 'Category breakdowns, score history and more.' },
  { icon: LayersIcon, title: 'More puzzle categories', body: "New puzzle types as they launch — first look." },
];

export default function PaywallScreen() {
  const { colors } = useTheme();
  const refreshProfile = useAuthStore((s) => s.refreshProfile);
  const [packages, setPackages] = useState<PurchasesPackage[]>([]);
  const [selected, setSelected] = useState<PurchasesPackage | null>(null);
  const [purchasing, setPurchasing] = useState(false);
  const [restoring, setRestoring] = useState(false);

  useEffect(() => {
    track(AnalyticsEvent.PaywallViewed, {});
    getCurrentOffering().then((offering) => {
      const pkgs = offering?.availablePackages ?? [];
      setPackages(pkgs);
      setSelected(pkgs.find((p) => p.packageType === 'ANNUAL') ?? pkgs[0] ?? null);
    });
  }, []);

  const handlePurchase = async () => {
    if (!isRevenueCatConfigured) {
      Alert.alert('Not configured', 'Add EXPO_PUBLIC_REVENUECAT_API_KEY_IOS and configure products in RevenueCat to enable purchases.');
      return;
    }
    if (!selected) return;
    setPurchasing(true);
    track(AnalyticsEvent.PaywallPurchaseStarted, { package: selected.identifier });
    try {
      await purchasePackage(selected);
      track(AnalyticsEvent.PaywallPurchaseCompleted, { package: selected.identifier });
      haptics.success();
      await refreshProfile();
      router.back();
    } catch (err: any) {
      if (!err?.userCancelled) {
        Alert.alert('Purchase failed', err?.message ?? 'Please try again.');
      }
    } finally {
      setPurchasing(false);
    }
  };

  const handleRestore = async () => {
    track(AnalyticsEvent.PaywallRestoreTapped, {});
    setRestoring(true);
    try {
      await restorePurchases();
      await refreshProfile();
      haptics.success();
      Alert.alert('Restored', 'Your purchases have been restored.');
    } catch (err: any) {
      Alert.alert('Restore failed', err?.message ?? 'Please try again.');
    } finally {
      setRestoring(false);
    }
  };

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={styles.header}>
        <View style={{ width: 24 }} />
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <View style={[styles.badge, { backgroundColor: colors.accentSoft }]}>
          <Text style={styles.badgeEmoji}>🔥</Text>
        </View>
        <Text variant="largeTitle" center style={styles.title}>
          Närmast Premium
        </Text>
        <Text variant="body" tone="secondary" center style={styles.subtitle}>
          Everything in the free daily loop, plus the full archive and deeper stats.
        </Text>

        <View style={styles.benefits}>
          {BENEFITS.map((b) => (
            <View key={b.title} style={styles.benefitRow}>
              <View style={[styles.checkWrap, { backgroundColor: colors.successSoft }]}>
                <CheckIcon size={14} color={colors.success} />
              </View>
              <View style={{ flex: 1 }}>
                <Text variant="headline">{b.title}</Text>
                <Text variant="footnote" tone="secondary">
                  {b.body}
                </Text>
              </View>
            </View>
          ))}
        </View>

        <View style={styles.packages}>
          {(packages.length > 0 ? packages : PLACEHOLDER_PACKAGES).map((pkg: any) => {
            const isSelected = selected ? pkg.identifier === selected.identifier : pkg.identifier === PLACEHOLDER_PACKAGES[1].identifier;
            const isYearly = pkg.packageType === 'ANNUAL';
            return (
              <Pressable
                key={pkg.identifier}
                onPress={() => (packages.length > 0 ? setSelected(pkg) : null)}
                style={[
                  styles.packageCard,
                  { borderColor: isSelected ? colors.accent : colors.border, backgroundColor: colors.card },
                ]}
              >
                {isYearly ? (
                  <View style={[styles.bestValueBadge, { backgroundColor: colors.accent }]}>
                    <Text variant="caption2" weight="700" style={{ color: colors.onAccent }}>
                      BEST VALUE
                    </Text>
                  </View>
                ) : null}
                <Text variant="headline">{isYearly ? 'Yearly' : 'Monthly'}</Text>
                <Text variant="title3" weight="700" style={{ color: colors.accent }}>
                  {pkg.product?.priceString ?? (isYearly ? '$39.99/yr' : '$4.99/mo')}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Button onPress={handlePurchase} loading={purchasing} style={styles.continueButton}>
          Continue
        </Button>
        <Button variant="tertiary" onPress={handleRestore} loading={restoring}>
          Restore purchases
        </Button>

        <Text variant="caption1" tone="tertiary" center style={styles.legal}>
          Payment charged to your Apple ID at confirmation. Subscriptions auto-renew unless
          cancelled at least 24 hours before the end of the current period. Manage or cancel
          anytime in Settings → Apple ID → Subscriptions.{' '}
          <Text
            variant="caption1"
            tone="accent"
            onPress={() => Linking.openURL('https://narmast.app/terms')}
          >
            Terms
          </Text>{' '}
          ·{' '}
          <Text
            variant="caption1"
            tone="accent"
            onPress={() => Linking.openURL('https://narmast.app/privacy')}
          >
            Privacy
          </Text>
        </Text>
      </ScrollView>
    </Screen>
  );
}

const PLACEHOLDER_PACKAGES = [
  { identifier: 'monthly_placeholder', packageType: 'MONTHLY', product: { priceString: '$4.99/mo' } },
  { identifier: 'yearly_placeholder', packageType: 'ANNUAL', product: { priceString: '$39.99/yr' } },
];

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  content: { alignItems: 'center', paddingHorizontal: spacing.lg, paddingBottom: spacing.lg },
  badge: { width: 72, height: 72, borderRadius: 36, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.sm },
  badgeEmoji: { fontSize: 34 },
  title: {},
  subtitle: { marginTop: spacing.xxs, marginBottom: spacing.lg, maxWidth: 300 },
  benefits: { width: '100%', gap: spacing.sm, marginBottom: spacing.lg },
  benefitRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  checkWrap: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  packages: { flexDirection: 'row', gap: spacing.sm, width: '100%', marginBottom: spacing.lg },
  packageCard: {
    flex: 1,
    borderWidth: 2,
    borderRadius: radius.lg,
    padding: spacing.md,
    alignItems: 'center',
    gap: spacing.xxs,
  },
  bestValueBadge: { position: 'absolute', top: -10, paddingHorizontal: spacing.xs, paddingVertical: 3, borderRadius: 999 },
  continueButton: { marginBottom: spacing.xxs },
  legal: { marginTop: spacing.md, lineHeight: 16 },
});
