import { useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect } from 'react';
import { StyleSheet, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { FeedTab } from '@/components/portfolio/FeedTab';
import { HoldingsTab } from '@/components/portfolio/HoldingsTab';
import { InsidersTab } from '@/components/portfolio/InsidersTab';
import { NewsTab } from '@/components/portfolio/NewsTab';
import { FilterChip } from '@/components/ui';
import { setAssistantSection } from '@/lib/assistantSection';
import {
  normalizePortfolioTab,
  PORTFOLIO_TAB_LABEL,
  PORTFOLIO_TAB_TITLE,
  PORTFOLIO_TABS,
  type PortfolioTab,
} from '@/lib/portfolioTab';
import { spacing } from '@/theme/tokens';

// "Portfolio detail" — the single tabbed destination that replaced the four
// separate /holdings, /feed, /news, /insiders routes, per the approved IA.
// Mirrors app/index.tsx's lens-tabbed spine: a FilterChip tablist driven by a
// `?tab=` param via router.setParams (no stack navigation). The old routes
// survive as redirect shims for deep links and bookmarks.
const ASSISTANT_CONTEXT: Record<PortfolioTab, string> = {
  holdings:
    'The user is viewing all portfolio holdings aggregated across their brokerage accounts. Fetch current holdings with the available tools before answering.',
  feed: 'The user is viewing the impact feed — portfolio-relevant events ranked by materiality, exposure, source confidence, and recency. Fetch current data with the available tools before answering.',
  news: 'The user is viewing market news stories feeding the impact feed, each with a portfolio impact score. Fetch current data with the available tools before answering.',
  // Insider context is symbol-aware and computed at render time.
  insiders: '',
};

export default function PortfolioScreen() {
  const params = useLocalSearchParams<{ tab?: string; symbol?: string }>();
  const router = useRouter();
  const tab = normalizePortfolioTab(params.tab);
  const symbol = String(params.symbol ?? '').trim().toUpperCase();

  useEffect(() => setAssistantSection('investing'), []);

  const setTab = (next: PortfolioTab) => router.setParams({ tab: next });
  // Stable reference: InsidersTab's auto-select-first-holding effect depends on this,
  // and a fresh function identity every render would re-run that effect needlessly.
  const selectSymbol = useCallback(
    (next: string) => router.setParams({ tab: 'insiders', symbol: next }),
    [router],
  );

  const assistantContext =
    tab === 'insiders'
      ? symbol
        ? `The user is reviewing insider activity for ${symbol}: reported insider transactions, Finnhub monthly MSPR sentiment, price movement, portfolio exposure, recent news, and AI interpretation. When the user says "this stock", "this insider", "these trades", or "this signal", they mean ${symbol}. Fetch current data with the available tools before drawing conclusions.`
        : 'The user is on the insider activity tab, choosing a portfolio holding or searching for a ticker. Help them understand insider transactions and Finnhub MSPR sentiment; fetch current data once they identify a symbol.'
      : ASSISTANT_CONTEXT[tab];
  const assistantContextLabel =
    tab === 'insiders' && symbol
      ? `${symbol} · Insider activity`
      : `Portfolio · ${PORTFOLIO_TAB_LABEL[tab]}`;

  return (
    <AppShell
      title={PORTFOLIO_TAB_TITLE[tab]}
      eyebrow="PORTFOLIO DETAIL"
      assistantSection="investing"
      assistantContext={assistantContext}
      assistantContextLabel={assistantContextLabel}>
      <View accessibilityRole="tablist" style={styles.tabRow}>
        {PORTFOLIO_TABS.map((option) => (
          <FilterChip
            key={option}
            label={PORTFOLIO_TAB_LABEL[option]}
            active={tab === option}
            onPress={() => setTab(option)}
          />
        ))}
      </View>

      {tab === 'holdings' ? <HoldingsTab /> : null}
      {tab === 'feed' ? <FeedTab /> : null}
      {tab === 'news' ? <NewsTab /> : null}
      {tab === 'insiders' ? <InsidersTab symbol={symbol} onSelectSymbol={selectSymbol} /> : null}
    </AppShell>
  );
}

const styles = StyleSheet.create({
  tabRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.md },
});
