import type { ExpoConfig } from 'expo/config';

// All copy in this file (permission strings, notification text, etc.) is written to be
// clear and honest for App Review — it should read the same to a user as it does to a reviewer.

const BUNDLE_IDENTIFIER = 'com.narmast.app';
const SCHEME = 'narmast';

// Populate this once you've run `eas init` — see README.md.
const EAS_PROJECT_ID = process.env.EAS_PROJECT_ID ?? '00000000-0000-0000-0000-000000000000';

const config: ExpoConfig = {
  name: 'Närmast',
  slug: 'narmast',
  scheme: SCHEME,
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'automatic',
  primaryColor: '#E4572E',
  backgroundColor: '#FFFDF9',
  // New Architecture is mandatory as of RN 0.86 / SDK 57 — there's no opt-in flag anymore.
  ios: {
    bundleIdentifier: BUNDLE_IDENTIFIER,
    supportsTablet: false,
    icon: {
      light: './assets/icon.png',
      dark: './assets/icon.png',
      tinted: './assets/icon.png',
    },
    infoPlist: {
      // NSContactsUsageDescription is set via the expo-contacts plugin config below,
      // not duplicated here.
      ITSAppUsesNonExemptEncryption: false,
    },
    entitlements: {
      'com.apple.developer.applesignin': ['Default'],
    },
    // Challenge links use the custom `narmast://` scheme (see lib/share.ts), which
    // needs no extra config. If you later host narmast.app with a real
    // apple-app-site-association file, add `associatedDomains: ['applinks:narmast.app']`
    // here for Universal Links (https://narmast.app/... opening the app directly).
  },
  android: {
    package: BUNDLE_IDENTIFIER,
    adaptiveIcon: {
      backgroundColor: '#FFFDF9',
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
    permissions: ['READ_CONTACTS'],
  },
  web: {
    favicon: './assets/favicon.png',
    bundler: 'metro',
  },
  // Splash screen is configured entirely through the expo-splash-screen plugin below —
  // the top-level `splash` config field was removed from the Expo config schema.
  plugins: [
    'expo-router',
    [
      'expo-splash-screen',
      {
        image: './assets/splash-icon.png',
        imageWidth: 160,
        resizeMode: 'contain',
        backgroundColor: '#FFFDF9',
        dark: {
          image: './assets/splash-icon.png',
          backgroundColor: '#161512',
        },
      },
    ],
    [
      'expo-notifications',
      {
        icon: './assets/icon.png',
        color: '#E4572E',
      },
    ],
    [
      'expo-contacts',
      {
        contactsPermission:
          'Närmast can check which of your contacts already play Närmast so you can add them as friends. Your contact list stays on your device and is never uploaded or stored on our servers.',
      },
    ],
    'expo-apple-authentication',
    'expo-secure-store',
    'expo-system-ui',
    '@react-native-community/datetimepicker',
  ],
  extra: {
    eas: {
      projectId: EAS_PROJECT_ID,
    },
  },
  experiments: {
    typedRoutes: true,
  },
  updates: {
    url: `https://u.expo.dev/${EAS_PROJECT_ID}`,
  },
  runtimeVersion: {
    policy: 'appVersion',
  },
};

export default config;
