import { StyleSheet, View } from 'react-native';
import { Text } from './Text';

interface AvatarProps {
  emoji: string;
  color: string;
  size?: number;
}

export function Avatar({ emoji, color, size = 44 }: AvatarProps) {
  return (
    <View
      style={[
        styles.base,
        { width: size, height: size, borderRadius: size / 2, backgroundColor: `${color}26` },
      ]}
    >
      <Text style={{ fontSize: size * 0.5, lineHeight: size * 0.58 }}>{emoji}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  base: { alignItems: 'center', justifyContent: 'center' },
});
