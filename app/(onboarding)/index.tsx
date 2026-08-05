import { useRef, useState } from 'react';
import {
  Alert,
  Dimensions,
  Platform,
  ScrollView,
  StyleSheet,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';
import { ArrowLeftIcon, MailIcon, PuzzleIcon, TargetIcon, UsersIcon } from 'lucide-react-native';
import { OnboardingHero } from '@/components/onboarding/OnboardingHero';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { TextField } from '@/components/ui/TextField';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { signInWithEmailOtp, verifyEmailOtp } from '@/lib/api/auth';
import { haptics } from '@/lib/haptics';
import { useAuthStore } from '@/store/useAuthStore';
import { useSettingsStore } from '@/store/useSettingsStore';

const { width } = Dimensions.get('window');

const PAGES = [
  {
    sfSymbol: 'target' as const,
    fallback: TargetIcon,
    gradient: ['#F17A54', '#E4572E'] as [string, string],
    headline: 'One number a day.',
    body: 'A daily trivia question with a numeric answer. Three guesses — higher or lower each time.',
  },
  {
    sfSymbol: 'puzzlepiece.fill' as const,
    fallback: PuzzleIcon,
    gradient: ['#7FCFC0', '#2A9D8F'] as [string, string],
    headline: 'One puzzle a day.',
    body: "A short pattern to crack. The timer just counts up — there's no pressure, only proof.",
  },
  {
    sfSymbol: 'person.2.fill' as const,
    fallback: UsersIcon,
    gradient: ['#F4C06A', '#D68A1E'] as [string, string],
    headline: 'Compare with friends.',
    body: 'Build a streak, climb the weekly leaderboard, and challenge a friend to beat your score.',
  },
];

type Step = 'pages' | 'email' | 'code';

export default function OnboardingScreen() {
  const { colors, isDark } = useTheme();
  const scrollRef = useRef<ScrollView>(null);
  const [page, setPage] = useState(0);
  const [step, setStep] = useState<Step>('pages');
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const completeOnboarding = useSettingsStore((s) => s.completeOnboarding);
  const signInApple = useAuthStore((s) => s.signInApple);
  const refreshProfile = useAuthStore((s) => s.refreshProfile);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.round(e.nativeEvent.contentOffset.x / width);
    if (next !== page) setPage(next);
  };

  const goToPage = (index: number) => {
    scrollRef.current?.scrollTo({ x: index * width, animated: true });
    setPage(index);
  };

  const finishSignIn = (method: string) => {
    track(AnalyticsEvent.OnboardingCompleted, { method });
    completeOnboarding();
    haptics.success();
  };

  const handleAppleSignIn = async () => {
    setBusy(true);
    try {
      await signInApple();
      finishSignIn('apple');
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
      finishSignIn('email');
    } catch (err: any) {
      Alert.alert('Invalid code', err?.message ?? 'Please try again.');
    } finally {
      setBusy(false);
    }
  };

  if (step !== 'pages') {
    return (
      <Screen padded>
        <View style={styles.emailStep}>
          <Button
            variant="tertiary"
            fullWidth={false}
            icon={<ArrowLeftIcon size={18} color={colors.accent} />}
            onPress={() => (step === 'code' ? setStep('email') : setStep('pages'))}
            style={styles.backButton}
          >
            Back
          </Button>

          <Text variant="title1" style={styles.emailHeadline}>
            {step === 'email' ? 'What’s your email?' : 'Enter your code'}
          </Text>
          <Text variant="subhead" tone="secondary" style={styles.emailBody}>
            {step === 'email'
              ? "We'll send you a one-time code — no password to remember."
              : `We sent a 6-digit code to ${email}.`}
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
            <TextField
              placeholder="123456"
              value={code}
              onChangeText={setCode}
              keyboardType="number-pad"
              maxLength={6}
              autoFocus
            />
          )}

          <Button
            onPress={step === 'email' ? handleSendCode : handleVerifyCode}
            loading={busy}
            style={styles.emailSubmit}
          >
            {step === 'email' ? 'Send code' : 'Verify'}
          </Button>
        </View>
      </Screen>
    );
  }

  return (
    <Screen edges={['top', 'bottom']}>
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={onScroll}
        style={styles.pager}
      >
        {PAGES.map((p, i) => (
          <View key={i} style={[styles.page, { width }]}>
            <OnboardingHero sfSymbol={p.sfSymbol} fallback={p.fallback} gradient={p.gradient} />
            <Text variant="title1" center style={styles.headline}>
              {p.headline}
            </Text>
            <Text variant="body" tone="secondary" center style={styles.body}>
              {p.body}
            </Text>
          </View>
        ))}
      </ScrollView>

      <View style={styles.footer}>
        <View style={styles.dots}>
          {PAGES.map((_, i) => (
            <View
              key={i}
              style={[
                styles.dot,
                { backgroundColor: i === page ? colors.accent : colors.border, width: i === page ? 20 : 8 },
              ]}
            />
          ))}
        </View>

        {page < PAGES.length - 1 ? (
          <Button onPress={() => goToPage(page + 1)}>Continue</Button>
        ) : (
          <View style={styles.signInGroup}>
            {Platform.OS === 'ios' ? (
              <AppleAuthentication.AppleAuthenticationButton
                buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
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
                Continue with Apple
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
            <Text variant="caption1" tone="tertiary" center style={styles.legal}>
              By continuing you agree to our Terms and Privacy Policy.
            </Text>
          </View>
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  pager: { flex: 1 },
  page: { alignItems: 'center', justifyContent: 'center', paddingHorizontal: spacing.xl },
  headline: { marginTop: spacing.lg },
  body: { marginTop: spacing.xs, maxWidth: 300 },
  footer: { paddingHorizontal: spacing.lg, paddingBottom: spacing.lg, gap: spacing.md, alignItems: 'center' },
  dots: { flexDirection: 'row', gap: 6, alignItems: 'center' },
  dot: { height: 8, borderRadius: 4 },
  signInGroup: { gap: spacing.sm, width: '100%' },
  appleButton: { width: '100%', height: 52 },
  legal: { paddingHorizontal: spacing.md },
  emailStep: { flex: 1, justifyContent: 'center', gap: spacing.sm },
  backButton: { marginBottom: spacing.md, paddingHorizontal: 0 },
  emailHeadline: { marginBottom: spacing.xxs },
  emailBody: { marginBottom: spacing.md },
  emailSubmit: { marginTop: spacing.sm },
});
