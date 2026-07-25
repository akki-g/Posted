import { Text, View, StyleSheet } from 'react-native';

import { LoadingState } from '@/components/ui';
import { daysUntil, money, percent } from '@/lib/format';
import type { HoldingSummary, MoneyOverviewResponse, MorningDebriefResponse } from '@/lib/types';
import { colors, radius, spacing } from '@/theme/tokens';

type Props = {
  debrief?: MorningDebriefResponse;
  debriefLoading: boolean;
  holdings: HoldingSummary[];
  money: MoneyOverviewResponse | undefined;
  moneyLoading: boolean;
  privateMode: boolean;
};

export function DebriefPanel({
  debrief,
  debriefLoading,
  holdings,
  money: moneyOverview,
  moneyLoading,
  privateMode,
}: Props) {
  const topHoldings = holdings.slice(0, 4);
  const topCategories = (moneyOverview?.spending_by_category ?? []).slice(0, 3);
  const upcoming = (moneyOverview?.subscriptions ?? [])
    .filter((item) => item.status === 'active')
    .sort((a, b) => a.next_expected_date.localeCompare(b.next_expected_date))
    .slice(0, 3);

  return (
    <View style={styles.panel}>
      <Text style={styles.kicker}>TODAY'S DEBRIEF</Text>
      {debriefLoading ? (
        <LoadingState label="Putting your debrief together" />
      ) : debrief?.available && debrief.summary ? (
        <Text style={styles.summary}>{debrief.summary}</Text>
      ) : (
        <Text style={styles.summaryMuted}>
          No AI summary available right now — the breakdown below is still current.
        </Text>
      )}

      <View style={styles.divider} />
      <Text style={styles.sectionLabel}>TOP HOLDINGS</Text>
      {topHoldings.length === 0 ? (
        <Text style={styles.emptyText}>No holdings yet.</Text>
      ) : (
        topHoldings.map((holding) => {
          const weight = Number(holding.portfolio_weight);
          return (
            <View key={holding.security_id} style={styles.holdingRow}>
              <Text style={styles.holdingSymbol}>{holding.symbol}</Text>
              <View style={styles.weightTrack}>
                <View style={[styles.weightFill, { width: `${Math.min(100, Math.max(2, weight))}%` }]} />
              </View>
              <Text style={styles.holdingWeight}>{weight.toFixed(1)}%</Text>
            </View>
          );
        })
      )}

      <View style={styles.divider} />
      <Text style={styles.sectionLabel}>SPENDING THIS WEEK</Text>
      {moneyLoading ? (
        <LoadingState label="Loading spending" />
      ) : moneyOverview ? (
        <>
          <View style={styles.spendingHeadline}>
            <Text style={styles.bigNumber}>
              {privateMode ? '$••••' : money(moneyOverview.weekly_spending)}
            </Text>
            <Text style={styles.caption}>
              vs {privateMode ? '$••••' : money(moneyOverview.weekly_income)} income
            </Text>
          </View>
          {topCategories.length === 0 ? (
            <Text style={styles.emptyText}>No spending recorded this week.</Text>
          ) : (
            topCategories.map((category) => (
              <View key={category.category} style={styles.categoryRow}>
                <Text style={styles.categoryLabel}>{category.label}</Text>
                <Text style={styles.categoryAmount}>
                  {privateMode ? '$••••' : money(category.amount)} · {percent(category.percent)}
                </Text>
              </View>
            ))
          )}
        </>
      ) : (
        <Text style={styles.emptyText}>Spending data unavailable.</Text>
      )}

      <View style={styles.divider} />
      <Text style={styles.sectionLabel}>UPCOMING</Text>
      {upcoming.length === 0 ? (
        <Text style={styles.emptyText}>Nothing recurring due soon.</Text>
      ) : (
        upcoming.map((item) => (
          <View key={item.id} style={styles.upcomingRow}>
            <View style={styles.upcomingIdentity}>
              <Text style={styles.upcomingMerchant}>{item.merchant_name}</Text>
              <Text style={styles.upcomingWhen}>{daysUntil(item.next_expected_date)}</Text>
            </View>
            <Text style={styles.upcomingAmount}>
              {privateMode ? '$••••' : money(item.average_amount)}
            </Text>
          </View>
        ))
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderTopWidth: 3,
    borderTopColor: colors.ink,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  kicker: {
    color: colors.inkFaint,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.4,
    marginBottom: spacing.sm,
  },
  summary: { color: colors.ink, fontSize: 13, lineHeight: 20 },
  summaryMuted: { color: colors.inkMuted, fontSize: 12, lineHeight: 18, fontStyle: 'italic' },
  divider: { height: 1, backgroundColor: colors.line, marginVertical: spacing.md },
  sectionLabel: {
    color: colors.inkFaint,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.2,
    marginBottom: spacing.sm,
  },
  emptyText: { color: colors.inkMuted, fontSize: 11, lineHeight: 16 },
  holdingRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  holdingSymbol: { color: colors.ink, fontSize: 11, fontWeight: '700', width: 48 },
  weightTrack: { flex: 1, height: 5, backgroundColor: colors.surfaceMuted, borderRadius: 3 },
  weightFill: { height: 5, backgroundColor: colors.teal, borderRadius: 3 },
  holdingWeight: {
    color: colors.inkMuted,
    fontSize: 10,
    fontVariant: ['tabular-nums'],
    width: 42,
    textAlign: 'right',
  },
  spendingHeadline: { marginBottom: spacing.sm },
  bigNumber: { color: colors.ink, fontSize: 22, fontWeight: '700', fontVariant: ['tabular-nums'] },
  caption: { color: colors.inkMuted, fontSize: 11, marginTop: 3 },
  categoryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 5,
  },
  categoryLabel: { color: colors.ink, fontSize: 11, fontWeight: '600' },
  categoryAmount: { color: colors.inkMuted, fontSize: 11, fontVariant: ['tabular-nums'] },
  upcomingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 7,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  upcomingIdentity: { flex: 1 },
  upcomingMerchant: { color: colors.ink, fontSize: 12, fontWeight: '600' },
  upcomingWhen: { color: colors.inkMuted, fontSize: 10, marginTop: 2 },
  upcomingAmount: { color: colors.ink, fontSize: 12, fontWeight: '700', fontVariant: ['tabular-nums'] },
});
