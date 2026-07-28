/// <reference types="node" />
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { isStale, targetConnections } from './useConnectionSync.ts';

const FRESH = new Date(Date.now() - 60_000).toISOString(); // 1 minute ago
const STALE = new Date(Date.now() - 10 * 60_000).toISOString(); // 10 minutes ago

test('isStale is false when every connection synced within the last 5 minutes', () => {
  assert.equal(
    isStale([{ id: 'a', last_synced_at: FRESH, demo: false }]),
    false,
  );
});

test('isStale is true when any connection is older than 5 minutes', () => {
  assert.equal(
    isStale([
      { id: 'a', last_synced_at: FRESH, demo: false },
      { id: 'b', last_synced_at: STALE, demo: false },
    ]),
    true,
  );
});

test('isStale is true when a connection has never synced', () => {
  assert.equal(isStale([{ id: 'a', last_synced_at: null, demo: false }]), true);
});

test('targetConnections syncs only live connections when at least one exists', () => {
  const result = targetConnections([
    { id: 'live-1', last_synced_at: FRESH, demo: false },
    { id: 'demo-1', last_synced_at: FRESH, demo: true },
  ]);
  assert.deepEqual(result.map((c) => c.id), ['live-1']);
});

test('targetConnections falls back to the first demo connection when there is no live one', () => {
  const result = targetConnections([{ id: 'demo-1', last_synced_at: FRESH, demo: true }]);
  assert.deepEqual(result.map((c) => c.id), ['demo-1']);
});

test('targetConnections returns nothing for an empty connection list', () => {
  assert.deepEqual(targetConnections([]), []);
});
