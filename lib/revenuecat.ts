import { Platform } from 'react-native';
import Purchases, { type CustomerInfo, type PurchasesOffering, type PurchasesPackage } from 'react-native-purchases';
import { env, isRevenueCatConfigured } from './env';

/** The RevenueCat entitlement identifier that gates the archive + extended stats. */
export const PREMIUM_ENTITLEMENT_ID = 'premium';

let configured = false;

export function isPremiumEntitled(info: CustomerInfo | null): boolean {
  if (!info) return false;
  return typeof info.entitlements.active[PREMIUM_ENTITLEMENT_ID] !== 'undefined';
}

/** Configures the RevenueCat SDK once, associating purchases with the Supabase user id. */
export async function configurePurchases(userId: string): Promise<void> {
  if (!isRevenueCatConfigured || Platform.OS !== 'ios') return;
  if (!configured) {
    Purchases.configure({ apiKey: env.revenueCatApiKeyIOS, appUserID: userId });
    configured = true;
  } else {
    await Purchases.logIn(userId);
  }
}

export async function getCurrentOffering(): Promise<PurchasesOffering | null> {
  if (!isRevenueCatConfigured) return null;
  const offerings = await Purchases.getOfferings();
  return offerings.current ?? null;
}

export async function getCustomerInfo(): Promise<CustomerInfo | null> {
  if (!isRevenueCatConfigured) return null;
  return Purchases.getCustomerInfo();
}

export async function restorePurchases(): Promise<CustomerInfo | null> {
  if (!isRevenueCatConfigured) return null;
  return Purchases.restorePurchases();
}

export async function purchasePackage(pkg: PurchasesPackage): Promise<CustomerInfo> {
  const { customerInfo } = await Purchases.purchasePackage(pkg);
  return customerInfo;
}

export async function logOutPurchases(): Promise<void> {
  if (!isRevenueCatConfigured || !configured) return;
  await Purchases.logOut();
}

/** Fires whenever RevenueCat's local entitlement cache changes (e.g. right after a
 * purchase, or when a background receipt refresh completes) — used to nudge the app
 * into re-fetching the Supabase profile sooner than waiting on the webhook alone. The
 * DB's `is_premium` (updated by revenuecat-webhook) stays the actual source of truth
 * for gating; this just makes the UI feel instant. */
export function addPremiumStatusListener(callback: (info: CustomerInfo) => void): () => void {
  if (!isRevenueCatConfigured) return () => {};
  Purchases.addCustomerInfoUpdateListener(callback);
  return () => Purchases.removeCustomerInfoUpdateListener(callback);
}
