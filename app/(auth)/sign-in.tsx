import { useState } from 'react';
import { Alert, Platform, StyleSheet, View } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';
import { ArrowLeftIcon, FlameIcon, MailIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { TextField } from '@/components/ui/TextField';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { signInWithEmailOtp, verifyEmailOtp } from '@/lib/api/auth';
import { useAuthStore } from '@/store/useAuthStore';

type Step = 'welcome' | 'email' | 'code';

/** Shown when a returning user is signed out (e.g. after Settings → Sign Out) — a
 * lighter-weight re-entry point than the full first-run onboarding carousel. */
export default function SignInScreen() {
  const { colors, isDark } = useTheme();
  const [step, setStep] = useState<Step>('welcome');
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const signInApple = useAuthStore((s) => s.signInApple);
  const refreshProfile = useAuthStore((s) => s.refreshProfile);

  const handleAppleSignIn = async () => {
    setBusy(true);
    try {
      await signInApple();
    } catch (err: any) {
      if (err?.code !== 'ERR_REQUEST_CANCELED') {
        Alert.alert('Sign in failed', err?.message ?? 'Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  const handleSendCode = async () => {
    if (!email.includes('@')) {
      Alert.alert('Enter a valid email address');
      return;
    }
    setBusy(true);
    try {
      await signInWithEmailOtp(email);
      setStep('code');
    } catch (err: any) {
      Alert.alert('Could not send code', err?.message ?? 'Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const handleVerifyCode = async () => {
    if (code.length < 6) return;
    setBusy(true);
    try {
      await verifyEmailOtp(email, code);
      await refreshProfile();
    } catch (err: any) {
      Alert.alert('Invalid code', err?.message ?? 'Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen padded>
      <View style={styles.wrap}>
        {step === 'welcome' ? (
          <>
            <View style={[styles.iconWrap, { backgroundColor: colors.accentSoft }]}>
              <FlameIcon size={32} color={colors.accent} />
            </View>
            <Text variant="title1" center style={styles.headline}>
              Welcome back
            </Text>
            <Text variant="subhead" tone="secondary" center style={styles.body}>
              Sign back in to pick up your streak where you left off.
            </Text>

            <View style={styles.signInGroup}>
              {Platform.OS === 'ios' ? (
                <AppleAuthentication.AppleAuthenticationButton
                  buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
                  buttonStyle={
                    isDark
                      ? AppleAuthentication.AppleAuthenticationButtonStyle.WHITE
                      : AppleAuthentication.AppleAuthenticationButtonStyle.BLACK
                  }
                  cornerRadius={16}
                  style={styles.appleButton}
                  onPress={handleAppleSignIn}
                />
              ) : (
                <Button onPress={handleAppleSignIn} loading={busy}>
                  Sign in with Apple
                </Button>
              )}
              <Button
                variant="tertiary"
                icon={<MailIcon size={18} color={colors.accent} />}
                disabled={busy}
                onPress={() => setStep('email')}
              >
                Continue with email
              </Button>
            </View>
          </>
        ) : (
          <>
            <Button
              variant="tertiary"
              fullWidth={false}
              icon={<ArrowLeftIcon size={18} color={colors.accent} />}
              onPress={() => (step === 'code' ? setStep('email') : setStep('welcome'))}
              style={styles.backButton}
            >
              Back
            </Button>
            <Text variant="title1" style={styles.emailHeadline}>
              {step === 'email' ? 'What’s your email?' : 'Enter your code'}
            </Text>
            <Text variant="subhead" tone="secondary" style={styles.emailBody}>
              {step === 'email' ? "We'll send you a one-time code." : `We sent a 6-digit code to ${email}.`}
            </Text>
            {step === 'email' ? (
              <TextField
                placeholder="you@example.com"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                autoComplete="email"
                autoFocus
              />
            ) : (
              <TextField placeholder="123456" value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={6} autoFocus />
            )}
            <Button onPress={step === 'email' ? handleSendCode : handleVerifyCode} loading={busy} style={styles.submit}>
              {step === 'email' ? 'Send code' : 'Verify'}
            </Button>
          </>
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, justifyContent: 'center' },
  iconWrap: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    marginBottom: spacing.md,
  },
  headline: { marginBottom: spacing.xxs },
  body: { marginBottom: spacing.xl, maxWidth: 280, alignSelf: 'center' },
  signInGroup: { gap: spacing.sm },
  appleButton: { width: '100%', height: 52 },
  backButton: { marginBottom: spacing.md, paddingHorizontal: 0, alignSelf: 'flex-start' },
  emailHeadline: { marginBottom: spacing.xxs },
  emailBody: { marginBottom: spacing.md },
  submit: { marginTop: spacing.sm },
});
