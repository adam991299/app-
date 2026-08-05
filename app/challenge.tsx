import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Button } from '@/components/ui/Button';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { Avatar } from '@/components/ui/Avatar';
import { spacing } from '@/constants/theme';
import { addFriendByCode, findUserByCode } from '@/lib/api/friends';
import { haptics } from '@/lib/haptics';
import type { FindUserByCodeRow } from '@/types/database';

/** Handles narmast://challenge?from=<inviteCode> — opened via a shared result link. */
export default function ChallengeScreen() {
  const { from } = useLocalSearchParams<{ from?: string }>();
  const [challenger, setChallenger] = useState<FindUserByCodeRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!from) {
      router.replace('/(tabs)');
      return;
    }
    findUserByCode(from)
      .then((user) => (user ? setChallenger(user) : setNotFound(true)))
      .catch(() => setNotFound(true));
  }, [from]);

  useEffect(() => {
    if (notFound) router.replace('/(tabs)');
  }, [notFound]);

  const handleAdd = async () => {
    if (!from) return;
    setBusy(true);
    try {
      await addFriendByCode(from);
      haptics.success();
      router.replace('/(tabs)/friends');
    } catch {
      router.replace('/(tabs)');
    } finally {
      setBusy(false);
    }
  };

  if (!from || notFound) {
    return null;
  }

  return (
    <Screen padded>
      <View style={styles.wrap}>
        {challenger ? (
          <>
            <Avatar emoji={challenger.avatar_emoji} color={challenger.avatar_color} size={72} />
            <Text variant="title2" center style={styles.headline}>
              {challenger.display_name} challenged you!
            </Text>
            <Text variant="subhead" tone="secondary" center style={styles.body}>
              Add them as a friend to compare today's results and climb the leaderboard together.
            </Text>
            <Button onPress={handleAdd} loading={busy} style={styles.action}>
              Add {challenger.display_name}
            </Button>
            <Button variant="tertiary" onPress={() => router.replace('/(tabs)')}>
              Not now
            </Button>
          </>
        ) : (
          <Text tone="secondary">Loading…</Text>
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.xs },
  headline: { marginTop: spacing.sm },
  body: { marginBottom: spacing.md, maxWidth: 280 },
  action: { marginTop: spacing.sm },
});
