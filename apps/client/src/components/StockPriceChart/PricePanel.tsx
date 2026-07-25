import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Polygon, Rect, Stop } from 'react-native-svg';

import type { ChartScrub } from '@/lib/chartScrub';
import { money } from '@/lib/format';
import type { SignalDirection, SignalEvent } from '@/lib/indicators/signals';
import type { IndicatorInstance, IndicatorSeries } from '@/lib/indicators/types';
import type { PriceBar } from '@/lib/marketTypes';
import { colors } from '@/theme/tokens';

import { formatTrackingDate } from './formatting';

export const WIDTH = 900;
export const HEIGHT = 292;
export const PRICE_TOP = 20;
export const PRICE_BOTTOM = 72;
export const VOLUME_HEIGHT = 42;

export function priceToY(value: number, min: number, range: number): number {
  return PRICE_TOP + (1 - (value - min) / range) * (HEIGHT - PRICE_TOP - PRICE_BOTTOM);
}

function seriesPath(values: (number | null)[], min: number, max: number): string {
  const range = max - min || 1;
  let drawing = false;
  return values
    .map((value, index) => {
      if (value == null) {
        drawing = false;
        return '';
      }
      const x = (index / Math.max(values.length - 1, 1)) * WIDTH;
      const y = priceToY(value, min, range);
      const command = drawing ? 'L' : 'M';
      drawing = true;
      return `${command} ${x} ${y}`;
    })
    .filter(Boolean)
    .join(' ');
}

function bandAreaPath(
  upper: (number | null)[],
  lower: (number | null)[],
  min: number,
  max: number,
): string {
  const range = max - min || 1;
  const mappedUpper = upper
    .map((value, index) =>
      value == null
        ? null
        : { x: (index / Math.max(upper.length - 1, 1)) * WIDTH, y: priceToY(value, min, range) },
    )
    .filter((value): value is { x: number; y: number } => value != null);
  const mappedLower = lower
    .map((value, index) =>
      value == null
        ? null
        : { x: (index / Math.max(lower.length - 1, 1)) * WIDTH, y: priceToY(value, min, range) },
    )
    .filter((value): value is { x: number; y: number } => value != null)
    .reverse();
  if (!mappedUpper.length || !mappedLower.length) return '';
  return [
    ...mappedUpper.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`),
    ...mappedLower.map((point) => `L ${point.x} ${point.y}`),
    'Z',
  ].join(' ');
}

type OverlayEntry = { instance: IndicatorInstance; series: IndicatorSeries };

type Props = {
  displayPoints: PriceBar[];
  overlays: OverlayEntry[];
  signals: SignalEvent[];
  activeSignalRules: Set<string>;
  activeSignalDirections: Set<SignalDirection>;
  chartMin: number;
  chartMax: number;
  chartLine: string;
  chartArea: string;
  maxVolume: number;
  lineColor: string;
  includeTime: boolean;
  scrub: ChartScrub;
};

export function PricePanel({
  displayPoints,
  overlays,
  signals,
  activeSignalRules,
  activeSignalDirections,
  chartMin,
  chartMax,
  chartLine,
  chartArea,
  maxVolume,
  lineColor,
  includeTime,
  scrub,
}: Props) {
  const selectedIndex = scrub.selectedIndex;
  const selectedPoint = displayPoints[selectedIndex];
  const volumeWidth = Math.max(0.8, WIDTH / displayPoints.length - 0.6);
  const crosshairX = (selectedIndex / Math.max(displayPoints.length - 1, 1)) * WIDTH;
  const crosshairY = priceToY(selectedPoint.close, chartMin, chartMax - chartMin || 1);
  const visibleSignals = signals.filter(
    (signal) =>
      activeSignalRules.has(signal.rule) &&
      activeSignalDirections.has(signal.direction) &&
      signal.index < displayPoints.length,
  );

  return (
    <View style={styles.chartArea} onLayout={scrub.onLayout}>
      <Svg width="100%" height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none">
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
        {displayPoints.map((point, index) => {
          const barHeight = (point.volume / maxVolume) * VOLUME_HEIGHT;
          const x = (index / Math.max(displayPoints.length - 1, 1)) * WIDTH;
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
        <Path d={chartArea} fill="url(#stockChartFill)" />
        {overlays.map(({ instance, series }) => (
          <OverlayLines key={instance.id} instance={instance} series={series} min={chartMin} max={chartMax} />
        ))}
        <Path
          d={chartLine}
          fill="none"
          stroke={lineColor}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2.4"
        />
        {visibleSignals.map((signal, index) => (
          <SignalMarker
            key={`${signal.index}-${signal.rule}-${index}`}
            signal={signal}
            point={displayPoints[signal.index]}
            allPoints={displayPoints}
            min={chartMin}
            max={chartMax}
          />
        ))}
        <Line
          x1={crosshairX}
          x2={crosshairX}
          y1={PRICE_TOP}
          y2={HEIGHT - 2}
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
          strokeOpacity="0.52"
          strokeWidth="1"
        />
        <Circle cx={crosshairX} cy={crosshairY} fill={colors.surface} r="5" stroke={lineColor} strokeWidth="2.5" />
      </Svg>
      <Text style={[styles.axisLabel, styles.axisTop]}>{money(chartMax)}</Text>
      <Text style={[styles.axisLabel, styles.axisBottom]}>{money(chartMin)}</Text>
      <View
        {...scrub.panHandlers}
        accessible
        accessibilityLabel={`Interactive price chart. Selected ${formatTrackingDate(selectedPoint.timestamp, includeTime)}, close ${money(selectedPoint.close)}`}
        accessibilityRole="adjustable"
        accessibilityValue={scrub.accessibilityValue}
        onAccessibilityAction={scrub.onAccessibilityAction}
        accessibilityActions={[
          { name: 'increment', label: 'Next price bar' },
          { name: 'decrement', label: 'Previous price bar' },
        ]}
        onPointerDown={scrub.onPointerDown}
        onPointerMove={scrub.onPointerMove}
        style={styles.trackingLayer}
      />
    </View>
  );
}

function OverlayLines({
  instance,
  series,
  min,
  max,
}: {
  instance: IndicatorInstance;
  series: IndicatorSeries;
  min: number;
  max: number;
}) {
  if (instance.type === 'bollinger') {
    const bandArea = bandAreaPath(series.upper, series.lower, min, max);
    return (
      <>
        {bandArea ? <Path d={bandArea} fill={instance.color} opacity={0.08} /> : null}
        <Path d={seriesPath(series.upper, min, max)} fill="none" stroke={instance.color} strokeDasharray="6 5" strokeWidth="1.4" />
        <Path d={seriesPath(series.lower, min, max)} fill="none" stroke={instance.color} strokeDasharray="6 5" strokeWidth="1.4" />
      </>
    );
  }
  return <Path d={seriesPath(series.main, min, max)} fill="none" stroke={instance.color} strokeWidth="1.7" />;
}

function SignalMarker({
  signal,
  point,
  allPoints,
  min,
  max,
}: {
  signal: SignalEvent;
  point: PriceBar;
  allPoints: PriceBar[];
  min: number;
  max: number;
}) {
  const range = max - min || 1;
  const x = (signal.index / Math.max(allPoints.length - 1, 1)) * WIDTH;
  const y = priceToY(point.close, min, range);
  const size = 7;
  const offset = signal.direction === 'bullish' ? 12 : -12;
  const markerY = y + offset;
  const color = signal.direction === 'bullish' ? colors.positive : colors.negative;
  const points =
    signal.direction === 'bullish'
      ? `${x},${markerY - size} ${x - size},${markerY + size} ${x + size},${markerY + size}`
      : `${x},${markerY + size} ${x - size},${markerY - size} ${x + size},${markerY - size}`;
  return <Polygon points={points} fill={color} />;
}

const styles = StyleSheet.create({
  chartArea: { height: HEIGHT, position: 'relative', overflow: 'hidden' },
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
    color: colors.inkMuted,
    fontSize: 9,
    backgroundColor: colors.surface,
    paddingLeft: 5,
  },
  axisTop: { top: 14 },
  axisBottom: { top: HEIGHT - PRICE_BOTTOM - 6 },
});
