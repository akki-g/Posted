// The four "Portfolio detail" tabs. Holdings / Feed / News / Insider activity
// used to be four separate routes; they now collapse into one tabbed
// destination at /portfolio?tab=... , mirroring how index.tsx collapsed
// money/invest into one lens-tabbed spine. This module owns the tab set so the
// container, the redirect shims, and any deep link agree on valid values.

export const PORTFOLIO_TABS = ['holdings', 'feed', 'news', 'insiders'] as const;

export type PortfolioTab = (typeof PORTFOLIO_TABS)[number];

export const PORTFOLIO_TAB_LABEL: Record<PortfolioTab, string> = {
  holdings: 'Holdings',
  feed: 'Feed',
  news: 'News',
  insiders: 'Insiders',
};

/** The full page title AppShell shows for each tab (kept from the old routes). */
export const PORTFOLIO_TAB_TITLE: Record<PortfolioTab, string> = {
  holdings: 'Holdings',
  feed: 'Impact feed',
  news: 'News stories',
  insiders: 'Insider activity',
};

/** Normalizes the `?tab=` param to a known tab, defaulting to Holdings. */
export function normalizePortfolioTab(value: string | null | undefined): PortfolioTab {
  return (PORTFOLIO_TABS as readonly string[]).includes(value ?? '')
    ? (value as PortfolioTab)
    : 'holdings';
}
