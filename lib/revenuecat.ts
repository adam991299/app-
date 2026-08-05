import { Platform } from 'react-native';
import Purchases, { type CustomerInfo, type PurchasesOffering } from 'react-native-purchases';
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

export async function logOutPurchases(): Promise<void> {
  if (!isRevenueCatConfigured || !configured) return;
  await Purchases.logOut();
}
