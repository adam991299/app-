import { forwardRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { palette, radius, spacing } from '@/constants/theme';

export interface ShareCardSection {
  label: string;
  grid: string[];
  detail: string;
}

interface ShareCardProps {
  date: string;
  streak: number;
  sections: ShareCardSection[];
}

/**
 * The shareable result image — deliberately rendered with a fixed brand look (dark
 * coral gradient, white text) regardless of the sharer's light/dark app setting, the
 * same way Wordle's share grid always renders the same way. Captured off-screen via
 * react-native-view-shot (see lib/share.ts).
 */
export const ShareCard = forwardRef<View, ShareCardProps>(({ date, streak, sections }, ref) => {
  return (
    <View ref={ref} collapsable={false} style={styles.wrap}>
      <LinearGradient colors={[palette.coral[600], palette.coral[900]]} style={styles.gradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
        <View style={styles.header}>
          <Text style={styles.wordmark}>Närmast</Text>
          <Text style={styles.date}>{date}</Text>
        </View>

        <View style={styles.sections}>
          {sections.map((section) => (
            <View key={section.label} style={styles.section}>
              <Text style={styles.sectionLabel}>{section.label}</Text>
              <View style={styles.grid}>
                {section.grid.map((square, i) => (
                  <Text key={i} style={styles.square}>
                    {square}
                  </Text>
                ))}
              </View>
              <Text style={styles.sectionDetail}>{section.detail}</Text>
            </View>
          ))}
        </View>

        <View style={styles.footer}>
          <Text style={styles.streak}>🔥 {streak}-day streak</Text>
          <Text style={styles.cta}>Beat my score →</Text>
        </View>
      </LinearGradient>
    </View>
  );
});
ShareCard.displayName = 'ShareCard';

const CARD_WIDTH = 320;

const styles = StyleSheet.create({
  wrap: { width: CARD_WIDTH, borderRadius: radius.xl, overflow: 'hidden' },
  gradient: { padding: spacing.lg, gap: spacing.lg },
  header: { alignItems: 'center', gap: 2 },
  wordmark: { fontSize: 22, fontWeight: '700', color: '#FFFFFF', letterSpacing: 0.2 },
  date: { fontSize: 13, color: 'rgba(255,255,255,0.75)' },
  sections: { gap: spacing.md },
  section: { alignItems: 'center', gap: spacing.xxs },
  sectionLabel: { fontSize: 12, fontWeight: '600', color: 'rgba(255,255,255,0.7)', letterSpacing: 0.5, textTransform: 'uppercase' },
  grid: { flexDirection: 'row', gap: 6 },
  square: { fontSize: 28, lineHeight: 32 },
  sectionDetail: { fontSize: 14, color: '#FFFFFF', fontWeight: '600' },
  footer: {
    alignItems: 'center',
    gap: 2,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(255,255,255,0.25)',
    paddingTop: spacing.sm,
  },
  streak: { fontSize: 15, fontWeight: '700', color: '#FFFFFF' },
  cta: { fontSize: 13, color: 'rgba(255,255,255,0.85)' },
});
