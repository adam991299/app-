import { useState } from 'react';
import { Alert, Pressable, ScrollView, Share, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import * as Contacts from 'expo-contacts';
import { CheckIcon, ContactIcon, CopyIcon, ShareIcon, XIcon } from 'lucide-react-native';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { TextField } from '@/components/ui/TextField';
import { spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/useTheme';
import { AnalyticsEvent, track } from '@/lib/analytics';
import { addFriendByCode, findUserByCode } from '@/lib/api/friends';
import { haptics } from '@/lib/haptics';
import { useAuthStore } from '@/store/useAuthStore';
import type { FindUserByCodeRow } from '@/types/database';

export default function AddFriendScreen() {
  const { colors } = useTheme();
  const profile = useAuthStore((s) => s.profile);
  const [code, setCode] = useState('');
  const [preview, setPreview] = useState<FindUserByCodeRow | null>(null);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState(false);
  const [copied, setCopied] = useState(false);
  const [contactsStatus, setContactsStatus] = useState<'idle' | 'loading' | 'granted' | 'denied'>('idle');
  const [contacts, setContacts] = useState<Contacts.ExistingContact[]>([]);

  const handleCopyCode = async () => {
    if (!profile) return;
    await Clipboard.setStringAsync(profile.invite_code);
    setCopied(true);
    haptics.tap();
    setTimeout(() => setCopied(false), 1500);
  };

  const handleShareCode = async () => {
    if (!profile) return;
    await Share.share({ message: `Add me on Närmast! My code is ${profile.invite_code}` });
  };

  const handleSearch = async () => {
    if (code.trim().length < 4) return;
    setSearching(true);
    setPreview(null);
    try {
      const found = await findUserByCode(code);
      if (!found) Alert.alert('No player found', 'Double-check the code and try again.');
      setPreview(found);
    } catch (err: any) {
      Alert.alert('Something went wrong', err?.message ?? 'Please try again.');
    } finally {
      setSearching(false);
    }
  };

  const handleAdd = async () => {
    setAdding(true);
    try {
      await addFriendByCode(code);
      track(AnalyticsEvent.FriendAdded, { method: 'code' });
      haptics.success();
      router.back();
    } catch (err: any) {
      Alert.alert('Could not add friend', err?.message ?? 'Please try again.');
    } finally {
      setAdding(false);
    }
  };

  const handleFindContacts = async () => {
    setContactsStatus('loading');
    const { status } = await Contacts.requestPermissionsAsync();
    if (status !== 'granted') {
      setContactsStatus('denied');
      return;
    }
    const { data } = await Contacts.getContactsAsync({ fields: [Contacts.Fields.Name], sort: Contacts.SortTypes.FirstName });
    setContacts(data.filter((c) => c.name).slice(0, 50));
    setContactsStatus('granted');
  };

  const handleInviteContact = async (name: string) => {
    await Share.share({ message: `Hey ${name.split(' ')[0]}, join me on Närmast! My code is ${profile?.invite_code}` });
  };

  return (
    <Screen padded>
      <View style={styles.header}>
        <Text variant="title2">Add a Friend</Text>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <XIcon size={24} color={colors.textSecondary} />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <Card style={styles.myCodeCard}>
          <Text variant="footnote" tone="secondary">
            Your invite code
          </Text>
          <Text variant="largeTitle" weight="700" style={styles.codeText}>
            {profile?.invite_code ?? '——————'}
          </Text>
          <View style={styles.codeActions}>
            <Button variant="secondary" size="medium" fullWidth={false} icon={copied ? <CheckIcon size={16} color={colors.accent} /> : <CopyIcon size={16} color={colors.accent} />} onPress={handleCopyCode}>
              {copied ? 'Copied' : 'Copy'}
            </Button>
            <Button variant="tertiary" size="medium" fullWidth={false} icon={<ShareIcon size={16} color={colors.accent} />} onPress={handleShareCode}>
              Share
            </Button>
          </View>
        </Card>

        <Text variant="footnote" tone="secondary" style={styles.sectionLabel}>
          ENTER A CODE
        </Text>
        <View style={styles.searchRow}>
          <View style={{ flex: 1 }}>
            <TextField
              placeholder="e.g. ANNA42"
              value={code}
              onChangeText={(t) => setCode(t.toUpperCase())}
              autoCapitalize="characters"
              maxLength={8}
            />
          </View>
          <Button size="medium" fullWidth={false} onPress={handleSearch} loading={searching} disabled={code.length < 4}>
            Find
          </Button>
        </View>

        {preview ? (
          <Card style={styles.previewCard}>
            <Avatar emoji={preview.avatar_emoji} color={preview.avatar_color} size={44} />
            <Text variant="headline" style={{ flex: 1 }}>
              {preview.display_name}
            </Text>
            <Button size="medium" fullWidth={false} onPress={handleAdd} loading={adding}>
              Add
            </Button>
          </Card>
        ) : null}

        <Text variant="footnote" tone="secondary" style={styles.sectionLabel}>
          FROM YOUR CONTACTS
        </Text>
        {contactsStatus === 'idle' || contactsStatus === 'loading' ? (
          <Button
            variant="secondary"
            icon={<ContactIcon size={18} color={colors.accent} />}
            onPress={handleFindContacts}
            loading={contactsStatus === 'loading'}
          >
            Find contacts to invite
          </Button>
        ) : contactsStatus === 'denied' ? (
          <Text variant="subhead" tone="secondary">
            Contacts access was denied. You can still invite friends by sharing your code above.
          </Text>
        ) : (
          <View style={styles.contactsList}>
            {contacts.length === 0 ? (
              <Text variant="subhead" tone="secondary">
                No contacts found.
              </Text>
            ) : (
              contacts.map((c) => (
                <View key={c.id} style={styles.contactRow}>
                  <Text variant="subhead" style={{ flex: 1 }}>
                    {c.name}
                  </Text>
                  <Button variant="tertiary" size="medium" fullWidth={false} onPress={() => handleInviteContact(c.name ?? '')}>
                    Invite
                  </Button>
                </View>
              ))
            )}
          </View>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: spacing.sm },
  scroll: { gap: spacing.md, paddingBottom: spacing.xxl },
  myCodeCard: { alignItems: 'center', gap: spacing.xs, paddingVertical: spacing.lg },
  codeText: { letterSpacing: 4 },
  codeActions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xxs },
  sectionLabel: { letterSpacing: 0.5, marginTop: spacing.xs },
  searchRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'flex-start' },
  previewCard: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  contactsList: { gap: spacing.xxs },
  contactRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.xxs },
});
