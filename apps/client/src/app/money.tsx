import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { ArrowRight, Eye, EyeOff, SlidersHorizontal } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { MoneyAccountList, SubscriptionList, TransactionList } from '@/components/MoneyLists';
import { ActionButton, DemoBanner, ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { money, relativeTime } from '@/lib/format';
import type { DailySpendingPoint, SpendingCategorySummary } from '@/lib/types';
import { colors } from '@/theme/tokens';

export default function MoneyScreen() {
  const { width } = useWindowDimensions();
  const desktop = width >= 1080;
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
      <ActionButton
        label="Manage accounts"
        onPress={() => router.push('/settings')}
        icon={<SlidersHorizontal size={14} color={colors.white} />}
      />
    </View>
  );

  return (
    <AppShell title="Money overview" eyebrow="CASH FLOW AND EVERYDAY FINANCES" headerAction={headerAction}>
      {query.isLoading ? <LoadingState label="Loading financial accounts" /> : null}
      {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
      {query.data ? (
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

function Metric({ label, value, caption, primary = false }: { label: string; value: string; caption: string; primary?: boolean }) {
  return (
    <View style={[styles.metric, primary && styles.metricPrimary]}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, primary && styles.metricValuePrimary]}>{value}</Text>
      <Text style={styles.metricCaption}>{caption}</Text>
    </View>
  );
}

function DailyBars({ points, privateMode }: { points: DailySpendingPoint[]; privateMode: boolean }) {
  const maximum = Math.max(...points.map((point) => Number(point.amount)), 1);
  return (
    <View style={styles.dailyChart}>
      {points.map((point) => {
        const height = Math.max(4, (Number(point.amount) / maximum) * 96);
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
  panel: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  activityPanel: { flex: 1.5, minHeight: 390 },
  accountsPanel: { flex: 1, minHeight: 390 },
  transactionsPanel: { flex: 1.25 },
  subscriptionPanel: { flex: 1 },
  dailyChart: { height: 165, flexDirection: 'row', alignItems: 'flex-end', gap: 8, paddingHorizontal: 18, paddingTop: 20, borderBottomWidth: 1, borderBottomColor: colors.line },
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
