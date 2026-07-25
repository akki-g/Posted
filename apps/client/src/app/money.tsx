import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import {
  ArrowDownLeft,
  ArrowRight,
  Eye,
  EyeOff,
  ReceiptText,
  Repeat2,
  SlidersHorizontal,
  WalletCards,
} from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { MoneyAccountList, SubscriptionList, TransactionList } from '@/components/MoneyLists';
import { ActionButton, DemoBanner, ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { money, relativeTime } from '@/lib/format';
import type {
  DailySpendingPoint,
  MoneyOverviewResponse,
  SpendingCategorySummary,
} from '@/lib/types';
import { cardShadow, colors, radius } from '@/theme/tokens';

export default function MoneyScreen() {
  useEffect(() => setAssistantSection('money'), []);
  const { width } = useWindowDimensions();
  const desktop = width >= 1080;
  const mobile = width < 700;
  const router = useRouter();
  const [privateMode, setPrivateMode] = useState(false);
  const query = useQuery({ queryKey: ['money-overview'], queryFn: api.moneyOverview });
  const concealed = (value: string) => (privateMode ? '$••••' : money(value));

  const headerAction = (
    <View style={styles.headerActions}>
      <Pressable
        accessibilityLabel={privateMode ? 'Show balances' : 'Hide balances'}
        onPress={() => setPrivateMode((value) => !value)}
        style={styles.privacyButton}>
        {privateMode ? (
          <EyeOff size={17} color={colors.inkMuted} />
        ) : (
          <Eye size={17} color={colors.inkMuted} />
        )}
      </Pressable>
      {!mobile ? (
        <ActionButton
          label="Manage accounts"
          onPress={() => router.push('/settings')}
          icon={<SlidersHorizontal size={14} color={colors.white} />}
        />
      ) : null}
    </View>
  );

  return (
    <AppShell
      title={mobile ? 'Your money' : 'Money overview'}
      eyebrow={mobile ? 'TODAY' : 'CASH FLOW AND EVERYDAY FINANCES'}
      headerAction={headerAction}
      refreshing={query.isRefetching}
      onRefresh={() => query.refetch()}>
      {query.isLoading ? <LoadingState label="Loading financial accounts" /> : null}
      {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
      {query.data && mobile ? (
        <MobileMoneyOverview
          data={query.data}
          privateMode={privateMode}
          openTransactions={() => router.push('/transactions')}
          openRecurring={() => router.push('/subscriptions')}
          openAccounts={() => router.push('/settings')}
        />
      ) : null}
      {query.data && !mobile ? (
        <>
          {query.data.demo_mode ? (
            <DemoBanner message="Sample bank accounts and transactions. Connect Plaid Sandbox when your credentials are ready." />
          ) : null}

          <View style={[styles.metrics, !desktop && styles.metricsWrapped]}>
            <Metric
              label="NET CASH POSITION"
              value={concealed(query.data.net_cash_position)}
              caption={`${concealed(query.data.cash_balance)} cash less card balances`}
              primary
            />
            <Metric
              label="SPENT THIS WEEK"
              value={concealed(query.data.weekly_spending)}
              caption={`${concealed(query.data.weekly_income)} income received`}
            />
            <Metric
              label="CARD BALANCES"
              value={concealed(query.data.card_balance)}
              caption="Across connected credit cards"
            />
            <Metric
              label="RECURRING MONTHLY"
              value={concealed(query.data.monthly_recurring)}
              caption={`${concealed(query.data.annualized_recurring)} annualized`}
            />
          </View>

          <View style={[styles.twoColumn, !desktop && styles.stack]}>
            <View style={[styles.panel, styles.activityPanel]}>
              <SectionHeader title="Weekly activity" caption="Posted purchases · transfers excluded" />
              <DailyBars points={query.data.daily_spending} privateMode={privateMode} />
              <CategoryBars categories={query.data.spending_by_category} privateMode={privateMode} />
            </View>
            <View style={[styles.panel, styles.accountsPanel]}>
              <SectionHeader title="Connected accounts" caption="Cash and liabilities" />
              <MoneyAccountList accounts={query.data.accounts} />
              <View style={styles.syncMeta}>
                <View style={styles.liveDot} />
                <Text style={styles.syncMetaText}>
                  Updated {query.data.last_synced_at ? relativeTime(query.data.last_synced_at) : 'never'}
                </Text>
              </View>
            </View>
          </View>

          <View style={[styles.twoColumn, !desktop && styles.stack]}>
            <View style={[styles.panel, styles.transactionsPanel]}>
              <SectionHeader
                title="Recent transactions"
                caption="All connected spending sources"
                action={<TextAction label="All transactions" onPress={() => router.push('/transactions')} />}
              />
              <TransactionList transactions={query.data.recent_transactions.slice(0, 6)} />
            </View>
            <View style={[styles.panel, styles.subscriptionPanel]}>
              <SectionHeader
                title="Recurring charges"
                caption="Detected from transaction history"
                action={<TextAction label="Review" onPress={() => router.push('/subscriptions')} />}
              />
              <SubscriptionList streams={query.data.subscriptions.slice(0, 4)} />
            </View>
          </View>
        </>
      ) : null}
    </AppShell>
  );
}

function MobileMoneyOverview({
  data,
  privateMode,
  openTransactions,
  openRecurring,
  openAccounts,
}: {
  data: MoneyOverviewResponse;
  privateMode: boolean;
  openTransactions: () => void;
  openRecurring: () => void;
  openAccounts: () => void;
}) {
  const concealed = (value: string) => (privateMode ? '$••••' : money(value));
  return (
    <>
      {data.demo_mode ? (
        <DemoBanner message="You’re viewing sample money activity. Connect Plaid Sandbox when you’re ready." />
      ) : null}

      <View style={styles.mobileHero}>
        <Text style={styles.mobileHeroLabel}>NET CASH</Text>
        <Text style={styles.mobileHeroValue}>{concealed(data.net_cash_position)}</Text>
        <Text style={styles.mobileHeroCaption}>
          {concealed(data.cash_balance)} cash · {concealed(data.card_balance)} on cards
        </Text>
        <View style={styles.mobileHeroDivider} />
        <View style={styles.mobileHeroBottom}>
          <View>
            <Text style={styles.mobileHeroSmallLabel}>MONTHLY COMMITMENTS</Text>
            <Text style={styles.mobileHeroSmallValue}>{concealed(data.monthly_recurring)}</Text>
          </View>
          <Text style={styles.mobileHeroSync}>
            {data.last_synced_at ? `Updated ${relativeTime(data.last_synced_at)}` : 'Not synced yet'}
          </Text>
        </View>
      </View>

      <View style={styles.mobileMetricRow}>
        <View style={styles.mobileMetricCard}>
          <View style={styles.mobileMetricIconOut}>
            <ReceiptText size={17} color={colors.warning} />
          </View>
          <Text style={styles.mobileMetricLabel}>Spent this week</Text>
          <Text style={styles.mobileMetricValue}>{concealed(data.weekly_spending)}</Text>
        </View>
        <View style={styles.mobileMetricCard}>
          <View style={styles.mobileMetricIconIn}>
            <ArrowDownLeft size={17} color={colors.positive} />
          </View>
          <Text style={styles.mobileMetricLabel}>Income received</Text>
          <Text style={styles.mobileMetricValue}>{concealed(data.weekly_income)}</Text>
        </View>
      </View>

      <View style={styles.mobileQuickActions}>
        <MobileQuickAction
          icon={<ReceiptText size={19} color={colors.tealDark} />}
          label="Activity"
          onPress={openTransactions}
        />
        <MobileQuickAction
          icon={<Repeat2 size={19} color={colors.tealDark} />}
          label="Recurring"
          onPress={openRecurring}
        />
        <MobileQuickAction
          icon={<WalletCards size={19} color={colors.tealDark} />}
          label="Accounts"
          onPress={openAccounts}
        />
      </View>

      <View style={[styles.panel, styles.mobileSection]}>
        <SectionHeader title="This week" caption="Posted spending · transfers removed" />
        <DailyBars points={data.daily_spending} privateMode={privateMode} compact />
        <CategoryBars categories={data.spending_by_category} privateMode={privateMode} />
      </View>

      <View style={[styles.panel, styles.mobileSection]}>
        <SectionHeader
          title="Recent activity"
          action={<TextAction label="See all" onPress={openTransactions} />}
        />
        <TransactionList transactions={data.recent_transactions.slice(0, 5)} />
      </View>

      <View style={[styles.panel, styles.mobileSection]}>
        <SectionHeader
          title="Coming up"
          caption="Detected recurring charges"
          action={<TextAction label="Review" onPress={openRecurring} />}
        />
        <SubscriptionList streams={data.subscriptions.slice(0, 3)} />
      </View>

      <View style={[styles.panel, styles.mobileSection]}>
        <SectionHeader title="Accounts" caption="Cash and card balances" />
        <MoneyAccountList accounts={data.accounts} />
      </View>
    </>
  );
}

function MobileQuickAction({
  icon,
  label,
  onPress,
}: {
  icon: React.ReactNode;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.mobileQuickAction}>
      <View style={styles.mobileQuickIcon}>{icon}</View>
      <Text style={styles.mobileQuickLabel}>{label}</Text>
    </Pressable>
  );
}

function Metric({ label, value, caption, primary = false }: { label: string; value: string; caption: string; primary?: boolean }) {
  return (
    <View style={[styles.metric, primary && styles.metricPrimary]}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, primary && styles.metricValuePrimary]}>{value}</Text>
      <Text style={styles.metricCaption}>{caption}</Text>
    </View>
  );
}

function DailyBars({
  points,
  privateMode,
  compact = false,
}: {
  points: DailySpendingPoint[];
  privateMode: boolean;
  compact?: boolean;
}) {
  const maximum = Math.max(...points.map((point) => Number(point.amount)), 1);
  return (
    <View style={[styles.dailyChart, compact && styles.dailyChartCompact]}>
      {points.map((point) => {
        const height = Math.max(4, (Number(point.amount) / maximum) * (compact ? 70 : 96));
        return (
          <View key={point.date} style={styles.dayColumn}>
            <Text style={styles.dayAmount}>{privateMode ? '••' : money(point.amount, true)}</Text>
            <View style={styles.barTrack}>
              <View style={[styles.dayBar, { height }]} />
            </View>
            <Text style={styles.dayLabel}>{new Date(`${point.date}T12:00:00`).toLocaleDateString('en-US', { weekday: 'short' }).slice(0, 2)}</Text>
          </View>
        );
      })}
    </View>
  );
}

function CategoryBars({ categories, privateMode }: { categories: SpendingCategorySummary[]; privateMode: boolean }) {
  return (
    <View style={styles.categoryList}>
      {categories.slice(0, 4).map((category) => (
        <View key={category.category} style={styles.categoryRow}>
          <View style={styles.categoryCopy}>
            <Text style={styles.categoryLabel}>{category.label}</Text>
            <Text style={styles.categoryAmount}>{privateMode ? '$••' : money(category.amount)}</Text>
          </View>
          <View style={styles.categoryTrack}>
            <View style={[styles.categoryFill, { width: `${Math.max(2, Number(category.percent))}%` }]} />
          </View>
        </View>
      ))}
    </View>
  );
}

function TextAction({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={styles.textAction}>
      <Text style={styles.textActionLabel}>{label}</Text>
      <ArrowRight size={14} color={colors.tealDark} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  privacyButton: { width: 38, height: 38, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', borderRadius: 4 },
  mobileHero: {
    backgroundColor: colors.navy,
    borderRadius: 16,
    padding: 22,
    marginBottom: 12,
  },
  mobileHeroLabel: { color: '#8FA0B7', fontSize: 10, fontWeight: '800', letterSpacing: 1.2 },
  mobileHeroValue: {
    color: colors.white,
    fontSize: 36,
    lineHeight: 43,
    fontWeight: '700',
    letterSpacing: -1,
    marginTop: 9,
    fontVariant: ['tabular-nums'],
  },
  mobileHeroCaption: { color: '#AAB5C4', fontSize: 11, marginTop: 6 },
  mobileHeroDivider: { height: 1, backgroundColor: '#2A3548', marginVertical: 18 },
  mobileHeroBottom: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12 },
  mobileHeroSmallLabel: { color: '#7F8DA1', fontSize: 8, fontWeight: '800', letterSpacing: 0.8 },
  mobileHeroSmallValue: { color: colors.white, fontSize: 15, fontWeight: '700', marginTop: 5, fontVariant: ['tabular-nums'] },
  mobileHeroSync: { color: '#8FA0B7', fontSize: 9, textAlign: 'right' },
  mobileMetricRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  mobileMetricCard: { flex: 1, minHeight: 126, borderWidth: 1, borderColor: colors.line, borderRadius: 12, backgroundColor: colors.surface, padding: 14 },
  mobileMetricIconOut: { width: 32, height: 32, borderRadius: 16, backgroundColor: colors.warningSoft, alignItems: 'center', justifyContent: 'center' },
  mobileMetricIconIn: { width: 32, height: 32, borderRadius: 16, backgroundColor: colors.positiveSoft, alignItems: 'center', justifyContent: 'center' },
  mobileMetricLabel: { color: colors.inkMuted, fontSize: 10, marginTop: 12 },
  mobileMetricValue: { color: colors.ink, fontSize: 18, fontWeight: '700', marginTop: 4, fontVariant: ['tabular-nums'] },
  mobileQuickActions: { flexDirection: 'row', gap: 10, marginBottom: 18 },
  mobileQuickAction: { flex: 1, minHeight: 76, borderWidth: 1, borderColor: colors.line, borderRadius: 10, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', gap: 7 },
  mobileQuickIcon: { width: 34, height: 34, borderRadius: 17, backgroundColor: colors.tealSoft, alignItems: 'center', justifyContent: 'center' },
  mobileQuickLabel: { color: colors.ink, fontSize: 10, fontWeight: '700' },
  mobileSection: { marginBottom: 14, borderRadius: 12, overflow: 'hidden' },
  metrics: { flexDirection: 'row', marginBottom: 16, gap: 1, backgroundColor: colors.line },
  metricsWrapped: { flexWrap: 'wrap' },
  metric: { flex: 1, minWidth: 185, height: 130, padding: 18, backgroundColor: colors.surface },
  metricPrimary: { flex: 1.45, minWidth: 275 },
  metricLabel: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  metricValue: { color: colors.ink, fontSize: 23, fontWeight: '700', marginTop: 17, fontVariant: ['tabular-nums'] },
  metricValuePrimary: { fontSize: 30, marginTop: 13 },
  metricCaption: { color: colors.inkMuted, fontSize: 10, marginTop: 7 },
  twoColumn: { flexDirection: 'row', gap: 16, marginBottom: 16, alignItems: 'stretch' },
  stack: { flexDirection: 'column' },
  panel: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.lg,
    overflow: 'hidden',
    ...cardShadow,
  },
  activityPanel: { flex: 1.5, minHeight: 390 },
  accountsPanel: { flex: 1, minHeight: 390 },
  transactionsPanel: { flex: 1.25 },
  subscriptionPanel: { flex: 1 },
  dailyChart: { height: 165, flexDirection: 'row', alignItems: 'flex-end', gap: 8, paddingHorizontal: 18, paddingTop: 20, borderBottomWidth: 1, borderBottomColor: colors.line },
  dailyChartCompact: { height: 145, paddingTop: 8 },
  dayColumn: { flex: 1, height: 135, alignItems: 'center', justifyContent: 'flex-end' },
  dayAmount: { color: colors.inkFaint, fontSize: 8, marginBottom: 5, fontVariant: ['tabular-nums'] },
  barTrack: { height: 96, width: '54%', minWidth: 12, backgroundColor: colors.surfaceMuted, justifyContent: 'flex-end' },
  dayBar: { width: '100%', backgroundColor: colors.teal },
  dayLabel: { color: colors.inkMuted, fontSize: 9, fontWeight: '600', marginTop: 7 },
  categoryList: { padding: 18, gap: 13 },
  categoryRow: { gap: 6 },
  categoryCopy: { flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  categoryLabel: { color: colors.inkMuted, fontSize: 10 },
  categoryAmount: { color: colors.ink, fontSize: 10, fontWeight: '700', fontVariant: ['tabular-nums'] },
  categoryTrack: { height: 4, backgroundColor: colors.surfaceMuted },
  categoryFill: { height: 4, backgroundColor: colors.blue },
  syncMeta: { minHeight: 48, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', gap: 8 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.positive },
  syncMetaText: { color: colors.inkMuted, fontSize: 10 },
  textAction: { minHeight: 36, flexDirection: 'row', alignItems: 'center', gap: 6 },
  textActionLabel: { color: colors.tealDark, fontSize: 11, fontWeight: '700' },
});
