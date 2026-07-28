/// <reference types="node" />
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { normalizePortfolioTab, PORTFOLIO_TABS } from './portfolioTab.ts';

test('normalizePortfolioTab returns each known tab unchanged', () => {
  for (const tab of PORTFOLIO_TABS) {
    assert.equal(normalizePortfolioTab(tab), tab);
  }
});

test('normalizePortfolioTab defaults to holdings when the param is missing', () => {
  assert.equal(normalizePortfolioTab(undefined), 'holdings');
  assert.equal(normalizePortfolioTab(null), 'holdings');
  assert.equal(normalizePortfolioTab(''), 'holdings');
});

test('normalizePortfolioTab defaults to holdings for an unknown value', () => {
  assert.equal(normalizePortfolioTab('transactions'), 'holdings');
  assert.equal(normalizePortfolioTab('HOLDINGS'), 'holdings'); // case-sensitive by design
});
