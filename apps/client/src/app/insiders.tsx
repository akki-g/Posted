import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import {
  ArrowRight,
  BrainCircuit,
  BriefcaseBusiness,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  UserRoundSearch,
} from 'lucide-react-native';
import { useEffect, useMemo, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { AppShell } from '@/components/AppShell';
import { MarketSearch } from '@/components/MarketSearch';
import { DemoBanner, ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { setAssistantSection } from '@/lib/assistantSection';
import { useChartScrub } from '@/lib/chartScrub';
import { money, number, percent, relativeTime, signedMoney } from '@/lib/format';
import { marketApi } from '@/lib/marketApi';
import type {
  InsiderActivitySummary,
  InsiderSentimentPoint,
  InsiderTransaction,
  PortfolioInsiderWatchItem,
} from '@/lib/marketTypes';
import { cardShadow, colors, radius } from '@/theme/tokens';

export default function InsidersScreen() {
  const params = useLocalSearchParams<{ symbol?: string }>();
  const symbol = String(params.symbol ?? '').trim().toUpperCase();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const desktop = width >= 980;
  const [sentimentInspection, setSentimentInspection] =
    useState<InsiderSentimentPoint | null>(null);
  const watch = useQuery({
    queryKey: ['portfolio-insiders'],
    queryFn: () => marketApi.portfolioInsiders(),
    staleTime: 5 * 60_000,
  });
  const analysis = useQuery({
    queryKey: ['market-insiders', symbol],
    queryFn: () => marketApi.insiders(symbol),
    enabled: Boolean(symbol),
    staleTime: 5 * 60_000,
  });

  useEffect(() => setAssistantSection('investing'), []);

  useEffect(() => {
    const first = watch.data?.items[0]?.symbol;
    if (!symbol && first) {
      router.replace({ pathname: '/insiders', params: { symbol: first } });
    }
  }, [router, symbol, watch.data?.items]);

  const refresh = async () => {
    await Promise.all([watch.refetch(), symbol ? analysis.refetch() : Promise.resolve()]);
  };

  return (
    <AppShell
      assistantContext={
        symbol
          ? `The user is reviewing insider activity for ${symbol}. The screen contains reported insider transactions, Finnhub monthly MSPR sentiment, price movement, portfolio exposure, recent news, and AI interpretation. ${
              sentimentInspection
                ? `The inspected sentiment bar is ${monthLabel(sentimentInspection)} ${sentimentInspection.year}: exact MSPR ${sentimentInspection.mspr.toFixed(1)} and monthly share change ${number(sentimentInspection.change, 0)}.`
                : 'No monthly sentiment bar is currently available.'
            } When the user says "this stock", "this insider", "these trades", "this bar", or "this signal", they mean ${symbol} and the analysis visible on this screen. Fetch current data with the available tools before drawing conclusions.`
          : 'The user is on the insider activity tracker and is choosing a portfolio holding or searching for a ticker. Help them understand insider transactions and Finnhub MSPR sentiment; fetch current data after they identify a symbol.'
      }
      assistantContextLabel={symbol ? `${symbol} · Insider activity` : 'Insider activity'}
      eyebrow="INVESTING"
      onRefresh={() => void refresh()}
      refreshing={watch.isRefetching || analysis.isRefetching}
      title="Insider activity"
      headerAction={
        <View style={styles.headerActions}>
          {width >= 720 ? (
            <MarketSearch compact destination="insiders" initialValue={symbol} />
          ) : null}
          <Pressable
            accessibilityLabel="Refresh insider data"
            onPress={() => void refresh()}
            style={styles.headerIcon}>
            <RefreshCw size={16} color={colors.inkMuted} />
          </Pressable>
        </View>
      }>
      {width < 720 ? (
        <View style={styles.mobileSearch}>
          <MarketSearch compact destination="insiders" initialValue={symbol} />
        </View>
      ) : null}

      <View style={styles.educationStrip}>
        <View style={styles.educationIcon}>
          <UserRoundSearch size={19} color={colors.tealDark} />
        </View>
        <View style={styles.educationCopy}>
          <Text style={styles.educationTitle}>Track reported insider conviction</Text>
          <Text style={styles.educationText}>
            Open-market purchases and sales are separated from grants, gifts, withholding, and
            option exercises. MSPR summarizes monthly insider buying and selling from −100 to +100.
          </Text>
        </View>
      </View>

      <View style={styles.panel}>
        <SectionHeader
          title="Your holdings"
          caption="Monthly Finnhub sentiment across portfolio equities"
        />
        {watch.isLoading ? <LoadingState label="Loading portfolio insider signals" /> : null}
        {watch.isError ? (
          <ErrorState message={watch.error.message} retry={() => watch.refetch()} />
        ) : null}
        {watch.data?.items.length ? (
          <ScrollView
            contentContainerStyle={styles.watchList}
            horizontal
            showsHorizontalScrollIndicator={false}>
            {watch.data.items.map((item) => (
              <WatchCard
                active={item.symbol === symbol}
                item={item}
                key={item.symbol}
                onPress={() =>
                  router.push({ pathname: '/insiders', params: { symbol: item.symbol } })
                }
              />
            ))}
          </ScrollView>
        ) : !watch.isLoading && !watch.isError ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No equity holdings to track yet</Text>
            <Text style={styles.emptyText}>
              Search any US ticker above, or connect a brokerage account to populate this watchlist.
            </Text>
          </View>
        ) : null}
      </View>

      {!symbol ? (
        <View style={styles.emptyAnalysis}>
          <Sparkles size={25} color={colors.teal} />
          <Text style={styles.emptyTitle}>Select or search a ticker</Text>
          <Text style={styles.emptyText}>
            Posted will combine transactions, monthly sentiment, price movement, portfolio exposure,
            and recent news into one grounded interpretation.
          </Text>
        </View>
      ) : null}

      {analysis.isLoading ? <LoadingState label={`Analyzing ${symbol} insider activity`} /> : null}
      {analysis.isError ? (
        <ErrorState message={analysis.error.message} retry={() => analysis.refetch()} />
      ) : null}

      {analysis.data ? (
        <>
          {analysis.data.is_demo ? (
            <DemoBanner message="Sample insider filings and sentiment. Configure Finnhub for current reported activity." />
          ) : null}

          <View style={styles.hero}>
            <View style={styles.heroTop}>
              <View style={styles.assetBadge}>
                <Text style={styles.assetBadgeText}>{analysis.data.symbol.slice(0, 2)}</Text>
              </View>
              <View style={styles.heroIdentity}>
                <Text style={styles.heroName}>{analysis.data.name}</Text>
                <Text style={styles.heroTicker}>
                  {analysis.data.symbol} · Updated {relativeTime(analysis.data.updated_at)}
                </Text>
              </View>
              <SignalPill signal={analysis.data.summary.signal} />
            </View>
            <View style={styles.heroMetrics}>
              <View>
                <Text style={styles.heroPrice}>{money(analysis.data.quote.price)}</Text>
                <Text
                  style={[
                    styles.heroMove,
                    analysis.data.quote.change >= 0 ? styles.positive : styles.negative,
                  ]}>
                  {signedMoney(analysis.data.quote.change)} today ·{' '}
                  {percent(analysis.data.quote.change_percent)}
                </Text>
              </View>
              <Pressable
                onPress={() =>
                  router.push({
                    pathname: '/stock/[symbol]',
                    params: { symbol: analysis.data.symbol },
                  })
                }
                style={styles.stockLink}>
                <Text style={styles.stockLinkText}>Full stock research</Text>
                <ArrowRight size={14} color={colors.tealDark} />
              </Pressable>
            </View>
          </View>

          <SummaryGrid
            oneMonthChange={analysis.data.one_month_price_change_percent}
            summary={analysis.data.summary}
          />

          <View style={[styles.contentGrid, !desktop && styles.contentGridStacked]}>
            <View style={styles.mainColumn}>
              <View style={[styles.panel, styles.aiPanel]}>
                <View style={styles.aiHeader}>
                  <View style={styles.aiIcon}>
                    <BrainCircuit size={19} color={colors.tealDark} />
                  </View>
                  <View style={styles.aiHeading}>
                    <Text style={styles.aiEyebrow}>POSTED AI ANALYSIS</Text>
                    <Text style={styles.aiTitle}>What this activity means in context</Text>
                  </View>
                  <Sparkles size={17} color={colors.teal} />
                </View>
                {analysis.data.ai_insight ? (
                  <AiNarrative text={analysis.data.ai_insight} />
                ) : (
                  <View style={styles.aiUnavailable}>
                    <Text style={styles.aiUnavailableTitle}>
                      {analysis.data.ai_available
                        ? 'AI analysis is temporarily unavailable'
                        : 'AI analysis is not configured'}
                    </Text>
                    <Text style={styles.aiUnavailableText}>
                      The evidence-based interpretation below remains available and uses the same
                      transaction and MSPR inputs.
                    </Text>
                  </View>
                )}
              </View>

              <View style={styles.panel}>
                <SectionHeader
                  title="Monthly insider sentiment"
                  caption="Finnhub MSPR; positive values indicate net accumulation"
                />
                <SentimentChart
                  points={analysis.data.sentiment}
                  onSelectionChange={setSentimentInspection}
                />
              </View>

              <View style={styles.panel}>
                <SectionHeader
                  title="Transaction ledger"
                  caption="Most recent reported filings; directional trades are labeled separately"
                />
                {analysis.data.transactions.length ? (
                  analysis.data.transactions
                    .slice(0, 20)
                    .map((item) => <TransactionRow item={item} key={item.id} />)
                ) : (
                  <View style={styles.emptyState}>
                    <Text style={styles.emptyText}>
                      No recent insider transaction rows were returned for this ticker.
                    </Text>
                  </View>
                )}
              </View>
            </View>

            <View style={styles.sideColumn}>
              <View style={styles.panel}>
                <SectionHeader title="Evidence-based read" />
                <View style={styles.interpretationBody}>
                  <Text style={styles.interpretationHeadline}>
                    {analysis.data.interpretation.headline}
                  </Text>
                  <Text style={styles.interpretationSummary}>
                    {analysis.data.interpretation.summary}
                  </Text>
                  {analysis.data.interpretation.factors.map((factor) => (
                    <View style={styles.factorRow} key={factor}>
                      <View style={styles.factorDot} />
                      <Text style={styles.factorText}>{factor}</Text>
                    </View>
                  ))}
                </View>
              </View>

              {analysis.data.position ? (
                <View style={[styles.panel, styles.positionPanel]}>
                  <View style={styles.positionHeader}>
                    <BriefcaseBusiness size={17} color={colors.tealDark} />
                    <Text style={styles.positionEyebrow}>YOUR EXPOSURE</Text>
                  </View>
                  <Text style={styles.positionValue}>
                    {money(analysis.data.position.market_value)}
                  </Text>
                  <Text style={styles.positionMeta}>
                    {analysis.data.position.portfolio_weight.toFixed(2)}% of portfolio ·{' '}
                    {number(analysis.data.position.quantity, 4)} shares
                  </Text>
                  <Text
                    style={[
                      styles.positionReturn,
                      analysis.data.position.total_gain >= 0
                        ? styles.positive
                        : styles.negative,
                    ]}>
                    {signedMoney(analysis.data.position.total_gain)} all-time ·{' '}
                    {percent(analysis.data.position.total_gain_percent)}
                  </Text>
                </View>
              ) : null}

              <View style={styles.panel}>
                <SectionHeader title="Interpretation limits" />
                <View style={styles.caveatBody}>
                  {analysis.data.interpretation.caveats.map((caveat) => (
                    <View style={styles.caveatRow} key={caveat}>
                      <ShieldAlert size={14} color={colors.warning} />
                      <Text style={styles.caveatText}>{caveat}</Text>
                    </View>
                  ))}
                </View>
              </View>

              <View style={styles.panel}>
                <SectionHeader
                  title="Recent context"
                  caption="Ticker-linked events from Posted"
                />
                {analysis.data.recent_news.length ? (
                  analysis.data.recent_news.map((item) => (
                    <Pressable
                      key={item.id}
                      onPress={() =>
                        router.push({ pathname: '/event/[id]', params: { id: item.id } })
                      }
                      style={styles.newsRow}>
                      <View style={styles.newsCopy}>
                        <Text style={styles.newsHeadline}>{item.headline}</Text>
                        <Text style={styles.newsMeta}>
                          {item.source_name} · {relativeTime(item.occurred_at)}
                        </Text>
                      </View>
                      <ArrowRight size={13} color={colors.inkFaint} />
                    </Pressable>
                  ))
                ) : (
                  <View style={styles.emptyState}>
                    <Text style={styles.emptyText}>
                      No normalized portfolio news is linked to this ticker yet.
                    </Text>
                  </View>
                )}
              </View>
            </View>
          </View>

          <Text style={styles.disclaimer}>{analysis.data.disclaimer}</Text>
        </>
      ) : null}
    </AppShell>
  );
}

function WatchCard({
  item,
  active,
  onPress,
}: {
  item: PortfolioInsiderWatchItem;
  active: boolean;
  onPress: () => void;
}) {
  const mspr = item.three_month_average_mspr;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.watchCard,
        active && styles.watchCardActive,
        pressed && styles.watchCardPressed,
      ]}>
      <View style={styles.watchTop}>
        <Text style={[styles.watchSymbol, active && styles.watchTextActive]}>{item.symbol}</Text>
        <TrendIcon trend={item.mspr_trend} />
      </View>
      <Text numberOfLines={1} style={[styles.watchName, active && styles.watchMutedActive]}>
        {item.name}
      </Text>
      <Text style={[styles.watchMspr, active && styles.watchTextActive]}>
        {mspr == null ? '—' : `${mspr >= 0 ? '+' : ''}${mspr.toFixed(1)}`}
      </Text>
      <Text style={[styles.watchCaption, active && styles.watchMutedActive]}>
        3-month MSPR · {item.portfolio_weight.toFixed(1)}% weight
      </Text>
    </Pressable>
  );
}

function SummaryGrid({
  summary,
  oneMonthChange,
}: {
  summary: InsiderActivitySummary;
  oneMonthChange: number | null;
}) {
  return (
    <View style={styles.summaryGrid}>
      <SummaryMetric
        label="LATEST MSPR"
        tone={toneForValue(summary.latest_mspr)}
        value={signedNumber(summary.latest_mspr)}
        caption={`${summary.mspr_trend} multi-month trend`}
      />
      <SummaryMetric
        label="3-MONTH MSPR"
        tone={toneForValue(summary.three_month_average_mspr)}
        value={signedNumber(summary.three_month_average_mspr)}
        caption={`${summary.confidence} signal confidence`}
      />
      <SummaryMetric
        label="NET INSIDER SHARES"
        tone={toneForValue(summary.three_month_net_shares)}
        value={signedCompact(summary.three_month_net_shares)}
        caption="Last three reported months"
      />
      <SummaryMetric
        label="1-MONTH PRICE MOVE"
        tone={toneForValue(oneMonthChange)}
        value={oneMonthChange == null ? '—' : percent(oneMonthChange)}
        caption="Context, not attributed causation"
      />
    </View>
  );
}

function SummaryMetric({
  label,
  value,
  caption,
  tone,
}: {
  label: string;
  value: string;
  caption: string;
  tone: 'positive' | 'negative' | 'neutral';
}) {
  return (
    <View style={styles.summaryMetric}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text
        style={[
          styles.summaryValue,
          tone === 'positive' ? styles.positive : tone === 'negative' ? styles.negative : null,
        ]}>
        {value}
      </Text>
      <Text style={styles.summaryCaption}>{caption}</Text>
    </View>
  );
}

function SentimentChart({
  points,
  onSelectionChange,
}: {
  points: InsiderSentimentPoint[];
  onSelectionChange?: (point: InsiderSentimentPoint | null) => void;
}) {
  const visible = useMemo(() => points.slice(-12), [points]);
  const scrub = useChartScrub(visible.length, 'bar');
  const selectedIndex = scrub.selectedIndex;
  const selectedPoint = visible[selectedIndex];

  useEffect(() => {
    onSelectionChange?.(selectedPoint ?? null);
  }, [onSelectionChange, selectedPoint]);

  if (!points.length) {
    return (
      <View style={styles.emptyState}>
        <Text style={styles.emptyText}>No monthly MSPR history is available.</Text>
      </View>
    );
  }
  return (
    <View style={styles.sentimentChartRoot}>
      <View style={styles.sentimentReadout}>
        <View>
          <Text style={styles.sentimentReadoutDate}>
            {monthLabel(selectedPoint)} {selectedPoint.year}
          </Text>
          <Text style={styles.sentimentReadoutHint}>MOVE OR DRAG ACROSS MONTHS</Text>
        </View>
        <View style={styles.sentimentReadoutValues}>
          <View>
            <Text style={styles.sentimentReadoutLabel}>EXACT MSPR</Text>
            <Text
              style={[
                styles.sentimentReadoutValue,
                selectedPoint.mspr >= 0 ? styles.positive : styles.negative,
              ]}>
              {selectedPoint.mspr >= 0 ? '+' : ''}
              {selectedPoint.mspr.toFixed(1)}
            </Text>
          </View>
          <View>
            <Text style={styles.sentimentReadoutLabel}>SHARE CHANGE</Text>
            <Text style={styles.sentimentReadoutShares}>
              {selectedPoint.change >= 0 ? '+' : ''}
              {number(selectedPoint.change, 0)}
            </Text>
          </View>
        </View>
      </View>
      <View style={styles.chartWrap}>
        <View style={styles.chartScale}>
          <Text style={styles.scaleText}>+100</Text>
          <Text style={styles.scaleText}>0</Text>
          <Text style={styles.scaleText}>−100</Text>
        </View>
        <View onLayout={scrub.onLayout} style={styles.chartPlot}>
          <View style={[styles.guideLine, styles.guideTop]} />
          <View style={[styles.guideLine, styles.guideMiddle]} />
          <View style={[styles.guideLine, styles.guideBottom]} />
          {visible.map((point, index) => {
            const height = Math.max(2, Math.abs(point.mspr) * 0.58);
            const positive = point.mspr >= 0;
            return (
              <View
                style={[styles.barColumn, index === selectedIndex && styles.barColumnActive]}
                key={`${point.year}-${point.month}`}>
                <View style={styles.barArea}>
                  <View
                    style={[
                      styles.sentimentBar,
                      positive ? styles.positiveBar : styles.negativeBar,
                      {
                        height,
                        top: positive ? 60 - height : 60,
                      },
                    ]}
                  />
                </View>
                <Text style={styles.barValue}>{point.mspr.toFixed(0)}</Text>
                <Text style={styles.barLabel}>{monthLabel(point)}</Text>
              </View>
            );
          })}
          <View
            {...scrub.panHandlers}
            accessible
            accessibilityLabel={`Interactive MSPR chart. Selected ${monthLabel(selectedPoint)} ${selectedPoint.year}, MSPR ${selectedPoint.mspr.toFixed(1)}`}
            accessibilityRole="adjustable"
            accessibilityValue={scrub.accessibilityValue}
            onAccessibilityAction={scrub.onAccessibilityAction}
            accessibilityActions={[
              { name: 'increment', label: 'Next month' },
              { name: 'decrement', label: 'Previous month' },
            ]}
            onPointerDown={scrub.onPointerDown}
            onPointerMove={scrub.onPointerMove}
            style={styles.sentimentTrackingLayer}
          />
        </View>
      </View>
    </View>
  );
}

function TransactionRow({ item }: { item: InsiderTransaction }) {
  const action = insiderAction(item.transaction_code);
  const directional = item.transaction_code.toUpperCase() === 'P' ||
    item.transaction_code.toUpperCase() === 'S';
  const change = item.shares_changed ?? 0;
  return (
    <View style={styles.transactionRow}>
      <View style={styles.transactionIdentity}>
        <View style={styles.transactionTitleRow}>
          <Text style={styles.transactionName}>{item.name}</Text>
          <View
            style={[
              styles.actionPill,
              directional ? styles.directionalPill : styles.administrativePill,
            ]}>
            <Text
              style={[
                styles.actionPillText,
                directional ? styles.directionalText : styles.administrativeText,
              ]}>
              {action.toUpperCase()}
            </Text>
          </View>
        </View>
        <Text style={styles.transactionMeta}>
          Traded {formatDate(item.transaction_date)} · Filed {formatDate(item.filing_date)}
          {item.is_derivative ? ' · Derivative security' : ''}
        </Text>
      </View>
      <View style={styles.transactionNumbers}>
        <Text
          style={[
            styles.transactionShares,
            change > 0 ? styles.positive : change < 0 ? styles.negative : null,
          ]}>
          {change > 0 ? '+' : ''}
          {number(change, 0)} shares
        </Text>
        <Text style={styles.transactionPrice}>
          {item.transaction_price != null ? `${money(item.transaction_price)} / share` : 'Price —'}
        </Text>
      </View>
    </View>
  );
}

function AiNarrative({ text }: { text: string }) {
  const paragraphs = text
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
  return (
    <View style={styles.aiBody}>
      {paragraphs.map((paragraph, index) => {
        const separator = paragraph.indexOf(':');
        const label = separator > 0 ? paragraph.slice(0, separator + 1) : null;
        const copy = separator > 0 ? paragraph.slice(separator + 1).trim() : paragraph;
        return (
          <Text style={styles.aiParagraph} key={`${index}-${label ?? copy.slice(0, 20)}`}>
            {label ? <Text style={styles.aiParagraphLabel}>{label} </Text> : null}
            {copy}
          </Text>
        );
      })}
    </View>
  );
}

function SignalPill({ signal }: { signal: string }) {
  const lower = signal.toLowerCase();
  const positive = lower.includes('accumulation');
  const negative = lower.includes('distribution');
  return (
    <View
      style={[
        styles.signalPill,
        positive
          ? styles.signalPositive
          : negative
            ? styles.signalNegative
            : styles.signalNeutral,
      ]}>
      <Text
        style={[
          styles.signalText,
          positive
            ? styles.signalPositiveText
            : negative
              ? styles.signalNegativeText
              : styles.signalNeutralText,
        ]}>
        {signal.toUpperCase()}
      </Text>
    </View>
  );
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'improving') return <TrendingUp size={14} color={colors.positive} />;
  if (trend === 'weakening') return <TrendingDown size={14} color={colors.negative} />;
  return <View style={styles.trendNeutral} />;
}

function toneForValue(value: number | null): 'positive' | 'negative' | 'neutral' {
  if (value == null || Math.abs(value) < 0.01) return 'neutral';
  return value > 0 ? 'positive' : 'negative';
}

function signedNumber(value: number | null) {
  if (value == null) return '—';
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}`;
}

function signedCompact(value: number | null) {
  if (value == null) return '—';
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
    signDisplay: 'always',
  }).format(value);
}

function monthLabel(point: InsiderSentimentPoint) {
  return new Date(point.year, point.month - 1, 1)
    .toLocaleDateString('en-US', { month: 'short' })
    .slice(0, 3);
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
  return labels[value.toUpperCase()] ?? `Code ${value}`;
}

function formatDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

const styles = StyleSheet.create({
  headerActions: {
    position: 'relative',
    zIndex: 1100,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  headerIcon: {
    width: 40,
    height: 40,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  mobileSearch: {
    position: 'relative',
    zIndex: 1100,
    marginBottom: 14,
    overflow: 'visible',
  },
  educationStrip: {
    position: 'relative',
    zIndex: 0,
    borderWidth: 1,
    borderColor: '#A6D9D9',
    backgroundColor: colors.tealSoft,
    padding: 15,
    marginBottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  educationIcon: {
    width: 38,
    height: 38,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  educationCopy: { flex: 1 },
  educationTitle: { color: colors.tealDark, fontSize: 12, fontWeight: '800' },
  educationText: { color: colors.tealDark, fontSize: 10, lineHeight: 15, marginTop: 3 },
  panel: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    marginBottom: 16,
    borderRadius: radius.lg,
    overflow: 'hidden',
    ...cardShadow,
  },
  watchList: { padding: 14, gap: 10 },
  watchCard: {
    width: 184,
    minHeight: 126,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    padding: 13,
  },
  watchCardActive: { borderColor: colors.teal, backgroundColor: colors.navy },
  watchCardPressed: { opacity: 0.82 },
  watchTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  watchSymbol: { color: colors.ink, fontSize: 12, fontWeight: '800' },
  watchTextActive: { color: colors.white },
  watchName: { color: colors.inkMuted, fontSize: 9, marginTop: 4 },
  watchMutedActive: { color: '#AEB8C5' },
  watchMspr: {
    color: colors.ink,
    fontSize: 23,
    fontWeight: '700',
    marginTop: 14,
    fontVariant: ['tabular-nums'],
  },
  watchCaption: { color: colors.inkFaint, fontSize: 8, marginTop: 3 },
  trendNeutral: { width: 12, height: 2, backgroundColor: colors.inkFaint },
  emptyState: { padding: 18 },
  emptyAnalysis: {
    minHeight: 230,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 30,
  },
  emptyTitle: { color: colors.ink, fontSize: 14, fontWeight: '700', marginTop: 9 },
  emptyText: {
    maxWidth: 570,
    color: colors.inkMuted,
    fontSize: 11,
    lineHeight: 17,
    marginTop: 5,
  },
  hero: { backgroundColor: colors.navy, borderRadius: radius.lg, padding: 22, marginBottom: 14 },
  heroTop: { flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  assetBadge: {
    width: 42,
    height: 42,
    backgroundColor: colors.teal,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetBadgeText: { color: colors.white, fontSize: 13, fontWeight: '800' },
  heroIdentity: { flex: 1, minWidth: 180 },
  heroName: { color: colors.white, fontSize: 17, fontWeight: '700' },
  heroTicker: { color: '#8F9CAE', fontSize: 9, letterSpacing: 0.6, marginTop: 5 },
  signalPill: { paddingHorizontal: 9, paddingVertical: 7, borderWidth: 1 },
  signalPositive: { borderColor: '#3B8960', backgroundColor: '#163B2B' },
  signalNegative: { borderColor: '#A95660', backgroundColor: '#44252D' },
  signalNeutral: { borderColor: '#526176', backgroundColor: colors.navyRaised },
  signalText: { fontSize: 8, fontWeight: '800', letterSpacing: 0.6 },
  signalPositiveText: { color: '#8CE1B1' },
  signalNegativeText: { color: '#F1A0A9' },
  signalNeutralText: { color: '#B8C1CE' },
  heroMetrics: {
    marginTop: 22,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: 16,
    flexWrap: 'wrap',
  },
  heroPrice: { color: colors.white, fontSize: 27, fontWeight: '700' },
  heroMove: { fontSize: 11, fontWeight: '700', marginTop: 5 },
  stockLink: {
    backgroundColor: colors.surface,
    paddingHorizontal: 13,
    height: 38,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  stockLinkText: { color: colors.tealDark, fontSize: 10, fontWeight: '800' },
  summaryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 16,
  },
  summaryMetric: {
    flexGrow: 1,
    flexBasis: 190,
    minHeight: 104,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    padding: 14,
  },
  summaryLabel: { color: colors.inkFaint, fontSize: 8, fontWeight: '800', letterSpacing: 0.8 },
  summaryValue: {
    color: colors.ink,
    fontSize: 22,
    fontWeight: '700',
    marginTop: 8,
    fontVariant: ['tabular-nums'],
  },
  summaryCaption: { color: colors.inkMuted, fontSize: 9, marginTop: 5 },
  positive: { color: colors.positive },
  negative: { color: colors.negative },
  contentGrid: { flexDirection: 'row', alignItems: 'flex-start', gap: 16 },
  contentGridStacked: { flexDirection: 'column' },
  mainColumn: { flex: 1.65, minWidth: 0, width: '100%' },
  sideColumn: { flex: 1, minWidth: 0, width: '100%' },
  aiPanel: { borderColor: '#96CFD0' },
  aiHeader: {
    minHeight: 66,
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 17,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  aiIcon: {
    width: 36,
    height: 36,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  aiHeading: { flex: 1 },
  aiEyebrow: { color: colors.tealDark, fontSize: 8, fontWeight: '900', letterSpacing: 1 },
  aiTitle: { color: colors.ink, fontSize: 14, fontWeight: '700', marginTop: 3 },
  aiBody: { padding: 18, gap: 12 },
  aiParagraph: { color: colors.inkMuted, fontSize: 11, lineHeight: 18 },
  aiParagraphLabel: { color: colors.ink, fontWeight: '800' },
  aiUnavailable: { padding: 18 },
  aiUnavailableTitle: { color: colors.ink, fontSize: 12, fontWeight: '700' },
  aiUnavailableText: { color: colors.inkMuted, fontSize: 10, lineHeight: 15, marginTop: 5 },
  sentimentChartRoot: { paddingTop: 14 },
  sentimentReadout: {
    paddingHorizontal: 18,
    paddingBottom: 8,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 12,
  },
  sentimentReadoutDate: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  sentimentReadoutHint: {
    color: colors.inkFaint,
    fontSize: 7,
    fontWeight: '800',
    letterSpacing: 0.7,
    marginTop: 3,
  },
  sentimentReadoutValues: { flexDirection: 'row', gap: 22 },
  sentimentReadoutLabel: {
    color: colors.inkFaint,
    fontSize: 7,
    fontWeight: '900',
    letterSpacing: 0.7,
  },
  sentimentReadoutValue: {
    fontSize: 14,
    fontWeight: '800',
    marginTop: 3,
    fontVariant: ['tabular-nums'],
  },
  sentimentReadoutShares: {
    color: colors.ink,
    fontSize: 12,
    fontWeight: '700',
    marginTop: 3,
    fontVariant: ['tabular-nums'],
  },
  chartWrap: { minHeight: 174, paddingHorizontal: 18, paddingBottom: 18, flexDirection: 'row', gap: 9 },
  chartScale: { width: 34, height: 145, justifyContent: 'space-between' },
  scaleText: { color: colors.inkFaint, fontSize: 8, fontVariant: ['tabular-nums'] },
  chartPlot: {
    flex: 1,
    height: 150,
    flexDirection: 'row',
    alignItems: 'flex-start',
    position: 'relative',
  },
  guideLine: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 1,
    backgroundColor: colors.line,
  },
  guideTop: { top: 0 },
  guideMiddle: { top: 60, backgroundColor: colors.lineStrong },
  guideBottom: { top: 120 },
  barColumn: { flex: 1, minWidth: 24, alignItems: 'center', zIndex: 2 },
  barColumnActive: { backgroundColor: colors.tealSoft },
  barArea: { width: '100%', height: 120, position: 'relative', alignItems: 'center' },
  sentimentBar: { position: 'absolute', width: '46%', minWidth: 7, maxWidth: 18 },
  positiveBar: { backgroundColor: colors.positive },
  negativeBar: { backgroundColor: colors.negative },
  barValue: { color: colors.inkMuted, fontSize: 7, fontVariant: ['tabular-nums'] },
  barLabel: { color: colors.inkFaint, fontSize: 8, marginTop: 4 },
  sentimentTrackingLayer: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    zIndex: 4,
    cursor: 'crosshair',
  } as never,
  transactionRow: {
    minHeight: 76,
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 14,
  },
  transactionIdentity: { flex: 1, minWidth: 0 },
  transactionTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 7, flexWrap: 'wrap' },
  transactionName: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  transactionMeta: { color: colors.inkFaint, fontSize: 9, lineHeight: 14, marginTop: 5 },
  actionPill: { paddingHorizontal: 6, paddingVertical: 3 },
  directionalPill: { backgroundColor: colors.blueSoft },
  administrativePill: { backgroundColor: colors.surfaceMuted },
  actionPillText: { fontSize: 7, fontWeight: '800', letterSpacing: 0.5 },
  directionalText: { color: colors.blue },
  administrativeText: { color: colors.inkMuted },
  transactionNumbers: { alignItems: 'flex-end' },
  transactionShares: { color: colors.ink, fontSize: 10, fontWeight: '800' },
  transactionPrice: { color: colors.inkFaint, fontSize: 9, marginTop: 4 },
  interpretationBody: { padding: 17 },
  interpretationHeadline: { color: colors.ink, fontSize: 14, fontWeight: '800' },
  interpretationSummary: { color: colors.inkMuted, fontSize: 10, lineHeight: 16, marginTop: 7 },
  factorRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 9, marginTop: 12 },
  factorDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.teal, marginTop: 5 },
  factorText: { flex: 1, color: colors.inkMuted, fontSize: 10, lineHeight: 15 },
  positionPanel: { padding: 17, backgroundColor: colors.tealSoft, borderColor: '#A6D9D9' },
  positionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  positionEyebrow: { color: colors.tealDark, fontSize: 8, fontWeight: '900', letterSpacing: 0.9 },
  positionValue: { color: colors.ink, fontSize: 23, fontWeight: '700', marginTop: 14 },
  positionMeta: { color: colors.tealDark, fontSize: 9, marginTop: 4 },
  positionReturn: { fontSize: 10, fontWeight: '700', marginTop: 10 },
  caveatBody: { padding: 16, gap: 12 },
  caveatRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 9 },
  caveatText: { flex: 1, color: colors.inkMuted, fontSize: 9, lineHeight: 14 },
  newsRow: {
    minHeight: 76,
    padding: 14,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  newsCopy: { flex: 1, minWidth: 0 },
  newsHeadline: { color: colors.ink, fontSize: 10, fontWeight: '700', lineHeight: 15 },
  newsMeta: { color: colors.inkFaint, fontSize: 8, marginTop: 5 },
  disclaimer: {
    color: colors.inkFaint,
    fontSize: 9,
    lineHeight: 14,
    textAlign: 'center',
    marginVertical: 8,
    paddingHorizontal: 20,
  },
});
