import { SymbolView, type SFSymbol } from 'expo-symbols';
import { Platform } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';

interface IconSymbolProps {
  /** SF Symbol name, used on iOS — browse names in the Apple SF Symbols app. */
  sfSymbol: SFSymbol;
  /** Lucide icon component, used as the fallback on Android/web. */
  fallback: LucideIcon;
  size?: number;
  color: string;
  weight?: 'regular' | 'medium' | 'semibold' | 'bold';
}

/**
 * SF Symbols everywhere on iOS for an authentic native feel, Lucide as the
 * cross-platform fallback (Android/web) — see the design-system rule in AGENTS.md.
 */
export function IconSymbol({ sfSymbol, fallback: Fallback, size = 24, color, weight = 'regular' }: IconSymbolProps) {
  if (Platform.OS === 'ios') {
    return (
      <SymbolView
        name={sfSymbol}
        size={size}
        tintColor={color}
        weight={weight}
        fallback={<Fallback size={size} color={color} />}
      />
    );
  }
  return <Fallback size={size} color={color} />;
}
