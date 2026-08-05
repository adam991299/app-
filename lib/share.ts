import * as Linking from 'expo-linking';
import * as Sharing from 'expo-sharing';
import { captureRef } from 'react-native-view-shot';
import type React from 'react';

/** Renders an off-screen (or on-screen) view ref to a PNG and returns its local file URI. */
export async function captureShareCard(ref: React.RefObject<any>): Promise<string> {
  return captureRef(ref, { format: 'png', quality: 1, result: 'tmpfile' });
}

/** Opens the native share sheet (Messages, Instagram Stories, etc.) for a local image URI. */
export async function shareImage(uri: string, dialogTitle?: string): Promise<void> {
  const available = await Sharing.isAvailableAsync();
  if (!available) return;
  await Sharing.shareAsync(uri, {
    dialogTitle: dialogTitle ?? 'Share your result',
    mimeType: 'image/png',
    UTI: 'public.png',
  });
}

/** narmast://challenge?from=<inviteCode> — opens today's challenge pre-loaded for a friend. */
export function buildChallengeLink(fromInviteCode: string): string {
  return Linking.createURL('challenge', { queryParams: { from: fromInviteCode } });
}
