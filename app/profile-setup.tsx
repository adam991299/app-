import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Button } from '@/components/ui/Button';
import { Avatar } from '@/components/ui/Avatar';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { TextField } from '@/components/ui/TextField';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { haptics } from '@/lib/haptics';
import { useAuthStore } from '@/store/useAuthStore';

const EMOJI_OPTIONS = ['🙂', '🦊', '🐻', '🦋', '🐢', '🦉', '🐙', '🦁', '🐝', '🦈', '🐨', '🦄'];
const COLOR_OPTIONS = ['#E4572E', '#2A9D8F', '#D68A1E', '#8A7D6B', '#C8451F', '#1D6E64', '#A33718', '#6B6052'];

export default function ProfileSetupScreen() {
  const { colors } = useTheme();
  const profile = useAuthStore((s) => s.profile);
  const saveProfileSetup = useAuthStore((s) => s.saveProfileSetup);
  const [name, setName] = useState(profile?.display_name === 'Player' ? '' : profile?.display_name ?? '');
  const [emoji, setEmoji] = useState(profile?.avatar_emoji ?? EMOJI_OPTIONS[0]);
  const [color, setColor] = useState(profile?.avatar_color ?? COLOR_OPTIONS[0]);
  const [busy, setBusy] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) {
      Alert.alert('Pick a display name', 'Friends will see this on the leaderboard.');
      return;
    }
    setBusy(true);
    try {
      await saveProfileSetup({ display_name: name.trim().slice(0, 24), avatar_emoji: emoji, avatar_color: color });
      haptics.success();
    } catch (err: any) {
      Alert.alert('Could not save', err?.message ?? 'Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen padded>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <Text variant="title1" style={styles.headline}>
          Set up your profile
        </Text>
        <Text variant="subhead" tone="secondary" style={styles.body}>
          This is how friends will recognize you on the leaderboard.
        </Text>

        <View style={styles.avatarPreview}>
          <Avatar emoji={emoji} color={color} size={88} />
        </View>

        <TextField
          label="Display name"
          placeholder="Your name"
          value={name}
          onChangeText={setName}
          maxLength={24}
          autoCapitalize="words"
        />

        <Text variant="footnote" tone="secondary" style={styles.sectionLabel}>
          Avatar
        </Text>
        <View style={styles.grid}>
          {EMOJI_OPTIONS.map((e) => (
            <Pressable
              key={e}
              onPress={() => {
                haptics.selectionChange();
                setEmoji(e);
              }}
              style={[
                styles.emojiCell,
                {
                  borderColor: e === emoji ? colors.accent : colors.border,
                  backgroundColor: colors.card,
                },
              ]}
            >
              <Text style={styles.emojiText}>{e}</Text>
            </Pressable>
          ))}
        </View>

        <Text variant="footnote" tone="secondary" style={styles.sectionLabel}>
          Color
        </Text>
        <View style={styles.grid}>
          {COLOR_OPTIONS.map((c) => (
            <Pressable
              key={c}
              onPress={() => {
                haptics.selectionChange();
                setColor(c);
              }}
              style={[
                styles.colorCell,
                { backgroundColor: c, borderColor: c === color ? colors.text : 'transparent' },
              ]}
            />
          ))}
        </View>
      </ScrollView>

      <Button onPress={handleSave} loading={busy} style={styles.submit}>
        Start playing
      </Button>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingBottom: spacing.lg },
  headline: { marginTop: spacing.md },
  body: { marginTop: spacing.xxs, marginBottom: spacing.lg },
  avatarPreview: { alignItems: 'center', marginBottom: spacing.lg },
  sectionLabel: { marginTop: spacing.lg, marginBottom: spacing.xs },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  emojiCell: {
    width: 52,
    height: 52,
    borderRadius: radius.md,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emojiText: { fontSize: 26 },
  colorCell: { width: 40, height: 40, borderRadius: 20, borderWidth: 3 },
  submit: { marginTop: spacing.md, marginBottom: spacing.sm },
});
