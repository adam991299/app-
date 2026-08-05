import { StyleSheet, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { MotiView } from 'moti';
import type { LucideIcon } from 'lucide-react-native';
import type { SFSymbol } from 'expo-symbols';
import { IconSymbol } from '@/components/ui/IconSymbol';
import { useTheme } from '@/hooks/useTheme';

interface OnboardingHeroProps {
  sfSymbol: SFSymbol;
  fallback: LucideIcon;
  gradient: [string, string];
}

/** A simple, elegant animated hero graphic for onboarding — a soft gradient blob with
 * a floating icon, since we don't ship bespoke illustrations at launch. */
export function OnboardingHero({ sfSymbol, fallback, gradient }: OnboardingHeroProps) {
  const { isDark } = useTheme();

  return (
    <View style={styles.wrap}>
      <MotiView
        from={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', damping: 14, stiffness: 90 }}
        style={styles.blobWrap}
      >
        <LinearGradient
          colors={gradient}
          start={{ x: 0.1, y: 0.1 }}
          end={{ x: 0.9, y: 0.9 }}
          style={[styles.blob, { opacity: isDark ? 0.35 : 0.9 }]}
        />
      </MotiView>
      <MotiView
        from={{ translateY: 0 }}
        animate={{ translateY: -10 }}
        transition={{ type: 'timing', duration: 1800, loop: true, repeatReverse: true }}
        style={styles.iconWrap}
      >
        <IconSymbol sfSymbol={sfSymbol} fallback={fallback} size={72} color="#FFFFFF" weight="semibold" />
      </MotiView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', justifyContent: 'center', height: 260 },
  blobWrap: { position: 'absolute' },
  blob: { width: 220, height: 220, borderRadius: 64, transform: [{ rotate: '8deg' }] },
  iconWrap: { alignItems: 'center', justifyContent: 'center' },
});
