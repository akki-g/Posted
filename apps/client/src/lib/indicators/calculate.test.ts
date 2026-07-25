/// <reference types="node" />
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  calculateBollinger,
  calculateEma,
  calculateMacd,
  calculateRsi,
  calculateSma,
  calculateStochastic,
  calculateVwap,
} from './calculate.ts';

function bar(overrides: Partial<{ timestamp: string; open: number; high: number; low: number; close: number; volume: number }>) {
  return {
    timestamp: overrides.timestamp ?? '2026-01-01T00:00:00Z',
    open: overrides.open ?? overrides.close ?? 0,
    high: overrides.high ?? overrides.close ?? 0,
    low: overrides.low ?? overrides.close ?? 0,
    close: overrides.close ?? 0,
    volume: overrides.volume ?? 0,
  };
}

function bars(closes: number[]) {
  return closes.map((close, index) => bar({ timestamp: `2026-01-0${index + 1}T00:00:00Z`, close }));
}

function assertCloseArray(actual: (number | null)[], expected: (number | null)[], epsilon = 0.001) {
  assert.equal(actual.length, expected.length);
  actual.forEach((value, index) => {
    const target = expected[index];
    if (target == null) {
      assert.equal(value, null, `index ${index}: expected null`);
    } else {
      assert.ok(value != null, `index ${index}: expected ${target}, got null`);
      assert.ok(
        Math.abs(value - target) < epsilon,
        `index ${index}: expected ${target}, got ${value}`,
      );
    }
  });
}

test('calculateSma computes a simple moving average with a custom period', () => {
  const result = calculateSma(bars([10, 20, 15, 25, 20, 30]), { period: 3 });
  assertCloseArray(result.main, [null, null, 15, 20, 20, 25]);
});

test('calculateEma computes an exponential moving average with a custom period', () => {
  const result = calculateEma(bars([10, 20, 15, 25, 20, 30]), { period: 3 });
  assertCloseArray(result.main, [null, null, 15, 20, 20, 25]);
});

test('calculateBollinger computes bands with a custom period and std-dev multiplier', () => {
  const result = calculateBollinger(bars([10, 12, 11, 13, 15, 14]), { period: 3, stdDev: 1 });
  assertCloseArray(result.middle, [null, null, 11, 12, 13, 14]);
  assertCloseArray(result.upper, [null, null, 11.8165, 12.8165, 14.63299, 14.8165], 0.001);
  assertCloseArray(result.lower, [null, null, 10.1835, 11.1835, 11.36701, 13.1835], 0.001);
});

test('calculateVwap accumulates typical-price-weighted average from the first bar', () => {
  const points = [
    bar({ high: 10, low: 10, close: 10, volume: 100 }),
    bar({ high: 20, low: 20, close: 20, volume: 100 }),
    bar({ high: 12, low: 12, close: 12, volume: 200 }),
  ];
  const result = calculateVwap(points, {});
  assertCloseArray(result.main, [10, 15, 13.5]);
});

test('calculateRsi matches a hand-computed Wilder RSI with a custom period', () => {
  const result = calculateRsi(bars([44, 44.5, 43.5, 44.5, 45, 44]), { period: 3 });
  assertCloseArray(result.main, [null, null, null, 60, 69.2308, 40.9091], 0.001);
});

test('calculateMacd computes line, signal, and histogram from a hand-computed example', () => {
  const result = calculateMacd(bars([10, 11, 12, 13, 14]), { fast: 2, slow: 3, signal: 2 });
  assertCloseArray(result.line, [null, null, 0.5, 0.5, 0.5]);
  assertCloseArray(result.signal, [null, null, null, 0.5, 0.5]);
  assertCloseArray(result.histogram, [null, null, null, 0, 0]);
});

test('calculateStochastic computes %K and %D from a hand-computed example', () => {
  const points = [
    bar({ high: 10, low: 8, close: 9 }),
    bar({ high: 11, low: 9, close: 9.5 }),
    bar({ high: 9, low: 7, close: 8 }),
    bar({ high: 13, low: 11, close: 12.5 }),
    bar({ high: 14, low: 12, close: 13 }),
  ];
  const result = calculateStochastic(points, { kPeriod: 3, dPeriod: 2 });
  assertCloseArray(result.k, [null, null, 25, 91.66667, 85.71429], 0.001);
  assertCloseArray(result.d, [null, null, null, 58.33333, 88.69048], 0.001);
});
