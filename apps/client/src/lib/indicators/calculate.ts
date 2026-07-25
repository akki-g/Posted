import type { PriceBar } from '@/lib/marketTypes';
import type { IndicatorParams, IndicatorSeries } from './types';

function simpleMovingAverage(values: number[], period: number): (number | null)[] {
  return values.map((_, index) => {
    if (index < period - 1) return null;
    const window = values.slice(index - period + 1, index + 1);
    return window.reduce((total, value) => total + value, 0) / period;
  });
}

function exponentialMovingAverage(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = values.map(() => null);
  if (values.length < period) return result;
  const multiplier = 2 / (period + 1);
  const seed = values.slice(0, period).reduce((total, value) => total + value, 0) / period;
  result[period - 1] = seed;
  for (let index = period; index < values.length; index += 1) {
    result[index] = values[index] * multiplier + result[index - 1]! * (1 - multiplier);
  }
  return result;
}

export function calculateSma(bars: PriceBar[], params: IndicatorParams): IndicatorSeries {
  return { main: simpleMovingAverage(bars.map((b) => b.close), params.period) };
}

export function calculateEma(bars: PriceBar[], params: IndicatorParams): IndicatorSeries {
  return { main: exponentialMovingAverage(bars.map((b) => b.close), params.period) };
}

export function calculateBollinger(bars: PriceBar[], params: IndicatorParams): IndicatorSeries {
  const period = params.period;
  const stdDevMultiplier = params.stdDev;
  const closes = bars.map((b) => b.close);
  const middle = simpleMovingAverage(closes, period);
  const upper: (number | null)[] = closes.map((_, index) => {
    if (index < period - 1) return null;
    const window = closes.slice(index - period + 1, index + 1);
    const average = middle[index]!;
    const variance = window.reduce((total, value) => total + (value - average) ** 2, 0) / period;
    return average + stdDevMultiplier * Math.sqrt(variance);
  });
  const lower: (number | null)[] = closes.map((_, index) => {
    if (index < period - 1) return null;
    const average = middle[index]!;
    return average - (upper[index]! - average);
  });
  return { middle, upper, lower };
}

export function calculateVwap(bars: PriceBar[], _params: IndicatorParams): IndicatorSeries {
  let cumulativeTypicalVolume = 0;
  let cumulativeVolume = 0;
  const main = bars.map((bar) => {
    const typicalPrice = (bar.high + bar.low + bar.close) / 3;
    cumulativeTypicalVolume += typicalPrice * bar.volume;
    cumulativeVolume += bar.volume;
    return cumulativeVolume === 0 ? null : cumulativeTypicalVolume / cumulativeVolume;
  });
  return { main };
}

function rsiFromAverages(averageGain: number, averageLoss: number): number {
  if (averageLoss === 0) return 100;
  const relativeStrength = averageGain / averageLoss;
  return 100 - 100 / (1 + relativeStrength);
}

export function calculateRsi(bars: PriceBar[], params: IndicatorParams): IndicatorSeries {
  const period = params.period;
  const closes = bars.map((b) => b.close);
  const main: (number | null)[] = closes.map(() => null);
  if (closes.length < period + 1) return { main };

  let gainSum = 0;
  let lossSum = 0;
  for (let index = 1; index <= period; index += 1) {
    const delta = closes[index] - closes[index - 1];
    if (delta >= 0) gainSum += delta;
    else lossSum += -delta;
  }
  let averageGain = gainSum / period;
  let averageLoss = lossSum / period;
  main[period] = rsiFromAverages(averageGain, averageLoss);

  for (let index = period + 1; index < closes.length; index += 1) {
    const delta = closes[index] - closes[index - 1];
    const gain = delta >= 0 ? delta : 0;
    const loss = delta < 0 ? -delta : 0;
    averageGain = (averageGain * (period - 1) + gain) / period;
    averageLoss = (averageLoss * (period - 1) + loss) / period;
    main[index] = rsiFromAverages(averageGain, averageLoss);
  }
  return { main };
}

export function calculateMacd(bars: PriceBar[], params: IndicatorParams): IndicatorSeries {
  const closes = bars.map((b) => b.close);
  const fastEma = exponentialMovingAverage(closes, params.fast);
  const slowEma = exponentialMovingAverage(closes, params.slow);
  const line: (number | null)[] = closes.map((_, index) => {
    const fast = fastEma[index];
    const slow = slowEma[index];
    return fast == null || slow == null ? null : fast - slow;
  });
  const signalStartIndex = line.findIndex((value) => value != null);
  const lineValues = line.filter((value): value is number => value != null);
  const signalOnValid = exponentialMovingAverage(lineValues, params.signal);
  const signal: (number | null)[] = line.map((_, index) => {
    if (signalStartIndex < 0 || index < signalStartIndex) return null;
    return signalOnValid[index - signalStartIndex] ?? null;
  });
  const histogram: (number | null)[] = line.map((_, index) => {
    const lineValue = line[index];
    const signalValue = signal[index];
    return lineValue == null || signalValue == null ? null : lineValue - signalValue;
  });
  return { line, signal, histogram };
}

export function calculateStochastic(bars: PriceBar[], params: IndicatorParams): IndicatorSeries {
  const kPeriod = params.kPeriod;
  const dPeriod = params.dPeriod;
  const k: (number | null)[] = bars.map((_, index) => {
    if (index < kPeriod - 1) return null;
    const window = bars.slice(index - kPeriod + 1, index + 1);
    const highestHigh = Math.max(...window.map((b) => b.high));
    const lowestLow = Math.min(...window.map((b) => b.low));
    const range = highestHigh - lowestLow;
    if (range === 0) return 50;
    return ((bars[index].close - lowestLow) / range) * 100;
  });
  const kStartIndex = k.findIndex((value) => value != null);
  const kValues = k.filter((value): value is number => value != null);
  const dOnValid = simpleMovingAverage(kValues, dPeriod);
  const d: (number | null)[] = k.map((_, index) => {
    if (kStartIndex < 0 || index < kStartIndex) return null;
    return dOnValid[index - kStartIndex] ?? null;
  });
  return { k, d };
}
