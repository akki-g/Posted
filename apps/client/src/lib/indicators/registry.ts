import { colors } from '@/theme/tokens';
import {
  calculateBollinger,
  calculateEma,
  calculateMacd,
  calculateRsi,
  calculateSma,
  calculateStochastic,
  calculateVwap,
} from './calculate';
import type { IndicatorCategory, IndicatorDef, IndicatorType } from './types';

export const INDICATOR_DEFS: Record<IndicatorType, IndicatorDef> = {
  sma: {
    type: 'sma',
    label: 'Simple Moving Average',
    category: 'trend',
    kind: 'overlay',
    domain: 'price',
    defaultParams: { period: 20 },
    paramSpecs: [{ key: 'period', label: 'Period', min: 2, max: 200, step: 1 }],
    shortLabel: (params) => `SMA ${params.period}`,
    formula: (params) => `SMA(${params.period}) = Σ Close ÷ ${params.period}`,
    calculate: calculateSma,
  },
  ema: {
    type: 'ema',
    label: 'Exponential Moving Average',
    category: 'trend',
    kind: 'overlay',
    domain: 'price',
    defaultParams: { period: 20 },
    paramSpecs: [{ key: 'period', label: 'Period', min: 2, max: 200, step: 1 }],
    shortLabel: (params) => `EMA ${params.period}`,
    formula: (params) => `EMAₜ = αCloseₜ + (1−α)EMAₜ₋₁ · α = 2÷(${params.period}+1)`,
    calculate: calculateEma,
  },
  bollinger: {
    type: 'bollinger',
    label: 'Bollinger Bands',
    category: 'trend',
    kind: 'overlay',
    domain: 'price',
    defaultParams: { period: 20, stdDev: 2 },
    paramSpecs: [
      { key: 'period', label: 'Period', min: 2, max: 200, step: 1 },
      { key: 'stdDev', label: 'Std Dev', min: 0.5, max: 4, step: 0.5 },
    ],
    shortLabel: (params) => `BB ${params.period}, ${params.stdDev}`,
    formula: (params) => `Bands = SMA(${params.period}) ± ${params.stdDev}σ(${params.period})`,
    calculate: calculateBollinger,
  },
  vwap: {
    type: 'vwap',
    label: 'Volume-Weighted Average Price',
    category: 'volume',
    kind: 'overlay',
    domain: 'price',
    defaultParams: {},
    paramSpecs: [],
    shortLabel: () => 'VWAP',
    formula: () => 'VWAP = Σ(Typical price × Volume) ÷ Σ Volume',
    calculate: calculateVwap,
  },
  rsi: {
    type: 'rsi',
    label: 'Relative Strength Index',
    category: 'momentum',
    kind: 'oscillator',
    domain: 'zeroToHundred',
    defaultParams: { period: 14 },
    paramSpecs: [{ key: 'period', label: 'Period', min: 2, max: 100, step: 1 }],
    shortLabel: (params) => `RSI ${params.period}`,
    formula: (params) => `RSI(${params.period}) = 100 − 100 ÷ (1 + AvgGain ÷ AvgLoss)`,
    calculate: calculateRsi,
  },
  macd: {
    type: 'macd',
    label: 'MACD',
    category: 'momentum',
    kind: 'oscillator',
    domain: 'auto',
    defaultParams: { fast: 12, slow: 26, signal: 9 },
    paramSpecs: [
      { key: 'fast', label: 'Fast', min: 2, max: 100, step: 1 },
      { key: 'slow', label: 'Slow', min: 2, max: 200, step: 1 },
      { key: 'signal', label: 'Signal', min: 2, max: 100, step: 1 },
    ],
    shortLabel: (params) => `MACD ${params.fast},${params.slow},${params.signal}`,
    formula: (params) => `MACD = EMA(${params.fast}) − EMA(${params.slow}); Signal = EMA(MACD, ${params.signal})`,
    calculate: calculateMacd,
  },
  stochastic: {
    type: 'stochastic',
    label: 'Stochastic Oscillator',
    category: 'momentum',
    kind: 'oscillator',
    domain: 'zeroToHundred',
    defaultParams: { kPeriod: 14, dPeriod: 3 },
    paramSpecs: [
      { key: 'kPeriod', label: '%K Period', min: 2, max: 100, step: 1 },
      { key: 'dPeriod', label: '%D Period', min: 2, max: 50, step: 1 },
    ],
    shortLabel: (params) => `Stoch ${params.kPeriod},${params.dPeriod}`,
    formula: (params) =>
      `%K = 100×(Close−LL${params.kPeriod})÷(HH${params.kPeriod}−LL${params.kPeriod}); %D = SMA(%K, ${params.dPeriod})`,
    calculate: calculateStochastic,
  },
};

export const INDICATOR_CATEGORY_LABELS: Record<IndicatorCategory, string> = {
  trend: 'Trend',
  momentum: 'Momentum',
  volume: 'Volume',
};

export const INDICATOR_PALETTE: string[] = [
  colors.blue,
  colors.warning,
  colors.purple,
  colors.pink,
  colors.orange,
  colors.indigo,
  colors.brown,
];

export function nextIndicatorColor(usedColors: string[]): string {
  const available = INDICATOR_PALETTE.find((color) => !usedColors.includes(color));
  if (available) return available;
  return INDICATOR_PALETTE[usedColors.length % INDICATOR_PALETTE.length];
}
