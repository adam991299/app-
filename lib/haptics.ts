import * as Haptics from 'expo-haptics';

/**
 * Every interactive control in the app should route through here rather than calling
 * expo-haptics directly, so the "feel" of the app stays consistent and is easy to tune
 * globally later. All calls are fire-and-forget and safe on platforms without a
 * Taptic Engine (Haptics silently no-ops on unsupported hardware).
 */
export const haptics = {
  tap: () => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light),
  buttonPress: () => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium),
  cardSelect: () => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light),
  success: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
  warning: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning),
  error: () => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error),
  selectionChange: () => Haptics.selectionAsync(),
};
