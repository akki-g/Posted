/// <reference types="node" />
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { formatAxisDate, formatTrackingDate, formatVolume } from './formatting.ts';

test('formatTrackingDate omits time when includeTime is false', () => {
  const result = formatTrackingDate('2026-01-15T04:00:00Z', false);
  assert.ok(!/\d{1,2}:\d{2}/.test(result), `expected no time-of-day in "${result}"`);
  assert.match(result, /Jan 1[45], 2026/);
});

test('formatTrackingDate includes time when includeTime is true', () => {
  const result = formatTrackingDate('2026-01-15T16:30:00Z', true);
  assert.match(result, /\d{1,2}:\d{2}/);
  assert.match(result, /2026/);
});

test('formatAxisDate omits time when includeTime is false', () => {
  const result = formatAxisDate('2026-01-15T04:00:00Z', false);
  assert.ok(!/\d{1,2}:\d{2}/.test(result));
});

test('formatVolume abbreviates without relying on Intl compact notation', () => {
  assert.equal(formatVolume(850), '850');
  assert.equal(formatVolume(4_500), '4.5K');
  assert.equal(formatVolume(54_391_205), '54.4M');
  assert.equal(formatVolume(2_000_000), '2M');
  assert.equal(formatVolume(1_200_000_000), '1.2B');
  assert.equal(formatVolume(999_950), '1M');
  assert.equal(formatVolume(999_999_999), '1B');
});
