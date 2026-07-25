import { Maximize2, ZoomIn, ZoomOut } from 'lucide-react-native';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { availableResolutions } from '@/lib/chartInteraction';
import { useChartScrub } from '@/lib/chartScrub';
import { useChartZoom } from '@/lib/chartZoom';
import { money, number } from '@/lib/format';
import { INDICATOR_DEFS, nextIndicatorColor } from '@/lib/indicators/registry';
import {
  macdSignalCrossSignals,
  overlayPairCrossoverSignals,
  rsiZoneExitSignals,
  stochasticCrossSignals,
  type SignalDirection,
  type SignalEvent,
} from '@/lib/indicators/signals';
import type {
  IndicatorInstance,
  IndicatorParams,
  IndicatorSeries,
  IndicatorType,
} from '@/lib/indicators/types';
import type { PriceBar } from '@/lib/marketTypes';
import { colors, radius } from '@/theme/tokens';

import { formatAxisDate, formatTrackingDate, formatVolume } from './formatting';
import { IndicatorToolbar } from './IndicatorToolbar';
import { OscillatorPanel } from './OscillatorPanel';
import { PricePanel, priceToY } from './PricePanel';
import { RangeBrush } from './RangeBrush';

const WIDTH = 900;
const HEIGHT = 292;
const PRICE_TOP = 20;
const PRICE_BOTTOM = 72;

type ResolutionKey = 'source' | '5m' | '15m' | '1w';

type Props = {
  points: PriceBar[];
  sourceInterval: '1Min' | '1Day';
  onContextChange?: (context: string) => void;
};

function createInstanceId(type: IndicatorType): string {
  return `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

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

function sliceSeries(series: IndicatorSeries, start: number, end: number): IndicatorSeries {
  const sliced: IndicatorSeries = {};
  for (const [key, values] of Object.entries(series)) {
    sliced[key] = values.slice(start, end + 1);
  }
  return sliced;
}

function chartGeometry(displayPoints: PriceBar[], overlaySeries: IndicatorSeries[]) {
  if (displayPoints.length < 2) {
    return { line: '', area: '', min: 0, max: 0, maxVolume: 0 };
  }
  const overlayValues = overlaySeries
    .flatMap((series) => Object.values(series))
    .flat()
    .filter((value): value is number => value != null);
  const values = [...displayPoints.map((point) => point.close), ...overlayValues];
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const padding = Math.max((rawMax - rawMin) * 0.06, rawMax * 0.001);
  const min = rawMin - padding;
  const max = rawMax + padding;
  const range = max - min || 1;
  const mapped = displayPoints.map((point, index) => ({
    x: (index / (displayPoints.length - 1)) * WIDTH,
    y: priceToY(point.close, min, range),
  }));
  const line = mapped.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  const baseline = HEIGHT - PRICE_BOTTOM;
  return {
    line,
    area: `${line} L ${WIDTH} ${baseline} L 0 ${baseline} Z`,
    min,
    max,
    maxVolume: Math.max(...displayPoints.map((point) => point.volume), 1),
  };
}

function primaryValueAt(instance: IndicatorInstance, series: IndicatorSeries, index: number): string {
  switch (instance.type) {
    case 'bollinger': {
      const lower = series.lower[index];
      const upper = series.upper[index];
      return lower == null || upper == null ? 'Needs more bars' : `${money(lower)}–${money(upper)}`;
    }
    case 'rsi': {
      const value = series.main[index];
      return value == null ? 'Needs more bars' : number(value, 1);
    }
    case 'stochastic': {
      const value = series.k[index];
      return value == null ? 'Needs more bars' : number(value, 1);
    }
    case 'macd': {
      const value = series.line[index];
      return value == null ? 'Needs more bars' : money(value);
    }
    default: {
      const value = series.main[index];
      return value == null ? 'Needs more bars' : money(value);
    }
  }
}

export function StockPriceChart({ points, sourceInterval, onContextChange }: Props) {
  const [resolution, setResolution] = useState<ResolutionKey>('source');
  const [instances, setInstances] = useState<IndicatorInstance[]>(() => [
    {
      id: createInstanceId('sma'),
      type: 'sma',
      params: { ...INDICATOR_DEFS.sma.defaultParams },
      color: nextIndicatorColor([]),
    },
  ]);
  const [openSettings, setOpenSettings] = useState<{
    id: string;
    anchor: 'toolbar' | 'panel';
  } | null>(null);
  const [mutedSignalRules, setMutedSignalRules] = useState<Set<string>>(new Set());
  const [mutedSignalDirections, setMutedSignalDirections] = useState<Set<SignalDirection>>(new Set());

  const options = useMemo(
    () => availableResolutions(sourceInterval, points.length),
    [sourceInterval, points.length],
  );
  const activeResolution = options.find((option) => option.key === resolution) ?? options[0];
  const displayPoints = useMemo(
    () => aggregateBars(points, activeResolution.groupSize),
    [activeResolution.groupSize, points],
  );

  useEffect(() => {
    setResolution('source');
  }, [sourceInterval]);

  const zoom = useChartZoom(displayPoints.length, activeResolution.key);
  const visiblePoints = useMemo(
    () => displayPoints.slice(zoom.start, zoom.end + 1),
    [displayPoints, zoom.start, zoom.end],
  );

  const seriesByInstance = useMemo(() => {
    const map = new Map<string, IndicatorSeries>();
    for (const instance of instances) {
      map.set(instance.id, INDICATOR_DEFS[instance.type].calculate(displayPoints, instance.params));
    }
    return map;
  }, [displayPoints, instances]);

  const overlayInstances = useMemo(
    () =>
      instances
        .filter((instance) => INDICATOR_DEFS[instance.type].kind === 'overlay')
        .map((instance) => ({ instance, series: seriesByInstance.get(instance.id)! })),
    [instances, seriesByInstance],
  );
  const oscillatorInstances = useMemo(
    () => instances.filter((instance) => INDICATOR_DEFS[instance.type].kind === 'oscillator'),
    [instances],
  );

  const visibleOverlayInstances = useMemo(
    () =>
      overlayInstances.map((entry) => ({
        instance: entry.instance,
        series: sliceSeries(entry.series, zoom.start, zoom.end),
      })),
    [overlayInstances, zoom.start, zoom.end],
  );

  const chart = useMemo(
    () => chartGeometry(visiblePoints, visibleOverlayInstances.map((entry) => entry.series)),
    [visiblePoints, visibleOverlayInstances],
  );

  const signals = useMemo(() => {
    const events: SignalEvent[] = [];
    const mainSeriesOverlays = overlayInstances.filter((entry) => entry.series.main);
    for (let i = 0; i < mainSeriesOverlays.length; i += 1) {
      for (let j = i + 1; j < mainSeriesOverlays.length; j += 1) {
        const a = mainSeriesOverlays[i];
        const b = mainSeriesOverlays[j];
        events.push(
          ...overlayPairCrossoverSignals(
            a.instance,
            INDICATOR_DEFS[a.instance.type].shortLabel(a.instance.params),
            a.series.main,
            b.instance,
            INDICATOR_DEFS[b.instance.type].shortLabel(b.instance.params),
            b.series.main,
          ),
        );
      }
    }
    for (const instance of oscillatorInstances) {
      const series = seriesByInstance.get(instance.id)!;
      if (instance.type === 'macd') events.push(...macdSignalCrossSignals(series));
      if (instance.type === 'rsi') events.push(...rsiZoneExitSignals(series));
      if (instance.type === 'stochastic') events.push(...stochasticCrossSignals(series));
    }
    return events;
  }, [oscillatorInstances, overlayInstances, seriesByInstance]);

  const signalRules = useMemo(() => Array.from(new Set(signals.map((signal) => signal.rule))), [signals]);
  const activeSignalRules = useMemo(
    () => new Set(signalRules.filter((rule) => !mutedSignalRules.has(rule))),
    [signalRules, mutedSignalRules],
  );
  const activeSignalDirections = useMemo(
    () => new Set((['bullish', 'bearish'] as SignalDirection[]).filter((direction) => !mutedSignalDirections.has(direction))),
    [mutedSignalDirections],
  );

  const visibleSignals = useMemo(
    () =>
      signals
        .filter((signal) => signal.index >= zoom.start && signal.index <= zoom.end)
        .map((signal) => ({ ...signal, index: signal.index - zoom.start })),
    [signals, zoom.start, zoom.end],
  );

  const scrub = useChartScrub(visiblePoints.length, 'point', `${activeResolution.key}:${zoom.start}:${zoom.end}`);
  const selectedIndex = scrub.selectedIndex;
  const fullSelectedIndex = zoom.start + selectedIndex;

  useEffect(() => {
    if (!onContextChange) return;
    const selectedPoint = displayPoints[fullSelectedIndex];
    if (!selectedPoint) return;

    const instrumentContext = instances
      .map((instance) => {
        const def = INDICATOR_DEFS[instance.type];
        const series = seriesByInstance.get(instance.id)!;
        const value = primaryValueAt(instance, series, fullSelectedIndex);
        return `${def.shortLabel(instance.params)} (${def.formula(instance.params)}) = ${value}`;
      })
      .join('; ');

    const signalsAtBar = signals
      .filter((signal) => signal.index === fullSelectedIndex)
      .map((signal) => `${signal.rule} (${signal.direction})`)
      .join(', ');

    onContextChange(
      [
        `The stock chart is displaying ${activeResolution.label} bars${zoom.isZoomed ? ', zoomed into a subrange of the loaded history' : ''}.`,
        `The inspected bar is ${formatTrackingDate(selectedPoint.timestamp, sourceInterval === '1Min')} with open ${money(selectedPoint.open)}, high ${money(selectedPoint.high)}, low ${money(selectedPoint.low)}, close ${money(selectedPoint.close)}, and volume ${formatVolume(selectedPoint.volume)}.`,
        instrumentContext
          ? `Active technical indicators with their formulas and current values: ${instrumentContext}.`
          : 'No technical indicators are active.',
        signalsAtBar
          ? `Signals firing at the inspected bar: ${signalsAtBar}.`
          : 'No buy/sell signals are firing at the inspected bar.',
      ].join(' '),
    );
  }, [
    activeResolution.label,
    displayPoints,
    fullSelectedIndex,
    instances,
    onContextChange,
    seriesByInstance,
    signals,
    sourceInterval,
    zoom.isZoomed,
  ]);

  const onAddIndicator = (type: IndicatorType) => {
    setInstances((current) => [
      ...current,
      {
        id: createInstanceId(type),
        type,
        params: { ...INDICATOR_DEFS[type].defaultParams },
        color: nextIndicatorColor(current.map((instance) => instance.color)),
      },
    ]);
  };

  const onRemoveIndicator = (id: string) => {
    setInstances((current) => current.filter((instance) => instance.id !== id));
    setOpenSettings((current) => (current?.id === id ? null : current));
  };

  const onUpdateIndicatorParams = (id: string, params: IndicatorParams) => {
    setInstances((current) => current.map((instance) => (instance.id === id ? { ...instance, params } : instance)));
  };

  const onToggleSignalRule = (rule: string) => {
    setMutedSignalRules((current) => {
      const next = new Set(current);
      if (next.has(rule)) next.delete(rule);
      else next.add(rule);
      return next;
    });
  };

  const onToggleSignalDirection = (direction: SignalDirection) => {
    setMutedSignalDirections((current) => {
      const next = new Set(current);
      if (next.has(direction)) next.delete(direction);
      else next.add(direction);
      return next;
    });
  };

  if (displayPoints.length < 2) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>Price history unavailable</Text>
        <Text style={styles.emptyText}>Try another range or configure a market-data provider.</Text>
      </View>
    );
  }

  const change = visiblePoints.at(-1)!.close - visiblePoints[0].close;
  const lineColor = change >= 0 ? colors.teal : colors.negative;
  const selectedPoint = visiblePoints[selectedIndex];

  return (
    <View style={styles.root}>
      <IndicatorToolbar
        instances={instances}
        onAdd={onAddIndicator}
        onRemove={onRemoveIndicator}
        onUpdateParams={onUpdateIndicatorParams}
        openSettingsId={openSettings?.anchor === 'toolbar' ? openSettings.id : null}
        onOpenSettings={(id) => setOpenSettings({ id, anchor: 'toolbar' })}
        onCloseSettings={() => setOpenSettings(null)}
        resolutionOptions={options}
        activeResolution={activeResolution}
        onSelectResolution={setResolution}
        signalRules={signalRules}
        activeSignalRules={activeSignalRules}
        onToggleSignalRule={onToggleSignalRule}
        activeSignalDirections={activeSignalDirections}
        onToggleSignalDirection={onToggleSignalDirection}
      />

      <View style={styles.inspectionRow}>
        <View style={styles.inspectionPrimary}>
          <View>
            <Text style={styles.inspectionTime}>
              {formatTrackingDate(selectedPoint.timestamp, sourceInterval === '1Min')}
            </Text>
            <Text style={styles.inspectionHint}>SCROLL TO ZOOM · DRAG TO INSPECT</Text>
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
          {instances.map((instance) => (
            <Readout
              color={instance.color}
              key={instance.id}
              label={INDICATOR_DEFS[instance.type].shortLabel(instance.params)}
              value={primaryValueAt(instance, seriesByInstance.get(instance.id)!, fullSelectedIndex)}
            />
          ))}
        </View>
      </View>

      <PricePanel
        displayPoints={visiblePoints}
        overlays={visibleOverlayInstances}
        signals={visibleSignals}
        activeSignalRules={activeSignalRules}
        activeSignalDirections={activeSignalDirections}
        chartMin={chart.min}
        chartMax={chart.max}
        chartLine={chart.line}
        chartArea={chart.area}
        maxVolume={chart.maxVolume}
        lineColor={lineColor}
        includeTime={sourceInterval === '1Min'}
        scrub={scrub}
        onZoomAtRatio={zoom.zoomAtRatio}
      />

      {oscillatorInstances.map((instance) => {
        const def = INDICATOR_DEFS[instance.type];
        const fullSeries = seriesByInstance.get(instance.id)!;
        return (
          <OscillatorPanel
            key={instance.id}
            title={`${def.label} (${def.shortLabel(instance.params)})`}
            instance={instance}
            series={sliceSeries(fullSeries, zoom.start, zoom.end)}
            domain={def.domain === 'zeroToHundred' ? 'zeroToHundred' : 'auto'}
            pointCount={visiblePoints.length}
            scrub={scrub}
            paramSpecs={def.paramSpecs}
            isSettingsOpen={openSettings?.anchor === 'panel' && openSettings.id === instance.id}
            onOpenSettings={() => setOpenSettings({ id: instance.id, anchor: 'panel' })}
            onCloseSettings={() => setOpenSettings(null)}
            onUpdateParams={(params) => onUpdateIndicatorParams(instance.id, params)}
            onRemove={() => onRemoveIndicator(instance.id)}
          />
        );
      })}

      <View style={styles.zoomRow}>
        <RangeBrush
          points={displayPoints}
          start={zoom.start}
          end={zoom.end}
          lastIndex={zoom.lastIndex}
          onChange={zoom.setRange}
        />
        <View style={styles.zoomButtons}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Zoom in"
            onPress={() => zoom.zoomAtRatio(0.5, true)}
            style={styles.zoomButton}>
            <ZoomIn size={13} color={colors.inkMuted} />
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Zoom out"
            onPress={() => zoom.zoomAtRatio(0.5, false)}
            style={styles.zoomButton}>
            <ZoomOut size={13} color={colors.inkMuted} />
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Reset zoom"
            disabled={!zoom.isZoomed}
            onPress={zoom.reset}
            style={[styles.zoomButton, !zoom.isZoomed && styles.zoomButtonDisabled]}>
            <Maximize2 size={12} color={zoom.isZoomed ? colors.inkMuted : colors.inkFaint} />
          </Pressable>
        </View>
      </View>

      <View style={styles.dateRow}>
        <Text style={styles.dateText}>
          {formatAxisDate(visiblePoints[0].timestamp, sourceInterval === '1Min')}
        </Text>
        <Text style={styles.volumeLabel}>VOLUME</Text>
        <Text style={styles.dateText}>
          {formatAxisDate(visiblePoints.at(-1)!.timestamp, sourceInterval === '1Min')}
        </Text>
      </View>
    </View>
  );
}

function Readout({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.readout}>
      <Text style={[styles.readoutLabel, color ? { color } : null]}>{label}</Text>
      <Text style={styles.readoutValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { position: 'relative', gap: 4 },
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
  inspectionTime: { color: colors.ink, fontSize: 11, fontWeight: '700', fontVariant: ['tabular-nums'] },
  inspectionHint: { color: colors.inkFaint, fontSize: 7, fontWeight: '800', letterSpacing: 0.7, marginTop: 4 },
  closeLabel: { color: colors.inkFaint, fontSize: 7, fontWeight: '900', letterSpacing: 0.8 },
  closeValue: { color: colors.ink, fontSize: 18, fontWeight: '700', marginTop: 2, fontVariant: ['tabular-nums'] },
  ohlcRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 14 },
  readout: { minWidth: 42 },
  readoutLabel: { color: colors.inkFaint, fontSize: 7, fontWeight: '900', letterSpacing: 0.7 },
  readoutValue: { color: colors.ink, fontSize: 10, fontWeight: '700', marginTop: 4, fontVariant: ['tabular-nums'] },
  zoomRow: {
    marginTop: 10,
    paddingHorizontal: 4,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  zoomButtons: { flexDirection: 'row', gap: 5 },
  zoomButton: {
    width: 26,
    height: 26,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  zoomButtonDisabled: { opacity: 0.45 },
  dateRow: {
    marginTop: 6,
    paddingHorizontal: 4,
    paddingBottom: 9,
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
