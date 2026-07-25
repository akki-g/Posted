import { StyleSheet, Text, View } from 'react-native';
import Svg, { Defs, Line, LinearGradient, Path, Rect, Stop } from 'react-native-svg';

import { money } from '@/lib/format';
import type { PriceBar } from '@/lib/marketTypes';
import { colors } from '@/theme/tokens';

const WIDTH = 900;
const HEIGHT = 292;
const PRICE_TOP = 20;
const PRICE_BOTTOM = 72;
const VOLUME_HEIGHT = 42;

function chartGeometry(points: PriceBar[]) {
  if (points.length < 2) {
    return { line: '', area: '', min: 0, max: 0, maxVolume: 0 };
  }
  const values = points.map((item) => item.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const mapped = values.map((value, index) => ({
    x: (index / (values.length - 1)) * WIDTH,
    y: PRICE_TOP + (1 - (value - min) / range) * (HEIGHT - PRICE_TOP - PRICE_BOTTOM),
  }));
  const line = mapped
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ');
  const baseline = HEIGHT - PRICE_BOTTOM;
  return {
    line,
    area: `${line} L ${WIDTH} ${baseline} L 0 ${baseline} Z`,
    min,
    max,
    maxVolume: Math.max(...points.map((item) => item.volume), 1),
  };
}

export function StockPriceChart({ points }: { points: PriceBar[] }) {
  const chart = chartGeometry(points);
  if (points.length < 2) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>Price history unavailable</Text>
        <Text style={styles.emptyText}>Try another range or configure a market-data provider.</Text>
      </View>
    );
  }
  const change = points.at(-1)!.close - points[0].close;
  const lineColor = change >= 0 ? colors.teal : colors.negative;
  const volumeWidth = Math.max(0.8, WIDTH / points.length - 0.6);

  return (
    <View style={styles.root}>
      <Svg width="100%" height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
        <Defs>
          <LinearGradient id="stockChartFill" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={lineColor} stopOpacity="0.22" />
            <Stop offset="1" stopColor={lineColor} stopOpacity="0.01" />
          </LinearGradient>
        </Defs>
        {[0.25, 0.5, 0.75].map((offset) => (
          <Line
            key={offset}
            x1="0"
            x2={WIDTH}
            y1={PRICE_TOP + (HEIGHT - PRICE_TOP - PRICE_BOTTOM) * offset}
            y2={PRICE_TOP + (HEIGHT - PRICE_TOP - PRICE_BOTTOM) * offset}
            stroke={colors.line}
            strokeDasharray="4 7"
            strokeWidth="1"
          />
        ))}
        {points.map((point, index) => {
          const barHeight = (point.volume / chart.maxVolume) * VOLUME_HEIGHT;
          const x = (index / Math.max(points.length - 1, 1)) * WIDTH;
          return (
            <Rect
              fill={colors.surfaceStrong}
              height={barHeight}
              key={`${point.timestamp}-${index}`}
              width={volumeWidth}
              x={x}
              y={HEIGHT - barHeight - 2}
            />
          );
        })}
        <Path d={chart.area} fill="url(#stockChartFill)" />
        <Path
          d={chart.line}
          fill="none"
          stroke={lineColor}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2.4"
        />
      </Svg>
      <Text style={[styles.axisLabel, styles.axisTop]}>{money(chart.max)}</Text>
      <Text style={[styles.axisLabel, styles.axisBottom]}>{money(chart.min)}</Text>
      <View style={styles.dateRow}>
        <Text style={styles.dateText}>{formatAxisDate(points[0].timestamp)}</Text>
        <Text style={styles.volumeLabel}>VOLUME</Text>
        <Text style={styles.dateText}>{formatAxisDate(points.at(-1)!.timestamp)}</Text>
      </View>
    </View>
  );
}

function formatAxisDate(value: string) {
  const date = new Date(value);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

const styles = StyleSheet.create({
  root: { position: 'relative', paddingHorizontal: 4 },
  axisLabel: {
    position: 'absolute',
    right: 8,
    color: colors.inkMuted,
    fontSize: 9,
    backgroundColor: colors.surface,
    paddingLeft: 5,
  },
  axisTop: { top: 14 },
  axisBottom: { top: HEIGHT - PRICE_BOTTOM - 6 },
  dateRow: {
    marginTop: -2,
    paddingHorizontal: 4,
    paddingBottom: 4,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dateText: { color: colors.inkFaint, fontSize: 9 },
  volumeLabel: { color: colors.inkFaint, fontSize: 8, fontWeight: '800', letterSpacing: 0.8 },
  empty: { height: HEIGHT, alignItems: 'center', justifyContent: 'center' },
  emptyTitle: { color: colors.ink, fontSize: 14, fontWeight: '700' },
  emptyText: { color: colors.inkMuted, fontSize: 11, marginTop: 5 },
});
