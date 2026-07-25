import type { IndicatorInstance, IndicatorSeries } from './types';

export type SignalDirection = 'bullish' | 'bearish';

export type SignalEvent = {
  index: number;
  direction: SignalDirection;
  rule: string;
};

type CrossingDirection = 'up' | 'down';

function detectCrossovers(
  seriesA: (number | null)[],
  seriesB: (number | null)[],
): { index: number; crossing: CrossingDirection }[] {
  const events: { index: number; crossing: CrossingDirection }[] = [];
  const length = Math.min(seriesA.length, seriesB.length);
  for (let index = 1; index < length; index += 1) {
    const previousA = seriesA[index - 1];
    const previousB = seriesB[index - 1];
    const currentA = seriesA[index];
    const currentB = seriesB[index];
    if (previousA == null || previousB == null || currentA == null || currentB == null) continue;
    if (previousA <= previousB && currentA > currentB) {
      events.push({ index, crossing: 'up' });
    } else if (previousA >= previousB && currentA < currentB) {
      events.push({ index, crossing: 'down' });
    }
  }
  return events;
}

function detectThresholdCrosses(
  series: (number | null)[],
  threshold: number,
): { index: number; crossing: CrossingDirection }[] {
  const events: { index: number; crossing: CrossingDirection }[] = [];
  for (let index = 1; index < series.length; index += 1) {
    const previous = series[index - 1];
    const current = series[index];
    if (previous == null || current == null) continue;
    if (previous <= threshold && current > threshold) {
      events.push({ index, crossing: 'up' });
    } else if (previous >= threshold && current < threshold) {
      events.push({ index, crossing: 'down' });
    }
  }
  return events;
}

export function overlayPairCrossoverSignals(
  _instanceA: IndicatorInstance,
  labelA: string,
  seriesA: (number | null)[],
  _instanceB: IndicatorInstance,
  labelB: string,
  seriesB: (number | null)[],
): SignalEvent[] {
  return detectCrossovers(seriesA, seriesB).map((event) => ({
    index: event.index,
    direction: event.crossing === 'up' ? 'bullish' : 'bearish',
    rule: `${labelA} × ${labelB} cross`,
  }));
}

export function macdSignalCrossSignals(macd: IndicatorSeries): SignalEvent[] {
  return detectCrossovers(macd.line, macd.signal).map((event) => ({
    index: event.index,
    direction: event.crossing === 'up' ? 'bullish' : 'bearish',
    rule: 'MACD signal cross',
  }));
}

export function rsiZoneExitSignals(rsi: IndicatorSeries): SignalEvent[] {
  const overboughtExits = detectThresholdCrosses(rsi.main, 70)
    .filter((event) => event.crossing === 'down')
    .map((event): SignalEvent => ({ index: event.index, direction: 'bearish', rule: 'RSI exits overbought' }));
  const oversoldExits = detectThresholdCrosses(rsi.main, 30)
    .filter((event) => event.crossing === 'up')
    .map((event): SignalEvent => ({ index: event.index, direction: 'bullish', rule: 'RSI exits oversold' }));
  return [...overboughtExits, ...oversoldExits];
}

export function stochasticCrossSignals(stochastic: IndicatorSeries): SignalEvent[] {
  return detectCrossovers(stochastic.k, stochastic.d).map((event) => ({
    index: event.index,
    direction: event.crossing === 'up' ? 'bullish' : 'bearish',
    rule: 'Stochastic %K/%D cross',
  }));
}
