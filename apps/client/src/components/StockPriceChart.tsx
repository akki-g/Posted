import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
  type PointerEvent,
} from 'react-native';
import Svg, {
  Circle,
  Defs,
  Line,
  LinearGradient,
  Path,
  Rect,
  Stop,
} from 'react-native-svg';

import { availableResolutions, pointIndexForX } from '@/lib/chartInteraction';
import { money } from '@/lib/format';
import type { PriceBar } from '@/lib/marketTypes';
import { colors, radius } from '@/theme/tokens';

const WIDTH = 900;
const HEIGHT = 292;
const PRICE_TOP = 20;
const PRICE_BOTTOM = 72;
const VOLUME_HEIGHT = 42;
const INDICATOR_WINDOW = 20;

type IndicatorKey = 'sma' | 'ema' | 'bollinger';
type ResolutionKey = 'source' | '5m' | '15m' | '1w';

type IndicatorSeries = {
  sma: (number | null)[];
  ema: (number | null)[];
  upper: (number | null)[];
  lower: (number | null)[];
};

type Props = {
  points: PriceBar[];
  sourceInterval: '1Min' | '1Day';
  onContextChange?: (context: string) => void;
};

const INDICATORS: {
  key: IndicatorKey;
  label: string;
  shortLabel: string;
  color: string;
  formula: string;
}[] = [
  {
    key: 'sma',
    label: 'Simple moving average',
    shortLabel: 'SMA 20',
    color: colors.blue,
    formula: 'SMA(20) = Σ Close ÷ 20',
  },
  {
    key: 'ema',
    label: 'Exponential moving average',
    shortLabel: 'EMA 20',
    color: colors.warning,
    formula: 'EMAₜ = αCloseₜ + (1−α)EMAₜ₋₁ · α = 2÷21',
  },
  {
    key: 'bollinger',
    label: 'Bollinger Bands',
    shortLabel: 'BB 20, 2',
    color: '#7357B8',
    formula: 'Bands = SMA(20) ± 2σ(20)',
  },
];

function aggregateBars(points: PriceBar[], groupSize: number): PriceBar[] {
  if (groupSize === 1) return points;
  const grouped: PriceBar[] = [];
  for (let index = 0; index < points.length; index += groupSize) {
    const group = points.slice(index, index + groupSize);
    if (!group.length) continue;
    grouped.push({
      timestamp: group.at(-1)!.timestamp,
      open: group[0].open,
      high: Math.max(...group.map((point) => point.high)),
      low: Math.min(...group.map((point) => point.low)),
      close: group.at(-1)!.close,
      volume: group.reduce((total, point) => total + point.volume, 0),
    });
  }
  return grouped;
}

function calculateIndicators(points: PriceBar[]): IndicatorSeries {
  const closes = points.map((point) => point.close);
  const sma: (number | null)[] = closes.map((_, index) => {
    if (index < INDICATOR_WINDOW - 1) return null;
    const window = closes.slice(index - INDICATOR_WINDOW + 1, index + 1);
    return window.reduce((total, value) => total + value, 0) / INDICATOR_WINDOW;
  });

  const multiplier = 2 / (INDICATOR_WINDOW + 1);
  const ema: (number | null)[] = closes.map(() => null);
  if (closes.length >= INDICATOR_WINDOW) {
    const seed = closes
      .slice(0, INDICATOR_WINDOW)
      .reduce((total, value) => total + value, 0) / INDICATOR_WINDOW;
    ema[INDICATOR_WINDOW - 1] = seed;
    for (let index = INDICATOR_WINDOW; index < closes.length; index += 1) {
      ema[index] = closes[index] * multiplier + ema[index - 1]! * (1 - multiplier);
    }
  }

  const upper: (number | null)[] = closes.map((_, index) => {
    if (index < INDICATOR_WINDOW - 1) return null;
    const window = closes.slice(index - INDICATOR_WINDOW + 1, index + 1);
    const average = sma[index]!;
    const variance =
      window.reduce((total, value) => total + (value - average) ** 2, 0) /
      INDICATOR_WINDOW;
    return average + 2 * Math.sqrt(variance);
  });
  const lower: (number | null)[] = closes.map((_, index) => {
    if (index < INDICATOR_WINDOW - 1) return null;
    const middle = sma[index]!;
    return middle - (upper[index]! - middle);
  });

  return { sma, ema, upper, lower };
}

function chartGeometry(
  points: PriceBar[],
  activeIndicators: IndicatorKey[],
  indicators: IndicatorSeries,
) {
  if (points.length < 2) {
    return { line: '', area: '', min: 0, max: 0, maxVolume: 0 };
  }

  const visibleIndicatorValues = [
    ...(activeIndicators.includes('sma') ? indicators.sma : []),
    ...(activeIndicators.includes('ema') ? indicators.ema : []),
    ...(activeIndicators.includes('bollinger')
      ? [...indicators.upper, ...indicators.lower]
      : []),
  ].filter((value): value is number => value != null);
  const values = [...points.map((item) => item.close), ...visibleIndicatorValues];
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const padding = Math.max((rawMax - rawMin) * 0.06, rawMax * 0.001);
  const min = rawMin - padding;
  const max = rawMax + padding;
  const range = max - min || 1;
  const mapped = points.map((point, index) => ({
    x: (index / (points.length - 1)) * WIDTH,
    y: priceToY(point.close, min, range),
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

function priceToY(value: number, min: number, range: number) {
  return PRICE_TOP + (1 - (value - min) / range) * (HEIGHT - PRICE_TOP - PRICE_BOTTOM);
}

function seriesPath(values: (number | null)[], min: number, max: number) {
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
) {
  const range = max - min || 1;
  const mappedUpper = upper
    .map((value, index) =>
      value == null
        ? null
        : {
            x: (index / Math.max(upper.length - 1, 1)) * WIDTH,
            y: priceToY(value, min, range),
          },
    )
    .filter((value): value is { x: number; y: number } => value != null);
  const mappedLower = lower
    .map((value, index) =>
      value == null
        ? null
        : {
            x: (index / Math.max(lower.length - 1, 1)) * WIDTH,
            y: priceToY(value, min, range),
          },
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

export function StockPriceChart({ points, sourceInterval, onContextChange }: Props) {
  const [resolution, setResolution] = useState<ResolutionKey>('source');
  const [activeIndicators, setActiveIndicators] = useState<IndicatorKey[]>(['sma']);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [chartWidth, setChartWidth] = useState(1);

  const options = useMemo(
    () => availableResolutions(sourceInterval, points.length),
    [sourceInterval, points.length],
  );
  const activeResolution = options.find((option) => option.key === resolution) ?? options[0];
  const displayPoints = useMemo(
    () => aggregateBars(points, activeResolution.groupSize),
    [activeResolution.groupSize, points],
  );
  const indicators = useMemo(() => calculateIndicators(displayPoints), [displayPoints]);
  const chart = useMemo(
    () => chartGeometry(displayPoints, activeIndicators, indicators),
    [activeIndicators, displayPoints, indicators],
  );
  const selectedIndex =
    activeIndex == null
      ? displayPoints.length - 1
      : Math.min(activeIndex, displayPoints.length - 1);
  const selectedPoint = displayPoints[selectedIndex];

  useEffect(() => {
    setResolution('source');
  }, [sourceInterval]);

  useEffect(() => {
    setActiveIndex(displayPoints.length ? displayPoints.length - 1 : null);
  }, [displayPoints.length]);

  const selectAt = useCallback(
    (x: number) => {
      if (!displayPoints.length) return;
      setActiveIndex(pointIndexForX(x, chartWidth, displayPoints.length));
    },
    [chartWidth, displayPoints.length],
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

  useEffect(() => {
    if (!onContextChange || !selectedPoint) return;
    const activeFormulaContext = INDICATORS.filter((item) =>
      activeIndicators.includes(item.key),
    )
      .map((item) => `${item.label}: ${item.formula}`)
      .join('; ');
    const selectedIndicatorContext = indicatorValuesAt(indicators, selectedIndex)
      .filter((item) => activeIndicators.includes(item.key))
      .map((item) => `${item.label} ${item.contextValue}`)
      .join(', ');
    onContextChange(
      [
        `The stock chart is displaying ${activeResolution.label} bars.`,
        `The inspected bar is ${formatTrackingDate(selectedPoint.timestamp)} with open ${money(selectedPoint.open)}, high ${money(selectedPoint.high)}, low ${money(selectedPoint.low)}, close ${money(selectedPoint.close)}, and volume ${formatVolume(selectedPoint.volume)}.`,
        activeFormulaContext
          ? `Active technical indicators and their formulas: ${activeFormulaContext}.`
          : 'No technical indicators are active.',
        selectedIndicatorContext
          ? `Indicator values at the inspected bar: ${selectedIndicatorContext}.`
          : '',
      ]
        .filter(Boolean)
        .join(' '),
    );
  }, [
    activeIndicators,
    activeResolution.label,
    indicators,
    onContextChange,
    selectedIndex,
    selectedPoint,
  ]);

  if (displayPoints.length < 2) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>Price history unavailable</Text>
        <Text style={styles.emptyText}>Try another range or configure a market-data provider.</Text>
      </View>
    );
  }

  const change = displayPoints.at(-1)!.close - displayPoints[0].close;
  const lineColor = change >= 0 ? colors.teal : colors.negative;
  const volumeWidth = Math.max(0.8, WIDTH / displayPoints.length - 0.6);
  const crosshairX = (selectedIndex / Math.max(displayPoints.length - 1, 1)) * WIDTH;
  const crosshairY = priceToY(selectedPoint.close, chart.min, chart.max - chart.min || 1);
  const valuesAtSelection = indicatorValuesAt(indicators, selectedIndex);
  const bandArea = bandAreaPath(indicators.upper, indicators.lower, chart.min, chart.max);

  const toggleIndicator = (indicator: IndicatorKey) => {
    setActiveIndicators((current) =>
      current.includes(indicator)
        ? current.filter((item) => item !== indicator)
        : [...current, indicator],
    );
  };

  const onChartLayout = (event: LayoutChangeEvent) => {
    setChartWidth(Math.max(event.nativeEvent.layout.width, 1));
  };

  const onPointerMove = (event: PointerEvent) => {
    selectAt(event.nativeEvent.offsetX);
  };

  return (
    <View style={styles.root}>
      <View style={styles.toolbar}>
        <View style={styles.controlGroup}>
          <Text style={styles.controlLabel}>INDICATORS</Text>
          <View style={styles.controlOptions}>
            {INDICATORS.map((indicator) => {
              const active = activeIndicators.includes(indicator.key);
              return (
                <Pressable
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                  key={indicator.key}
                  onPress={() => toggleIndicator(indicator.key)}
                  style={[styles.controlButton, active && styles.controlButtonActive]}>
                  <View
                    style={[
                      styles.indicatorSwatch,
                      { backgroundColor: active ? indicator.color : colors.lineStrong },
                    ]}
                  />
                  <Text style={[styles.controlText, active && styles.controlTextActive]}>
                    {indicator.shortLabel}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
        <View style={[styles.controlGroup, styles.intervalGroup]}>
          <Text style={styles.controlLabel}>BAR INTERVAL</Text>
          <View style={styles.controlOptions}>
            {options.map((option) => (
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ selected: activeResolution.key === option.key }}
                key={option.key}
                onPress={() => setResolution(option.key)}
                style={[
                  styles.intervalButton,
                  activeResolution.key === option.key && styles.intervalButtonActive,
                ]}>
                <Text
                  style={[
                    styles.intervalText,
                    activeResolution.key === option.key && styles.intervalTextActive,
                  ]}>
                  {option.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      </View>

      <View style={styles.inspectionRow}>
        <View style={styles.inspectionPrimary}>
          <View>
            <Text style={styles.inspectionTime}>
              {formatTrackingDate(selectedPoint.timestamp)}
            </Text>
            <Text style={styles.inspectionHint}>MOVE OR DRAG ACROSS THE CHART</Text>
          </View>
          <View>
            <Text style={styles.closeLabel}>CLOSE</Text>
            <Text style={styles.closeValue}>{money(selectedPoint.close)}</Text>
          </View>
        </View>
        <View style={styles.ohlcRow}>
          <Readout label="OPEN" value={money(selectedPoint.open)} />
          <Readout label="HIGH" value={money(selectedPoint.high)} />
          <Readout label="LOW" value={money(selectedPoint.low)} />
          <Readout label="VOLUME" value={formatVolume(selectedPoint.volume)} />
          {valuesAtSelection
            .filter((item) => activeIndicators.includes(item.key))
            .map((item) => (
              <Readout
                color={item.color}
                key={item.key}
                label={item.shortLabel}
                value={item.displayValue}
              />
            ))}
        </View>
      </View>

      <View style={styles.chartArea} onLayout={onChartLayout}>
        <Svg
          width="100%"
          height={HEIGHT}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none">
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
            const barHeight = (point.volume / chart.maxVolume) * VOLUME_HEIGHT;
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
          <Path d={chart.area} fill="url(#stockChartFill)" />
          {activeIndicators.includes('bollinger') && bandArea ? (
            <>
              <Path d={bandArea} fill="#7357B8" opacity={0.08} />
              <Path
                d={seriesPath(indicators.upper, chart.min, chart.max)}
                fill="none"
                stroke="#7357B8"
                strokeDasharray="6 5"
                strokeWidth="1.4"
              />
              <Path
                d={seriesPath(indicators.lower, chart.min, chart.max)}
                fill="none"
                stroke="#7357B8"
                strokeDasharray="6 5"
                strokeWidth="1.4"
              />
            </>
          ) : null}
          {activeIndicators.includes('sma') ? (
            <Path
              d={seriesPath(indicators.sma, chart.min, chart.max)}
              fill="none"
              stroke={colors.blue}
              strokeWidth="1.7"
            />
          ) : null}
          {activeIndicators.includes('ema') ? (
            <Path
              d={seriesPath(indicators.ema, chart.min, chart.max)}
              fill="none"
              stroke={colors.warning}
              strokeWidth="1.7"
            />
          ) : null}
          <Path
            d={chart.line}
            fill="none"
            stroke={lineColor}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2.4"
          />
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
          <Circle
            cx={crosshairX}
            cy={crosshairY}
            fill={colors.surface}
            r="5"
            stroke={lineColor}
            strokeWidth="2.5"
          />
        </Svg>
        <Text style={[styles.axisLabel, styles.axisTop]}>{money(chart.max)}</Text>
        <Text style={[styles.axisLabel, styles.axisBottom]}>{money(chart.min)}</Text>
        <View
          {...panResponder.panHandlers}
          accessible
          accessibilityLabel={`Interactive price chart. Selected ${formatTrackingDate(selectedPoint.timestamp)}, close ${money(selectedPoint.close)}`}
          accessibilityRole="adjustable"
          accessibilityValue={{ min: 0, max: displayPoints.length - 1, now: selectedIndex }}
          onAccessibilityAction={(event) => {
            const delta = event.nativeEvent.actionName === 'increment' ? 1 : -1;
            setActiveIndex((current) =>
              Math.max(0, Math.min((current ?? displayPoints.length - 1) + delta, displayPoints.length - 1)),
            );
          }}
          accessibilityActions={[
            { name: 'increment', label: 'Next price bar' },
            { name: 'decrement', label: 'Previous price bar' },
          ]}
          onPointerDown={onPointerMove}
          onPointerMove={onPointerMove}
          style={styles.trackingLayer}
        />
      </View>

      <View style={styles.dateRow}>
        <Text style={styles.dateText}>{formatAxisDate(displayPoints[0].timestamp)}</Text>
        <Text style={styles.volumeLabel}>VOLUME</Text>
        <Text style={styles.dateText}>{formatAxisDate(displayPoints.at(-1)!.timestamp)}</Text>
      </View>

      {activeIndicators.length ? (
        <View style={styles.formulaRail}>
          <View style={styles.formulaHeading}>
            <Text style={styles.formulaEyebrow}>ACTIVE FORMULAS</Text>
            <Text style={styles.formulaCaption}>
              Calculated from the selected {activeResolution.label} bars
            </Text>
          </View>
          <View style={styles.formulaCards}>
            {INDICATORS.filter((item) => activeIndicators.includes(item.key)).map((item) => {
              const value = valuesAtSelection.find((candidate) => candidate.key === item.key);
              return (
                <View style={styles.formulaCard} key={item.key}>
                  <View style={[styles.formulaAccent, { backgroundColor: item.color }]} />
                  <View style={styles.formulaCopy}>
                    <Text style={styles.formulaName}>{item.label}</Text>
                    <Text style={styles.formulaText}>{item.formula}</Text>
                  </View>
                  <Text style={[styles.formulaValue, { color: item.color }]}>
                    {value?.displayValue ?? '—'}
                  </Text>
                </View>
              );
            })}
          </View>
        </View>
      ) : null}
    </View>
  );
}

function indicatorValuesAt(indicators: IndicatorSeries, index: number) {
  return [
    {
      key: 'sma' as const,
      label: 'SMA(20)',
      shortLabel: 'SMA',
      color: colors.blue,
      displayValue:
        indicators.sma[index] == null ? 'Needs 20 bars' : money(indicators.sma[index]!),
      contextValue:
        indicators.sma[index] == null ? 'unavailable' : money(indicators.sma[index]!),
    },
    {
      key: 'ema' as const,
      label: 'EMA(20)',
      shortLabel: 'EMA',
      color: colors.warning,
      displayValue:
        indicators.ema[index] == null ? 'Needs 20 bars' : money(indicators.ema[index]!),
      contextValue:
        indicators.ema[index] == null ? 'unavailable' : money(indicators.ema[index]!),
    },
    {
      key: 'bollinger' as const,
      label: 'Bollinger Bands',
      shortLabel: 'BB RANGE',
      color: '#7357B8',
      displayValue:
        indicators.lower[index] == null || indicators.upper[index] == null
          ? 'Needs 20 bars'
          : `${money(indicators.lower[index]!)}–${money(indicators.upper[index]!)}`,
      contextValue:
        indicators.lower[index] == null || indicators.upper[index] == null
          ? 'unavailable'
          : `midpoint ${money(indicators.sma[index]!)}, lower band ${money(indicators.lower[index]!)}, upper band ${money(indicators.upper[index]!)}`,
    },
  ];
}

function Readout({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <View style={styles.readout}>
      <Text style={[styles.readoutLabel, color ? { color } : null]}>{label}</Text>
      <Text style={styles.readoutValue}>{value}</Text>
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

function formatTrackingDate(value: string) {
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatVolume(value: number) {
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

const styles = StyleSheet.create({
  root: { position: 'relative' },
  toolbar: {
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    flexWrap: 'wrap',
    gap: 12,
  },
  controlGroup: { gap: 6 },
  intervalGroup: { alignItems: 'flex-end' },
  controlLabel: { color: colors.inkFaint, fontSize: 8, fontWeight: '900', letterSpacing: 1 },
  controlOptions: { flexDirection: 'row', flexWrap: 'wrap', gap: 5 },
  controlButton: {
    minHeight: 30,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    paddingHorizontal: 9,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  controlButtonActive: { borderColor: colors.lineStrong, backgroundColor: colors.canvas },
  indicatorSwatch: { width: 7, height: 7, borderRadius: 4 },
  controlText: { color: colors.inkMuted, fontSize: 9, fontWeight: '700' },
  controlTextActive: { color: colors.ink },
  intervalButton: {
    height: 30,
    minWidth: 34,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  intervalButtonActive: { borderColor: colors.teal, backgroundColor: colors.tealSoft },
  intervalText: { color: colors.inkMuted, fontSize: 9, fontWeight: '800' },
  intervalTextActive: { color: colors.tealDark },
  inspectionRow: {
    minHeight: 74,
    paddingVertical: 11,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 12,
  },
  inspectionPrimary: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 20 },
  inspectionTime: {
    color: colors.ink,
    fontSize: 11,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  inspectionHint: {
    color: colors.inkFaint,
    fontSize: 7,
    fontWeight: '800',
    letterSpacing: 0.7,
    marginTop: 4,
  },
  closeLabel: { color: colors.inkFaint, fontSize: 7, fontWeight: '900', letterSpacing: 0.8 },
  closeValue: {
    color: colors.ink,
    fontSize: 18,
    fontWeight: '700',
    marginTop: 2,
    fontVariant: ['tabular-nums'],
  },
  ohlcRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 14 },
  readout: { minWidth: 42 },
  readoutLabel: { color: colors.inkFaint, fontSize: 7, fontWeight: '900', letterSpacing: 0.7 },
  readoutValue: {
    color: colors.ink,
    fontSize: 10,
    fontWeight: '700',
    marginTop: 4,
    fontVariant: ['tabular-nums'],
  },
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
  dateRow: {
    marginTop: -2,
    paddingHorizontal: 4,
    paddingBottom: 9,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dateText: { color: colors.inkFaint, fontSize: 9 },
  volumeLabel: { color: colors.inkFaint, fontSize: 8, fontWeight: '800', letterSpacing: 0.8 },
  formulaRail: {
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: 11,
    gap: 9,
  },
  formulaHeading: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 5,
  },
  formulaEyebrow: { color: colors.inkFaint, fontSize: 8, fontWeight: '900', letterSpacing: 1 },
  formulaCaption: { color: colors.inkFaint, fontSize: 8 },
  formulaCards: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  formulaCard: {
    minWidth: 210,
    flex: 1,
    minHeight: 54,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    backgroundColor: colors.canvas,
    padding: 9,
    paddingLeft: 13,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    position: 'relative',
  },
  formulaAccent: { position: 'absolute', top: 0, bottom: 0, left: 0, width: 3 },
  formulaCopy: { flex: 1, minWidth: 0 },
  formulaName: { color: colors.ink, fontSize: 9, fontWeight: '800' },
  formulaText: { color: colors.inkMuted, fontSize: 8, marginTop: 4 },
  formulaValue: { fontSize: 10, fontWeight: '800', fontVariant: ['tabular-nums'] },
  empty: { height: HEIGHT, alignItems: 'center', justifyContent: 'center' },
  emptyTitle: { color: colors.ink, fontSize: 14, fontWeight: '700' },
  emptyText: { color: colors.inkMuted, fontSize: 11, marginTop: 5 },
});
