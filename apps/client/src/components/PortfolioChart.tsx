import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  PanResponder,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
  type PointerEvent,
} from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';

import { pointIndexForX } from '@/lib/chartInteraction';
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
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const padding = Math.max((rawMax - rawMin) * 0.06, rawMax * 0.001);
  const min = rawMin - padding;
  const max = rawMax + padding;
  const range = max - min || 1;
  const mapped = values.map((value, index) => ({
    x: (index / (values.length - 1)) * WIDTH,
    y: valueToY(value, min, range),
  }));
  const line = mapped.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  const area = `${line} L ${WIDTH} ${HEIGHT - BOTTOM} L 0 ${HEIGHT - BOTTOM} Z`;
  return { line, area, min, max };
}

function valueToY(value: number, min: number, range: number) {
  return TOP + (1 - (value - min) / range) * (HEIGHT - TOP - BOTTOM);
}

type Props = {
  points: ChartPoint[];
  onSelectionChange?: (point: ChartPoint | null) => void;
};

export function PortfolioChart({ points, onSelectionChange }: Props) {
  const chart = useMemo(() => buildPath(points), [points]);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [chartWidth, setChartWidth] = useState(1);
  const selectedIndex =
    activeIndex == null ? Math.max(points.length - 1, 0) : Math.min(activeIndex, points.length - 1);
  const selectedPoint = points[selectedIndex];

  useEffect(() => {
    setActiveIndex(points.length ? points.length - 1 : null);
  }, [points.length]);

  useEffect(() => {
    onSelectionChange?.(selectedPoint ?? null);
  }, [onSelectionChange, selectedPoint]);

  const selectAt = useCallback(
    (x: number) => {
      if (!points.length) return;
      setActiveIndex(pointIndexForX(x, chartWidth, points.length));
    },
    [chartWidth, points.length],
  );

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: (_, gesture) =>
          Math.abs(gesture.dx) > Math.abs(gesture.dy),
        onShouldBlockNativeResponder: () => false,
        onPanResponderGrant: (event) => selectAt(event.nativeEvent.locationX),
        onPanResponderMove: (event) => selectAt(event.nativeEvent.locationX),
      }),
    [selectAt],
  );

  if (points.length < 2 || !selectedPoint) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>Portfolio history unavailable</Text>
        <Text style={styles.emptyText}>Sync your portfolio to begin tracking its movement.</Text>
      </View>
    );
  }

  const change = Number(points.at(-1)?.value) - Number(points[0].value);
  const selectedValue = Number(selectedPoint.value);
  const selectedChange = selectedValue - Number(points[0].value);
  const crosshairX = (selectedIndex / Math.max(points.length - 1, 1)) * WIDTH;
  const crosshairY = valueToY(selectedValue, chart.min, chart.max - chart.min || 1);

  const onChartLayout = (event: LayoutChangeEvent) => {
    setChartWidth(Math.max(event.nativeEvent.layout.width, 1));
  };

  const onPointerMove = (event: PointerEvent) => {
    selectAt(event.nativeEvent.offsetX);
  };

  return (
    <View style={styles.root}>
      <View style={styles.legendRow}>
        <View>
          <Text style={styles.legendLabel}>30-DAY CHANGE</Text>
          <Text style={[styles.change, { color: change >= 0 ? colors.positive : colors.negative }]}>
            {change >= 0 ? '+' : ''}{money(change)}
          </Text>
        </View>
        <View style={styles.trackingReadout}>
          <View style={styles.trackingCopy}>
            <Text style={styles.trackingDate}>{formatTrackingDate(selectedPoint.timestamp)}</Text>
            <Text style={styles.trackingHint}>MOVE OR DRAG TO INSPECT</Text>
          </View>
          <View style={styles.trackingValueBlock}>
            <Text style={styles.trackingLabel}>PORTFOLIO VALUE</Text>
            <Text style={styles.trackingValue}>{money(selectedValue)}</Text>
            <Text
              style={[
                styles.trackingDelta,
                { color: selectedChange >= 0 ? colors.positive : colors.negative },
              ]}>
              {selectedChange >= 0 ? '+' : ''}{money(selectedChange)} in range
            </Text>
          </View>
          <View style={styles.rangeBadge}>
            <Text style={styles.rangeText}>1M</Text>
          </View>
        </View>
      </View>
      <View style={styles.chartWrap} onLayout={onChartLayout}>
        <Svg
          width="100%"
          height={HEIGHT}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none">
          <Defs>
            <LinearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={colors.teal} stopOpacity="0.24" />
              <Stop offset="1" stopColor={colors.teal} stopOpacity="0.01" />
            </LinearGradient>
          </Defs>
          {[0.25, 0.5, 0.75].map((offset) => (
            <Line
              key={offset}
              x1="0"
              x2={WIDTH}
              y1={TOP + (HEIGHT - TOP - BOTTOM) * offset}
              y2={TOP + (HEIGHT - TOP - BOTTOM) * offset}
              stroke={colors.line}
              strokeDasharray="4 7"
              strokeWidth="1"
            />
          ))}
          <Path d={chart.area} fill="url(#chartFill)" />
          <Path
            d={chart.line}
            fill="none"
            stroke={colors.teal}
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          <Line
            x1={crosshairX}
            x2={crosshairX}
            y1={TOP}
            y2={HEIGHT - BOTTOM}
            stroke={colors.inkMuted}
            strokeDasharray="3 4"
            strokeWidth="1"
          />
          <Line
            x1="0"
            x2={WIDTH}
            y1={crosshairY}
            y2={crosshairY}
            stroke={colors.inkMuted}
            strokeDasharray="3 4"
            strokeOpacity="0.5"
            strokeWidth="1"
          />
          <Circle
            cx={crosshairX}
            cy={crosshairY}
            fill={colors.surface}
            r="5"
            stroke={colors.teal}
            strokeWidth="2.5"
          />
        </Svg>
        <Text style={[styles.axisLabel, styles.axisTop]}>{money(chart.max, true)}</Text>
        <Text style={[styles.axisLabel, styles.axisBottom]}>{money(chart.min, true)}</Text>
        <View
          {...panResponder.panHandlers}
          accessible
          accessibilityLabel={`Interactive portfolio chart. Selected ${formatTrackingDate(selectedPoint.timestamp)}, value ${money(selectedValue)}`}
          accessibilityRole="adjustable"
          accessibilityValue={{ min: 0, max: points.length - 1, now: selectedIndex }}
          onAccessibilityAction={(event) => {
            const delta = event.nativeEvent.actionName === 'increment' ? 1 : -1;
            setActiveIndex((current) =>
              Math.max(0, Math.min((current ?? points.length - 1) + delta, points.length - 1)),
            );
          }}
          accessibilityActions={[
            { name: 'increment', label: 'Next portfolio value' },
            { name: 'decrement', label: 'Previous portfolio value' },
          ]}
          onPointerDown={onPointerMove}
          onPointerMove={onPointerMove}
          style={styles.trackingLayer}
        />
      </View>
      <View style={styles.dateRow}>
        <Text style={styles.dateText}>{formatShortDate(points[0].timestamp)}</Text>
        <Text style={styles.dateText}>{formatShortDate(points.at(-1)!.timestamp)}</Text>
      </View>
    </View>
  );
}

function formatTrackingDate(value: string) {
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatShortDate(value: string) {
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const styles = StyleSheet.create({
  root: { flex: 1, paddingTop: 16 },
  legendRow: {
    minHeight: 68,
    paddingHorizontal: 18,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: 12,
  },
  legendLabel: { color: colors.inkFaint, fontSize: 9, fontWeight: '700', letterSpacing: 1.2 },
  change: { fontSize: 14, fontWeight: '700', marginTop: 5, fontVariant: ['tabular-nums'] },
  trackingReadout: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    flexWrap: 'wrap',
    gap: 13,
  },
  trackingCopy: { alignItems: 'flex-end' },
  trackingDate: { color: colors.ink, fontSize: 10, fontWeight: '700' },
  trackingHint: { color: colors.inkFaint, fontSize: 7, fontWeight: '800', letterSpacing: 0.7, marginTop: 3 },
  trackingValueBlock: { borderLeftWidth: 1, borderLeftColor: colors.line, paddingLeft: 12 },
  trackingLabel: { color: colors.inkFaint, fontSize: 7, fontWeight: '900', letterSpacing: 0.7 },
  trackingValue: { color: colors.ink, fontSize: 15, fontWeight: '800', marginTop: 2, fontVariant: ['tabular-nums'] },
  trackingDelta: { fontSize: 8, fontWeight: '700', marginTop: 2, fontVariant: ['tabular-nums'] },
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
  chartWrap: { height: HEIGHT, position: 'relative', overflow: 'hidden' },
  trackingLayer: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    cursor: 'crosshair',
  } as never,
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
  empty: { minHeight: 240, alignItems: 'center', justifyContent: 'center' },
  emptyTitle: { color: colors.ink, fontSize: 14, fontWeight: '700' },
  emptyText: { color: colors.inkMuted, fontSize: 11, marginTop: 5 },
});
