import { StyleSheet, Text, View } from 'react-native';
import Svg, { Defs, LinearGradient, Path, Stop } from 'react-native-svg';

import type { ChartPoint } from '@/lib/types';
import { money } from '@/lib/format';
import { colors } from '@/theme/tokens';

const WIDTH = 800;
const HEIGHT = 196;
const TOP = 12;
const BOTTOM = 22;

function buildPath(points: ChartPoint[]) {
  if (points.length < 2) return { line: '', area: '', min: 0, max: 0 };
  const values = points.map((item) => Number(item.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const mapped = values.map((value, index) => ({
    x: (index / (values.length - 1)) * WIDTH,
    y: TOP + (1 - (value - min) / range) * (HEIGHT - TOP - BOTTOM),
  }));
  const line = mapped.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  const area = `${line} L ${WIDTH} ${HEIGHT - BOTTOM} L 0 ${HEIGHT - BOTTOM} Z`;
  return { line, area, min, max };
}

export function PortfolioChart({ points }: { points: ChartPoint[] }) {
  const chart = buildPath(points);
  const change = points.length > 1 ? Number(points.at(-1)?.value) - Number(points[0].value) : 0;
  return (
    <View style={styles.root}>
      <View style={styles.legendRow}>
        <View>
          <Text style={styles.legendLabel}>30-DAY CHANGE</Text>
          <Text style={[styles.change, { color: change >= 0 ? colors.positive : colors.negative }]}>
            {change >= 0 ? '+' : ''}{money(change)}
          </Text>
        </View>
        <View style={styles.rangeBadge}>
          <Text style={styles.rangeText}>1M</Text>
        </View>
      </View>
      <View style={styles.chartWrap}>
        <Svg width="100%" height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
          <Defs>
            <LinearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={colors.teal} stopOpacity="0.24" />
              <Stop offset="1" stopColor={colors.teal} stopOpacity="0.01" />
            </LinearGradient>
          </Defs>
          <Path d={chart.area} fill="url(#chartFill)" />
          <Path
            d={chart.line}
            fill="none"
            stroke={colors.teal}
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        </Svg>
        <Text style={[styles.axisLabel, styles.axisTop]}>{money(chart.max, true)}</Text>
        <Text style={[styles.axisLabel, styles.axisBottom]}>{money(chart.min, true)}</Text>
      </View>
      <View style={styles.dateRow}>
        <Text style={styles.dateText}>30 days ago</Text>
        <Text style={styles.dateText}>Today</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, paddingTop: 18 },
  legendRow: {
    paddingHorizontal: 18,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  legendLabel: { color: colors.inkFaint, fontSize: 9, fontWeight: '700', letterSpacing: 1.2 },
  change: { fontSize: 14, fontWeight: '700', marginTop: 5, fontVariant: ['tabular-nums'] },
  rangeBadge: {
    height: 28,
    minWidth: 38,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surfaceMuted,
    justifyContent: 'center',
    alignItems: 'center',
  },
  rangeText: { color: colors.ink, fontSize: 10, fontWeight: '700' },
  chartWrap: { height: HEIGHT, marginTop: -8, overflow: 'hidden' },
  axisLabel: {
    position: 'absolute',
    right: 8,
    color: colors.inkFaint,
    fontSize: 9,
    backgroundColor: colors.surface,
    paddingLeft: 4,
  },
  axisTop: { top: 11 },
  axisBottom: { bottom: 19 },
  dateRow: {
    marginTop: -14,
    paddingHorizontal: 18,
    paddingBottom: 14,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  dateText: { color: colors.inkFaint, fontSize: 9 },
});

