import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import {
  ArrowLeft,
  BrainCircuit,
  BriefcaseBusiness,
  CalendarDays,
  ChevronRight,
  ExternalLink,
  RefreshCw,
} from 'lucide-react-native';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Linking,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { AppShell } from '@/components/AppShell';
import { MarketSearch } from '@/components/MarketSearch';
import { StockPriceChart } from '@/components/StockPriceChart';
import { DemoBanner, ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { setAssistantSection } from '@/lib/assistantSection';
import { money, number, percent, relativeTime, signedMoney } from '@/lib/format';
import { marketApi } from '@/lib/marketApi';
import type {
  EarningsResult,
  InsiderTransaction,
  MarketPeriod,
  MarketProviderStatus,
  MarketQuote,
} from '@/lib/marketTypes';
import { colors } from '@/theme/tokens';

const PERIODS: MarketPeriod[] = ['1D', '5D', '1M', '6M', '1Y', '5Y'];

export default function StockDetailScreen() {
  useEffect(() => setAssistantSection('investing'), []);
  const params = useLocalSearchParams<{ symbol: string }>();
  const symbol = String(params.symbol ?? '').toUpperCase();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const desktop = width >= 980;
  const showHeaderSearch = width >= 760;
  const [period, setPeriod] = useState<MarketPeriod>('1D');
  const chartContextRef = useRef(
    'The price chart has not loaded yet, so no chart bar or technical-indicator formula is selected.',
  );
  const getAssistantContext = useCallback(
    () =>
      `The user is researching ${symbol}. The screen includes its current quote, price history, earnings, related news, insider transactions and sentiment, and any portfolio position. When the user says "this stock", "this position", "this chart", "this formula", or asks why it is moving, they mean ${symbol}. The selected chart range is ${period}. ${chartContextRef.current} Use this chart state to explain the technical indicator the user is viewing, but fetch current market and portfolio facts with the available tools before answering.`,
    [period, symbol],
  );
  const detail = useQuery({
    queryKey: ['market-stock', symbol],
    queryFn: () => marketApi.stock(symbol),
    enabled: Boolean(symbol),
    staleTime: 60_000,
  });
  const history = useQuery({
    queryKey: ['market-history', symbol, period],
    queryFn: () => marketApi.history(symbol, period),
    enabled: Boolean(symbol),
    staleTime: period === '1D' ? 60_000 : 10 * 60_000,
  });
  const insiders = useQuery({
    queryKey: ['market-insiders', symbol],
    queryFn: () => marketApi.insiders(symbol),
    enabled: Boolean(symbol),
    staleTime: 5 * 60_000,
  });

  const refresh = async () => {
    await marketApi.refreshNews();
    await Promise.all([detail.refetch(), history.refetch(), insiders.refetch()]);
  };

  return (
    <AppShell
      assistantContext={getAssistantContext}
      assistantContextLabel={`${symbol} · Stock research`}
      eyebrow="STOCK RESEARCH"
      onRefresh={() => void refresh()}
      refreshing={detail.isRefetching || history.isRefetching || insiders.isRefetching}
      title={symbol || 'Stock'}
      headerAction={
        <View style={styles.headerActions}>
          {showHeaderSearch ? <MarketSearch compact initialValue="" /> : null}
          <Pressable
            accessibilityLabel="Refresh market data"
            onPress={() => void refresh()}
            style={styles.headerIcon}>
            <RefreshCw size={16} color={colors.inkMuted} />
          </Pressable>
        </View>
      }>
      <Pressable onPress={() => router.push('/holdings')} style={styles.backLink}>
        <ArrowLeft size={14} color={colors.tealDark} />
        <Text style={styles.backText}>All holdings</Text>
      </Pressable>

      {detail.isLoading ? <LoadingState label={`Loading ${symbol}`} /> : null}
      {detail.isError ? (
        <ErrorState message={detail.error.message} retry={() => detail.refetch()} />
      ) : null}

      {detail.data ? (
        <>
          {detail.data.is_demo ? (
            <DemoBanner message="Sample market data. Add Alpaca and Finnhub keys to enable current provider data." />
          ) : null}

          <View style={styles.quoteHero}>
            <View style={styles.identityRow}>
              <View style={styles.assetBadge}>
                <Text style={styles.assetBadgeText}>{detail.data.symbol.slice(0, 2)}</Text>
              </View>
              <View style={styles.identityCopy}>
                <Text style={styles.companyName}>{detail.data.name}</Text>
                <Text style={styles.listing}>
                  {[detail.data.exchange, detail.data.asset_type.toUpperCase(), detail.data.currency]
                    .filter(Boolean)
                    .join(' · ')}
                </Text>
              </View>
              <View style={styles.freshnessBadge}>
                <View
                  style={[
                    styles.freshnessDot,
                    detail.data.quote.freshness === 'demo' && styles.freshnessDotDemo,
                  ]}
                />
                <Text style={styles.freshnessText}>
                  {freshnessLabel(detail.data.quote.freshness)}
                </Text>
              </View>
            </View>
            <View style={styles.priceRow}>
              <Text style={styles.price}>{money(detail.data.quote.price)}</Text>
              <View>
                <Text
                  style={[
                    styles.priceChange,
                    detail.data.quote.change >= 0 ? styles.positive : styles.negative,
                  ]}>
                  {signedMoney(detail.data.quote.change)} ({percent(detail.data.quote.change_percent)})
                </Text>
                <Text style={styles.priceMeta}>
                  As of {relativeTime(detail.data.quote.timestamp)} · {detail.data.quote.source}
                </Text>
              </View>
            </View>
            <View style={styles.quoteMetrics}>
              <QuoteMetric label="OPEN" value={priceOrDash(detail.data.quote.open)} />
              <QuoteMetric label="DAY HIGH" value={priceOrDash(detail.data.quote.high)} />
              <QuoteMetric label="DAY LOW" value={priceOrDash(detail.data.quote.low)} />
              <QuoteMetric
                label="PREV CLOSE"
                value={priceOrDash(detail.data.quote.previous_close)}
              />
              <QuoteMetric
                label="BID / ASK"
                value={
                  detail.data.quote.bid != null &&
                  detail.data.quote.bid > 0 &&
                  detail.data.quote.ask != null &&
                  detail.data.quote.ask > 0
                    ? `${money(detail.data.quote.bid)} / ${money(detail.data.quote.ask)}`
                    : '—'
                }
              />
              <QuoteMetric
                label="VOLUME"
                value={
                  detail.data.quote.volume != null
                    ? number(detail.data.quote.volume, 0)
                    : '—'
                }
              />
            </View>
          </View>

          {!showHeaderSearch ? <MarketSearch compact initialValue="" /> : null}

          <View style={[styles.panel, styles.chartPanelSection]}>
            <SectionHeader
              title="Price history"
              caption={
                width >= 520 && history.data
                  ? `${history.data.interval === '1Min' ? '1-minute' : 'Daily'} bars · ${history.data.source}`
                  : undefined
              }
              action={
                <View style={styles.periodRow}>
                  {PERIODS.map((item) => (
                    <Pressable
                      key={item}
                      onPress={() => setPeriod(item)}
                      style={[
                        styles.periodButton,
                        period === item && styles.periodButtonActive,
                      ]}>
                      <Text
                        style={[
                          styles.periodText,
                          period === item && styles.periodTextActive,
                        ]}>
                        {item}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              }
            />
            {history.isLoading ? <LoadingState label="Loading price history" /> : null}
            {history.isError ? (
              <ErrorState message={history.error.message} retry={() => history.refetch()} />
            ) : null}
            {history.data ? (
              <View style={styles.chartBody}>
                <StockPriceChart
                  points={history.data.points}
                  sourceInterval={history.data.interval}
                  onContextChange={(value) => {
                    chartContextRef.current = value;
                  }}
                />
                <View style={styles.coverageNote}>
                  <Text style={styles.coverageText}>{history.data.coverage_note}</Text>
                  <Text style={styles.coverageText}>
                    Updated {relativeTime(history.data.last_updated)}
                  </Text>
                </View>
              </View>
            ) : null}
          </View>

          <View style={[styles.contentGrid, !desktop && styles.contentGridStacked]}>
            <View style={styles.mainColumn}>
              <View style={styles.panel}>
                <SectionHeader
                  title="Earnings"
                  caption="Reported results and the next scheduled estimate"
                />
                {detail.data.earnings.length ? (
                  <View>
                    <View style={styles.earningsHeader}>
                      <Text style={[styles.tableHeading, styles.dateColumn]}>DATE</Text>
                      <Text style={[styles.tableHeading, styles.numberColumn]}>EPS EST.</Text>
                      <Text style={[styles.tableHeading, styles.numberColumn]}>EPS ACT.</Text>
                      <Text style={[styles.tableHeading, styles.numberColumn]}>REVENUE</Text>
                    </View>
                    {detail.data.earnings.map((item) => (
                      <EarningsRow item={item} key={`${item.date}-${item.fiscal_quarter}`} />
                    ))}
                  </View>
                ) : (
                  <EmptyPanel text="No earnings records are available from the configured providers." />
                )}
              </View>

              <View style={styles.panel}>
                <SectionHeader
                  title="Related news & filings"
                  caption="Ticker-linked events from Posted’s normalized event store"
                />
                {detail.data.related_news.length ? (
                  detail.data.related_news.map((item) => (
                    <Pressable
                      key={item.id}
                      onPress={() =>
                        router.push({ pathname: '/event/[id]', params: { id: item.id } })
                      }
                      style={({ pressed }) => [
                        styles.newsRow,
                        pressed && styles.newsRowPressed,
                      ]}>
                      <View style={styles.newsBody}>
                        <View style={styles.newsMeta}>
                          <Text style={styles.newsType}>{item.event_type.replaceAll('_', ' ')}</Text>
                          <Text style={styles.newsTime}>{relativeTime(item.occurred_at)}</Text>
                        </View>
                        <Text style={styles.newsHeadline}>{item.headline}</Text>
                        <Text style={styles.newsSource}>{item.source_name}</Text>
                      </View>
                      <ChevronRight size={17} color={colors.inkFaint} />
                    </Pressable>
                  ))
                ) : (
                  <EmptyPanel text="No normalized portfolio events are linked to this ticker yet." />
                )}
              </View>

              <View style={styles.panel}>
                <SectionHeader
                  title="Insider activity"
                  caption="Transactions, monthly MSPR sentiment, and portfolio-aware interpretation"
                  action={
                    <Pressable
                      onPress={() =>
                        router.push({ pathname: '/insiders', params: { symbol } })
                      }
                      style={styles.insiderAnalysisLink}>
                      <BrainCircuit size={13} color={colors.tealDark} />
                      <Text style={styles.insiderAnalysisLinkText}>Full analysis</Text>
                    </Pressable>
                  }
                />
                {insiders.isLoading ? (
                  <LoadingState label="Interpreting insider activity" />
                ) : null}
                {insiders.isError ? (
                  <ErrorState message={insiders.error.message} retry={() => insiders.refetch()} />
                ) : null}
                {insiders.data ? (
                  <>
                    <View style={styles.insiderSnapshot}>
                      <InsiderMetric
                        label="LATEST MSPR"
                        value={signedMetric(insiders.data.summary.latest_mspr)}
                      />
                      <InsiderMetric
                        label="3-MONTH MSPR"
                        value={signedMetric(insiders.data.summary.three_month_average_mspr)}
                      />
                      <InsiderMetric
                        label="TREND"
                        value={insiders.data.summary.mspr_trend.toUpperCase()}
                      />
                    </View>
                    <View style={styles.insiderRead}>
                      <Text style={styles.insiderReadTitle}>
                        {insiders.data.interpretation.headline}
                      </Text>
                      <Text style={styles.insiderReadText}>
                        {insiders.data.interpretation.summary}
                      </Text>
                    </View>
                    {insiders.data.ai_insight ? (
                      <View style={styles.insiderAi}>
                        <View style={styles.insiderAiTitleRow}>
                          <BrainCircuit size={15} color={colors.tealDark} />
                          <Text style={styles.insiderAiTitle}>POSTED AI CONTEXT</Text>
                        </View>
                        <Text style={styles.insiderAiText}>{insiders.data.ai_insight}</Text>
                      </View>
                    ) : null}
                    {insiders.data.transactions.length ? (
                      insiders.data.transactions
                        .slice(0, 10)
                        .map((item) => <InsiderRow item={item} key={item.id} />)
                    ) : (
                      <EmptyPanel text="No recent insider transactions are available for this ticker." />
                    )}
                  </>
                ) : null}
              </View>
            </View>

            <View style={styles.sideColumn}>
              {detail.data.position ? (
                <View style={[styles.panel, styles.positionPanel]}>
                  <View style={styles.cardTitleRow}>
                    <View style={styles.cardIcon}>
                      <BriefcaseBusiness size={16} color={colors.tealDark} />
                    </View>
                    <View>
                      <Text style={styles.cardEyebrow}>YOUR POSITION</Text>
                      <Text style={styles.cardTitle}>
                        {number(detail.data.position.quantity, 4)} shares
                      </Text>
                    </View>
                  </View>
                  <Text style={styles.positionValue}>
                    {money(detail.data.position.market_value)}
                  </Text>
                  <Text
                    style={[
                      styles.positionGain,
                      detail.data.position.total_gain >= 0
                        ? styles.positive
                        : styles.negative,
                    ]}>
                    {signedMoney(detail.data.position.total_gain)} all-time ·{' '}
                    {percent(detail.data.position.total_gain_percent)}
                  </Text>
                  <View style={styles.cardMetrics}>
                    <SideMetric
                      label="Average cost"
                      value={
                        detail.data.position.average_price != null
                          ? money(detail.data.position.average_price)
                          : '—'
                      }
                    />
                    <SideMetric
                      label="Portfolio weight"
                      value={`${detail.data.position.portfolio_weight.toFixed(2)}%`}
                    />
                    <SideMetric
                      label="Across accounts"
                      value={String(detail.data.position.account_count)}
                    />
                  </View>
                </View>
              ) : null}

              <View style={styles.panel}>
                <SectionHeader title="Key statistics" />
                <View style={styles.statsGrid}>
                  <SideMetric
                    label="Market cap"
                    value={compactNumber(detail.data.company.market_cap)}
                  />
                  <SideMetric
                    label="P/E ratio"
                    value={decimalOrDash(detail.data.company.pe_ratio)}
                  />
                  <SideMetric
                    label="Dividend yield"
                    value={yieldOrDash(detail.data.company.dividend_yield)}
                  />
                  <SideMetric label="Beta" value={decimalOrDash(detail.data.company.beta)} />
                  <SideMetric
                    label="52-week high"
                    value={priceOrDash(detail.data.company.fifty_two_week_high)}
                  />
                  <SideMetric
                    label="52-week low"
                    value={priceOrDash(detail.data.company.fifty_two_week_low)}
                  />
                </View>
              </View>

              <View style={styles.panel}>
                <SectionHeader title="Company" />
                <View style={styles.companyBody}>
                  <View style={styles.companyTags}>
                    {detail.data.company.sector ? (
                      <Text style={styles.companyTag}>{detail.data.company.sector}</Text>
                    ) : null}
                    {detail.data.company.industry &&
                    detail.data.company.industry !== detail.data.company.sector ? (
                      <Text style={styles.companyTag}>{detail.data.company.industry}</Text>
                    ) : null}
                  </View>
                  <Text numberOfLines={8} style={styles.description}>
                    {detail.data.company.description ??
                      'A company description is not available from the configured free-tier providers.'}
                  </Text>
                  {detail.data.company.website ? (
                    <Pressable
                      onPress={() => void Linking.openURL(detail.data.company.website!)}
                      style={styles.websiteLink}>
                      <ExternalLink size={13} color={colors.tealDark} />
                      <Text style={styles.websiteText}>Company website</Text>
                    </Pressable>
                  ) : null}
                </View>
              </View>

              <View style={styles.panel}>
                <SectionHeader
                  title="Data coverage"
                  caption="What each free source contributes"
                />
                {detail.data.providers.map((provider) => (
                  <ProviderRow key={provider.name} provider={provider} />
                ))}
              </View>
            </View>
          </View>
          <Text style={styles.disclaimer}>{detail.data.disclaimer}</Text>
        </>
      ) : null}
    </AppShell>
  );
}

function QuoteMetric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.quoteMetric}>
      <Text style={styles.quoteMetricLabel}>{label}</Text>
      <Text style={styles.quoteMetricValue}>{value}</Text>
    </View>
  );
}

function SideMetric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.sideMetric}>
      <Text style={styles.sideMetricLabel}>{label}</Text>
      <Text style={styles.sideMetricValue}>{value}</Text>
    </View>
  );
}

function InsiderMetric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.insiderMetric}>
      <Text style={styles.insiderMetricLabel}>{label}</Text>
      <Text style={styles.insiderMetricValue}>{value}</Text>
    </View>
  );
}

function EarningsRow({ item }: { item: EarningsResult }) {
  return (
    <View style={styles.earningsRow}>
      <View style={styles.dateColumn}>
        <View style={styles.earningsDateRow}>
          <CalendarDays size={14} color={colors.inkFaint} />
          <View>
            <Text style={styles.earningsDate}>{formatDate(item.date)}</Text>
            <Text style={styles.earningsQuarter}>
              {[item.fiscal_quarter, timingLabel(item.timing)].filter(Boolean).join(' · ')}
            </Text>
          </View>
        </View>
      </View>
      <Text style={[styles.tableCell, styles.numberColumn]}>
        {item.eps_estimate != null ? `$${item.eps_estimate.toFixed(2)}` : '—'}
      </Text>
      <Text
        style={[
          styles.tableCellStrong,
          styles.numberColumn,
          item.eps_actual != null &&
            item.eps_estimate != null &&
            (item.eps_actual >= item.eps_estimate ? styles.positive : styles.negative),
        ]}>
        {item.eps_actual != null ? `$${item.eps_actual.toFixed(2)}` : 'Upcoming'}
      </Text>
      <Text style={[styles.tableCell, styles.numberColumn]}>
        {compactNumber(item.revenue_actual ?? item.revenue_estimate)}
      </Text>
    </View>
  );
}

function ProviderRow({ provider }: { provider: MarketProviderStatus }) {
  const active = provider.status === 'active';
  return (
    <View style={styles.providerRow}>
      <View style={[styles.providerDot, active && styles.providerDotActive]} />
      <View style={styles.providerCopy}>
        <View style={styles.providerTitleRow}>
          <Text style={styles.providerName}>{provider.name}</Text>
          <Text style={[styles.providerStatus, active && styles.providerStatusActive]}>
            {provider.status.toUpperCase()}
          </Text>
        </View>
        <Text style={styles.providerRole}>{provider.role}</Text>
        <Text style={styles.providerDetail}>{provider.detail}</Text>
      </View>
    </View>
  );
}

function InsiderRow({ item }: { item: InsiderTransaction }) {
  const change = item.shares_changed ?? 0;
  return (
    <View style={styles.insiderRow}>
      <View style={styles.insiderIdentity}>
        <Text style={styles.insiderName}>{item.name}</Text>
        <Text style={styles.insiderMeta}>
          {formatDate(item.transaction_date)} · {insiderAction(item.transaction_code)}
          {item.is_derivative ? ' · Derivative' : ''}
        </Text>
      </View>
      <View style={styles.insiderChange}>
        <Text
          style={[
            styles.insiderShares,
            change > 0 ? styles.insiderPositive : change < 0 ? styles.insiderNegative : null,
          ]}>
          {change > 0 ? '+' : ''}
          {number(change, 0)} shares
        </Text>
        <Text style={styles.insiderPrice}>
          {item.transaction_price != null ? `${money(item.transaction_price)} / share` : 'Price —'}
        </Text>
      </View>
    </View>
  );
}

function EmptyPanel({ text }: { text: string }) {
  return (
    <View style={styles.emptyPanel}>
      <Text style={styles.emptyPanelText}>{text}</Text>
    </View>
  );
}

function freshnessLabel(value: string) {
  if (value === 'real_time_iex') return 'REAL-TIME IEX';
  if (value === 'recent') return 'RECENT';
  if (value === 'demo') return 'DEMO DATA';
  if (value === 'snapshot') return 'PORTFOLIO SNAPSHOT';
  return 'DELAYED / CACHED';
}

function timingLabel(value: string | null) {
  if (value === 'bmo') return 'Before open';
  if (value === 'amc') return 'After close';
  if (value === 'dmh') return 'During market';
  return value;
}

function insiderAction(value: string) {
  const labels: Record<string, string> = {
    P: 'Purchase',
    S: 'Sale',
    A: 'Award',
    M: 'Option exercise',
    F: 'Tax withholding',
    G: 'Gift',
  };
  return labels[value.toUpperCase()] ?? `Transaction ${value}`;
}

function signedMetric(value: number | null) {
  if (value == null) return '—';
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`;
}

function priceOrDash(value: number | null) {
  return value != null ? money(value) : '—';
}

function decimalOrDash(value: number | null) {
  return value != null ? value.toFixed(2) : '—';
}

function yieldOrDash(value: number | null) {
  if (value == null) return '—';
  const normalized = value > 0 && value < 0.1 ? value * 100 : value;
  return `${normalized.toFixed(2)}%`;
}

function compactNumber(value: number | null) {
  if (value == null) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function formatDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const styles = StyleSheet.create({
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 9, zIndex: 30 },
  headerIcon: {
    width: 40,
    height: 40,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backLink: {
    alignSelf: 'flex-start',
    marginTop: -13,
    marginBottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  backText: { color: colors.tealDark, fontSize: 11, fontWeight: '700' },
  quoteHero: {
    borderRadius: 14,
    backgroundColor: colors.navy,
    padding: 22,
    marginBottom: 16,
  },
  identityRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  assetBadge: {
    width: 42,
    height: 42,
    borderRadius: 4,
    backgroundColor: colors.teal,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetBadgeText: { color: colors.white, fontSize: 13, fontWeight: '800' },
  identityCopy: { flex: 1, minWidth: 0 },
  companyName: { color: colors.white, fontSize: 17, fontWeight: '700' },
  listing: { color: '#8F9CAE', fontSize: 9, letterSpacing: 0.7, marginTop: 5 },
  freshnessBadge: {
    borderWidth: 1,
    borderColor: '#344258',
    paddingHorizontal: 9,
    height: 27,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  freshnessDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#32C98C' },
  freshnessDotDemo: { backgroundColor: '#75D4D1' },
  freshnessText: { color: '#B8C3D0', fontSize: 8, fontWeight: '800', letterSpacing: 0.6 },
  priceRow: {
    marginTop: 22,
    flexDirection: 'row',
    alignItems: 'flex-end',
    flexWrap: 'wrap',
    gap: 15,
  },
  price: {
    color: colors.white,
    fontSize: 42,
    lineHeight: 48,
    fontWeight: '700',
    letterSpacing: -1,
    fontVariant: ['tabular-nums'],
  },
  priceChange: { fontSize: 13, fontWeight: '800', fontVariant: ['tabular-nums'] },
  priceMeta: { color: '#8F9CAE', fontSize: 9, marginTop: 5 },
  positive: { color: '#46D39B' },
  negative: { color: '#FF7E8B' },
  quoteMetrics: {
    borderTopWidth: 1,
    borderTopColor: '#2D394C',
    marginTop: 21,
    paddingTop: 14,
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  quoteMetric: { minWidth: 125, flex: 1, marginBottom: 8 },
  quoteMetricLabel: {
    color: '#758297',
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  quoteMetricValue: {
    color: '#DCE2E9',
    fontSize: 11,
    fontWeight: '600',
    marginTop: 5,
    fontVariant: ['tabular-nums'],
  },
  contentGrid: { flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  contentGridStacked: { flexDirection: 'column' },
  mainColumn: { flex: 2, minWidth: 0, gap: 16 },
  sideColumn: { flex: 1, minWidth: 310, gap: 16 },
  panel: {
    width: '100%',
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  chartBody: { padding: 14 },
  chartPanelSection: { marginBottom: 16 },
  periodRow: { flexDirection: 'row', gap: 2 },
  periodButton: {
    height: 29,
    minWidth: 31,
    paddingHorizontal: 5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  periodButtonActive: { backgroundColor: colors.teal },
  periodText: { color: colors.inkMuted, fontSize: 9, fontWeight: '700' },
  periodTextActive: { color: colors.white },
  coverageNote: {
    minHeight: 34,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: 10,
    marginTop: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  coverageText: { color: colors.inkFaint, fontSize: 9, lineHeight: 13 },
  positionPanel: { padding: 18, borderTopWidth: 3, borderTopColor: colors.teal },
  cardTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  cardIcon: {
    width: 34,
    height: 34,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardEyebrow: { color: colors.inkFaint, fontSize: 8, fontWeight: '800', letterSpacing: 0.9 },
  cardTitle: { color: colors.ink, fontSize: 12, fontWeight: '700', marginTop: 3 },
  positionValue: {
    color: colors.ink,
    fontSize: 28,
    fontWeight: '700',
    marginTop: 20,
    fontVariant: ['tabular-nums'],
  },
  positionGain: { fontSize: 11, fontWeight: '700', marginTop: 6 },
  cardMetrics: {
    borderTopWidth: 1,
    borderTopColor: colors.line,
    marginTop: 16,
    paddingTop: 6,
  },
  sideMetric: {
    minHeight: 42,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
  },
  sideMetricLabel: { color: colors.inkMuted, fontSize: 10 },
  sideMetricValue: {
    color: colors.ink,
    fontSize: 11,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
    textAlign: 'right',
  },
  statsGrid: { paddingHorizontal: 16, paddingVertical: 7 },
  companyBody: { padding: 16 },
  companyTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  companyTag: {
    color: colors.tealDark,
    fontSize: 9,
    fontWeight: '700',
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  description: { color: colors.inkMuted, fontSize: 11, lineHeight: 17, marginTop: 13 },
  websiteLink: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 14 },
  websiteText: { color: colors.tealDark, fontSize: 10, fontWeight: '700' },
  earningsHeader: {
    minHeight: 35,
    paddingHorizontal: 16,
    backgroundColor: colors.surfaceMuted,
    flexDirection: 'row',
    alignItems: 'center',
  },
  tableHeading: { color: colors.inkMuted, fontSize: 8, fontWeight: '800', letterSpacing: 0.6 },
  dateColumn: { flex: 1.7, minWidth: 150 },
  numberColumn: { flex: 1, textAlign: 'right', fontVariant: ['tabular-nums'] },
  earningsRow: {
    minHeight: 66,
    paddingHorizontal: 16,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
  },
  earningsDateRow: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  earningsDate: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  earningsQuarter: { color: colors.inkFaint, fontSize: 9, marginTop: 3 },
  tableCell: { color: colors.inkMuted, fontSize: 10 },
  tableCellStrong: { color: colors.ink, fontSize: 10, fontWeight: '700' },
  newsRow: {
    minHeight: 96,
    paddingHorizontal: 16,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  newsRowPressed: { backgroundColor: colors.tealSoft },
  newsBody: { flex: 1, minWidth: 0, paddingVertical: 13 },
  newsMeta: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  newsType: {
    color: colors.tealDark,
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
  newsTime: { color: colors.inkFaint, fontSize: 9 },
  newsHeadline: { color: colors.ink, fontSize: 12, fontWeight: '700', lineHeight: 17, marginTop: 7 },
  newsSource: { color: colors.inkMuted, fontSize: 9, marginTop: 6 },
  insiderAnalysisLink: {
    minHeight: 32,
    borderWidth: 1,
    borderColor: '#A6D9D9',
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  insiderAnalysisLinkText: { color: colors.tealDark, fontSize: 9, fontWeight: '800' },
  insiderSnapshot: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  insiderMetric: {
    flex: 1,
    minWidth: 130,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRightWidth: 1,
    borderRightColor: colors.line,
  },
  insiderMetricLabel: {
    color: colors.inkFaint,
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.7,
  },
  insiderMetricValue: {
    color: colors.ink,
    fontSize: 16,
    fontWeight: '700',
    marginTop: 6,
    fontVariant: ['tabular-nums'],
  },
  insiderRead: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  insiderReadTitle: { color: colors.ink, fontSize: 12, fontWeight: '800' },
  insiderReadText: { color: colors.inkMuted, fontSize: 10, lineHeight: 16, marginTop: 6 },
  insiderAi: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#A6D9D9',
    backgroundColor: colors.tealSoft,
  },
  insiderAiTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  insiderAiTitle: { color: colors.tealDark, fontSize: 8, fontWeight: '900', letterSpacing: 0.9 },
  insiderAiText: { color: colors.inkMuted, fontSize: 10, lineHeight: 17, marginTop: 9 },
  insiderRow: {
    minHeight: 68,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 14,
  },
  insiderIdentity: { flex: 1, minWidth: 0 },
  insiderName: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  insiderMeta: { color: colors.inkFaint, fontSize: 9, marginTop: 4 },
  insiderChange: { alignItems: 'flex-end' },
  insiderShares: {
    color: colors.ink,
    fontSize: 10,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  insiderPositive: { color: colors.positive },
  insiderNegative: { color: colors.negative },
  insiderPrice: { color: colors.inkFaint, fontSize: 9, marginTop: 4 },
  providerRow: {
    padding: 14,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    flexDirection: 'row',
    gap: 10,
  },
  providerDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: colors.lineStrong,
    marginTop: 4,
  },
  providerDotActive: { backgroundColor: colors.positive },
  providerCopy: { flex: 1 },
  providerTitleRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  providerName: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  providerStatus: { color: colors.inkFaint, fontSize: 7, fontWeight: '800', letterSpacing: 0.5 },
  providerStatusActive: { color: colors.positive },
  providerRole: { color: colors.inkMuted, fontSize: 9, marginTop: 4 },
  providerDetail: { color: colors.inkFaint, fontSize: 9, lineHeight: 13, marginTop: 5 },
  emptyPanel: { minHeight: 96, alignItems: 'center', justifyContent: 'center', padding: 18 },
  emptyPanelText: { color: colors.inkMuted, fontSize: 11, textAlign: 'center' },
  disclaimer: { color: colors.inkFaint, fontSize: 9, lineHeight: 14, marginTop: 14 },
});
