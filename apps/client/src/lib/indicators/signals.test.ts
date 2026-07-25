/// <reference types="node" />
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  macdSignalCrossSignals,
  overlayPairCrossoverSignals,
  rsiZoneExitSignals,
  stochasticCrossSignals,
} from './signals.ts';

test('macdSignalCrossSignals flags where the MACD line crosses its signal line', () => {
  const macd = {
    line: [1, 2, 4, 3, 1],
    signal: [3, 3, 3, 3, 3],
  };
  const events = macdSignalCrossSignals(macd);
  assert.deepEqual(events, [
    { index: 2, direction: 'bullish', rule: 'MACD signal cross' },
    { index: 4, direction: 'bearish', rule: 'MACD signal cross' },
  ]);
});

test('rsiZoneExitSignals only flags exiting overbought/oversold, not entering', () => {
  const rsi = { main: [75, 72, 68, 65, 25, 28, 32, 35] };
  const events = rsiZoneExitSignals(rsi);
  assert.deepEqual(events, [
    { index: 2, direction: 'bearish', rule: 'RSI exits overbought' },
    { index: 6, direction: 'bullish', rule: 'RSI exits oversold' },
  ]);
});

test('stochasticCrossSignals flags where %K crosses %D', () => {
  const stochastic = {
    k: [20, 40, 60, 50, 30],
    d: [45, 45, 45, 45, 45],
  };
  const events = stochasticCrossSignals(stochastic);
  assert.deepEqual(events, [
    { index: 2, direction: 'bullish', rule: 'Stochastic %K/%D cross' },
    { index: 4, direction: 'bearish', rule: 'Stochastic %K/%D cross' },
  ]);
});

test('overlayPairCrossoverSignals flags crossovers between two overlay series', () => {
  const instanceA = { id: 'a', type: 'sma' as const, params: {}, color: '#000' };
  const instanceB = { id: 'b', type: 'ema' as const, params: {}, color: '#fff' };
  const seriesA = [10, 30, 50, 40, 20];
  const seriesB = [40, 40, 40, 40, 40];
  const events = overlayPairCrossoverSignals(instanceA, 'SMA', seriesA, instanceB, 'EMA', seriesB);
  assert.deepEqual(events, [
    { index: 2, direction: 'bullish', rule: 'SMA × EMA cross' },
    { index: 4, direction: 'bearish', rule: 'SMA × EMA cross' },
  ]);
});
