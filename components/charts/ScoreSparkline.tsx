import { View } from 'react-native';
import Svg, { Circle, Line, Polyline } from 'react-native-svg';
import { useTheme } from '@/hooks/useTheme';

interface ScoreSparklineProps {
  values: number[];
  width?: number;
  height?: number;
}

/** Minimal line chart (no axes/labels, Apple Health–style sparkline) of recent scores. */
export function ScoreSparkline({ values, width = 300, height = 80 }: ScoreSparklineProps) {
  const { colors } = useTheme();
  if (values.length < 2) {
    return (
      <View style={{ width, height, justifyContent: 'center' }}>
        <Line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke={colors.border} strokeWidth={1} strokeDasharray="4,4" />
      </View>
    );
  }

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(max - min, 1);
  const padding = 8;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * (width - padding * 2) + padding;
    const y = height - padding - ((v - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  const [lastX, lastY] = points[points.length - 1].split(',').map(Number);

  return (
    <Svg width={width} height={height}>
      <Polyline points={points.join(' ')} fill="none" stroke={colors.accent} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      <Circle cx={lastX} cy={lastY} r={4} fill={colors.accent} />
    </Svg>
  );
}
