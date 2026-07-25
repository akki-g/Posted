/// <reference types="node" />
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { availableResolutions, barIndexForX, pointIndexForX } from './chartInteraction.ts';

test('barIndexForX selects the bar whose column contains the pointer', () => {
  // 12 equal columns across 120px: bar 0 spans [0,10), bar 6 spans [60,70), bar 11 spans [110,120)
  assert.equal(barIndexForX(9, 120, 12), 0);
  assert.equal(barIndexForX(69, 120, 12), 6);
  assert.equal(barIndexForX(115, 120, 12), 11);
});

test('barIndexForX clamps to the valid index range', () => {
  assert.equal(barIndexForX(-5, 120, 12), 0);
  assert.equal(barIndexForX(120, 120, 12), 11);
  assert.equal(barIndexForX(500, 120, 12), 11);
});

test('barIndexForX handles a single bar and zero width without NaN', () => {
  assert.equal(barIndexForX(10, 120, 1), 0);
  assert.equal(barIndexForX(0, 0, 12), 0);
});

test('pointIndexForX maps to the nearest plotted point', () => {
  // 30 points across 870px: spacing 30px, midpoints round to the nearer index
  assert.equal(pointIndexForX(0, 870, 30), 0);
  assert.equal(pointIndexForX(870, 870, 30), 29);
  assert.equal(pointIndexForX(14, 870, 30), 0);
  assert.equal(pointIndexForX(16, 870, 30), 1);
});

test('availableResolutions omits aggregations that would leave fewer than 2 bars', () => {
  assert.deepEqual(
    availableResolutions('1Day', 5).map((option) => option.key),
    ['source'],
  );
  assert.deepEqual(
    availableResolutions('1Min', 5).map((option) => option.key),
    ['source'],
  );
  assert.deepEqual(
    availableResolutions('1Min', 14).map((option) => option.key),
    ['source', '5m'],
  );
});

test('availableResolutions keeps aggregations once enough bars exist', () => {
  assert.deepEqual(
    availableResolutions('1Day', 10).map((option) => option.key),
    ['source', '1w'],
  );
  assert.deepEqual(
    availableResolutions('1Min', 20).map((option) => option.key),
    ['source', '5m', '15m'],
  );
});
