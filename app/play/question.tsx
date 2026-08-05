import { useEffect, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { XIcon } from 'lucide-react-native';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { ProgressDots } from '@/components/ui/ProgressDots';
import { Screen } from '@/components/ui/Screen';
import { LoadingState } from '@/components/ui/StateViews';
import { Text } from '@/components/ui/Text';
import { GuessFeedback } from '@/components/game/GuessFeedback';
import { GuessHistory } from '@/components/game/GuessHistory';
import { NumericKeypad } from '@/components/keypad/NumericKeypad';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { haptics } from '@/lib/haptics';
import { useGameStore } from '@/store/useGameStore';
import type { QuestionGuess } from '@/types/database';

const MAX_GUESSES = 3;

export default function PlayQuestionScreen() {
  const { colors } = useTheme();
  const today = useGameStore((s) => s.today);
  const guessQuestion = useGameStore((s) => s.guessQuestion);

  const question = today?.question;
  const existingGuesses = today?.questionAttempt?.guesses ?? [];

  const [inputValue, setInputValue] = useState('');
  const [guesses, setGuesses] = useState<QuestionGuess[]>(existingGuesses);
  const [lastDirection, setLastDirection] = useState<QuestionGuess['direction'] | null>(
    existingGuesses.at(-1)?.direction ?? null
  );
  const [submitting, setSubmitting] = useState(false);
  const startedAt = useRef(Date.now());
  const hasStartedTracking = useRef(false);

  useEffect(() => {
    if (question && !hasStartedTracking.current) {
      hasStartedTracking.current = true;
      track(AnalyticsEvent.QuestionStarted, { category: question.category });
    }
  }, [question]);

  const remaining = MAX_GUESSES - guesses.length;

  if (!question) {
    return (
      <Screen>
        <LoadingState />
      </Screen>
    );
  }

  const handleSubmit = async () => {
    const value = Number(inputValue);
    if (!Number.isFinite(value) || inputValue.length === 0) return;

    setSubmitting(true);
    haptics.selectionChange();
    try {
      const elapsed = Math.floor((Date.now() - startedAt.current) / 1000);
      const result = await guessQuestion(value, elapsed);
      track(AnalyticsEvent.QuestionGuessSubmitted, { direction: result.direction, guess_count: result.guess_count });

      const nextGuesses: QuestionGuess[] = [...guesses, { value, direction: result.direction }];
      setGuesses(nextGuesses);
      setLastDirection(result.direction);
      setInputValue('');

      if (result.solved) haptics.success();
      else if (result.is_final) haptics.error();
      else haptics.warning();

      if (result.is_final) {
        track(AnalyticsEvent.QuestionCompleted, { solved: result.solved, guess_count: result.guess_count });
        setTimeout(() => router.replace('/results/question'), 900);
      }
    } catch (err: any) {
      Alert.alert('Something went wrong', err?.message ?? 'Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen edges={['top', 'bottom']}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
        <Text variant="headline">Today's Question</Text>
        <View style={{ width: 24 }} />
      </View>

      <View style={styles.content}>
        <Badge label={question.category} tone="accent" />
        <Text variant="title2" style={styles.questionText}>
          {question.question_text}
        </Text>

        <GuessHistory guesses={guesses} unit={question.unit} />
        <GuessFeedback direction={lastDirection} />

        <View style={styles.displayWrap}>
          <Text variant="largeTitle" weight="700" style={[styles.display, { color: inputValue ? colors.text : colors.textTertiary }]}>
            {inputValue || '?'}
            {question.unit ? <Text variant="title2" tone="secondary"> {question.unit}</Text> : null}
          </Text>
        </View>

        <ProgressDots total={MAX_GUESSES} filled={remaining} />
      </View>

      <View style={styles.bottom}>
        <NumericKeypad value={inputValue} onChange={setInputValue} maxLength={9} />
        <Button onPress={handleSubmit} disabled={inputValue.length === 0} loading={submitting} style={styles.guessButton}>
          Guess
        </Button>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  content: { flex: 1, paddingHorizontal: spacing.lg, gap: spacing.sm, alignItems: 'center' },
  questionText: { textAlign: 'center' },
  displayWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 80 },
  display: { fontVariant: ['tabular-nums'] },
  bottom: { paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, gap: spacing.md },
  guessButton: { marginTop: spacing.xxs },
});
