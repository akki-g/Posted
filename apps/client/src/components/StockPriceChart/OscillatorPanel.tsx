import { Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Line, Path, Rect } from 'react-native-svg';
import { Settings2, X } from 'lucide-react-native';

import type { ChartScrub } from '@/lib/chartScrub';
import type { IndicatorInstance, IndicatorParams, IndicatorSeries, ParamSpec } from '@/lib/indicators/types';
import { colors, radius } from '@/theme/tokens';

import { ParamPopover } from './ParamPopover';

const WIDTH = 900;
const HEIGHT = 110;
const TOP = 10;
const BOTTOM = 10;

function valueToY(value: number, min: number, range: number): number {
  return TOP + (1 - (value - min) / range) * (HEIGHT - TOP - BOTTOM);
}

function seriesPath(values: (number | null)[], min: number, range: number): string {
  let drawing = false;
  return values
    .map((value, index) => {
      if (value == null) {
        drawing = false;
        return '';
      }
      const x = (index / Math.max(values.length - 1, 1)) * WIDTH;
      const y = valueToY(value, min, range);
      const command = drawing ? 'L' : 'M';
      drawing = true;
      return `${command} ${x} ${y}`;
    })
    .filter(Boolean)
    .join(' ');
}

type Props = {
  title: string;
  instance: IndicatorInstance;
  series: IndicatorSeries;
  domain: 'zeroToHundred' | 'auto';
  pointCount: number;
  scrub: ChartScrub;
  paramSpecs: ParamSpec[];
  isSettingsOpen: boolean;
  onOpenSettings: () => void;
  onCloseSettings: () => void;
  onUpdateParams: (params: IndicatorParams) => void;
  onRemove: () => void;
};

export function OscillatorPanel({
  title,
  instance,
  series,
  domain,
  pointCount,
  scrub,
  paramSpecs,
  isSettingsOpen,
  onOpenSettings,
  onCloseSettings,
  onUpdateParams,
  onRemove,
}: Props) {
  const selectedIndex = scrub.selectedIndex;

  let min: number;
  let max: number;
  if (domain === 'zeroToHundred') {
    min = 0;
    max = 100;
  } else {
    const values = Object.values(series)
      .flat()
      .filter((value): value is number => value != null);
    const rawMax = Math.max(...values, 0);
    const rawMin = Math.min(...values, 0);
    const padding = Math.max((rawMax - rawMin) * 0.1, 0.01);
    max = rawMax + padding;
    min = rawMin - padding;
  }
  const range = max - min || 1;
  const crosshairX = (selectedIndex / Math.max(pointCount - 1, 1)) * WIDTH;

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.title}>{title}</Text>
        <View style={styles.headerActions}>
          {paramSpecs.length ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${title} settings`}
              accessibilityState={{ selected: isSettingsOpen }}
              onPress={() => (isSettingsOpen ? onCloseSettings() : onOpenSettings())}
              style={[styles.iconButton, isSettingsOpen && styles.iconButtonActive]}>
              <Settings2 size={13} color={isSettingsOpen ? colors.tealDark : colors.inkMuted} />
            </Pressable>
          ) : null}
          <Pressable accessibilityRole="button" accessibilityLabel={`Remove ${title}`} onPress={onRemove} style={styles.iconButton}>
            <X size={13} color={colors.inkMuted} />
          </Pressable>
        </View>
      </View>
      {isSettingsOpen ? (
        <View style={styles.paramRow}>
          <ParamPopover
            params={instance.params}
            paramSpecs={paramSpecs}
            onApply={(params) => {
              onUpdateParams(params);
              onCloseSettings();
            }}
            onClose={onCloseSettings}
          />
        </View>
      ) : null}
      <View style={styles.chartArea}>
        <Svg width="100%" height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none">
          {domain === 'zeroToHundred' ? (
            <>
              <Line x1="0" x2={WIDTH} y1={valueToY(70, min, range)} y2={valueToY(70, min, range)} stroke={colors.line} strokeDasharray="4 7" strokeWidth="1" />
              <Line x1="0" x2={WIDTH} y1={valueToY(30, min, range)} y2={valueToY(30, min, range)} stroke={colors.line} strokeDasharray="4 7" strokeWidth="1" />
            </>
          ) : (
            <Line x1="0" x2={WIDTH} y1={valueToY(0, min, range)} y2={valueToY(0, min, range)} stroke={colors.lineStrong} strokeWidth="1" />
          )}
          {instance.type === 'macd' ? (
            <>
              {series.histogram.map((value, index) => {
                if (value == null) return null;
                const x = (index / Math.max(series.histogram.length - 1, 1)) * WIDTH;
                const zeroY = valueToY(0, min, range);
                const barY = valueToY(value, min, range);
                const barWidth = Math.max(0.8, WIDTH / series.histogram.length - 0.6);
                return (
                  <Rect
                    key={index}
                    x={x}
                    y={Math.min(barY, zeroY)}
                    width={barWidth}
                    height={Math.abs(barY - zeroY)}
                    fill={value >= 0 ? colors.positive : colors.negative}
                  />
                );
              })}
              <Path d={seriesPath(series.line, min, range)} fill="none" stroke={instance.color} strokeWidth="1.6" />
              <Path d={seriesPath(series.signal, min, range)} fill="none" stroke={colors.inkMuted} strokeDasharray="4 3" strokeWidth="1.4" />
            </>
          ) : instance.type === 'stochastic' ? (
            <>
              <Path d={seriesPath(series.k, min, range)} fill="none" stroke={instance.color} strokeWidth="1.6" />
              <Path d={seriesPath(series.d, min, range)} fill="none" stroke={colors.inkMuted} strokeDasharray="4 3" strokeWidth="1.4" />
            </>
          ) : (
            <Path d={seriesPath(series.main, min, range)} fill="none" stroke={instance.color} strokeWidth="1.6" />
          )}
          <Line x1={crosshairX} x2={crosshairX} y1={0} y2={HEIGHT} stroke={colors.inkMuted} strokeDasharray="3 4" strokeWidth="1" />
        </Svg>
        <View
          {...scrub.panHandlers}
          accessible
          accessibilityLabel={`${title} panel`}
          accessibilityRole="adjustable"
          accessibilityValue={scrub.accessibilityValue}
          onAccessibilityAction={scrub.onAccessibilityAction}
          accessibilityActions={[
            { name: 'increment', label: 'Next bar' },
            { name: 'decrement', label: 'Previous bar' },
          ]}
          onPointerDown={scrub.onPointerDown}
          onPointerMove={scrub.onPointerMove}
          style={styles.trackingLayer}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: 'relative',
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: 8,
    paddingBottom: 4,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 4,
    marginBottom: 4,
  },
  title: { color: colors.inkMuted, fontSize: 9, fontWeight: '800', letterSpacing: 0.6 },
  headerActions: { flexDirection: 'row', gap: 6 },
  paramRow: { paddingHorizontal: 4, marginBottom: 8 },
  iconButton: {
    width: 22,
    height: 22,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconButtonActive: { borderColor: colors.teal, backgroundColor: colors.tealSoft },
  chartArea: { height: HEIGHT, position: 'relative', overflow: 'hidden' },
  trackingLayer: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    cursor: 'crosshair',
  } as never,
});
