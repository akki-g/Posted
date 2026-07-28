import { useQuery } from '@tanstack/react-query';
import { CalendarClock, CircleDollarSign, ShieldCheck } from 'lucide-react-native';
import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { SubscriptionList } from '@/components/MoneyLists';
import { ErrorState, LoadingState, Panel, SectionHeader, StatTile } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { money } from '@/lib/format';
import { useBreakpoint } from '@/theme/useBreakpoint';
import { colors, roles, spacing } from '@/theme/tokens';

export default function SubscriptionsScreen() {
  useEffect(() => setAssistantSection('money'), []);
  const { desktop, compact } = useBreakpoint();
  const query = useQuery({ queryKey: ['subscriptions'], queryFn: api.subscriptions });
  const monthly = (query.data ?? []).reduce(
    (total, stream) => total + monthlyEquivalent(stream.frequency, Number(stream.average_amount)),
    0,
  );
  const next = query.data?.[0];

  return (
    <AppShell
      title={compact ? 'Recurring' : 'Recurring charges'}
      eyebrow="PREDICTABLE BILLS"
      refreshing={query.isRefetching}
      onRefresh={() => query.refetch()}>
      <View style={styles.summaryRow}>
        <StatTile
          label={compact ? 'MONTHLY' : 'MONTHLY COMMITMENT'}
          value={money(monthly)}
          caption={`${money(monthly * 12)}${compact ? '/yr' : ' annualized'}`}
        />
        <StatTile label={compact ? 'ACTIVE' : 'ACTIVE STREAMS'} value={String(query.data?.length ?? '—')} caption={compact ? 'streams' : 'Detected from posted activity'} />
        {!compact ? (
          <StatTile label="NEXT EXPECTED" value={next ? money(next.average_amount) : '—'} caption={next?.merchant_name ?? 'No upcoming charge'} />
        ) : null}
      </View>

      <View style={[styles.layout, !desktop && styles.stack]}>
        <Panel style={styles.listPanel}>
          <SectionHeader title="Detected recurring activity" caption="Review before treating a charge as a subscription" />
          {query.isLoading ? <LoadingState label="Detecting recurring charges" /> : null}
          {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
          {query.data ? <SubscriptionList streams={query.data} /> : null}
        </Panel>

        <View style={styles.insightsColumn}>
          <Panel>
            <SectionHeader title="How detection works" caption="Evidence, not a provider label" />
            <Insight icon={<CalendarClock size={17} color={colors.tealDark} />} title="Timing cadence" caption="Looks for consistent gaps such as monthly or annual billing." />
            <Insight icon={<CircleDollarSign size={17} color={colors.tealDark} />} title="Amount stability" caption="Allows small changes without grouping unrelated purchases." />
            <Insight icon={<ShieldCheck size={17} color={colors.tealDark} />} title="Confidence score" caption="Requires repeated posted outflows and never counts pending charges." />
          </Panel>
          <View style={styles.notice}>
            <Text style={styles.noticeLabel}>IMPORTANT</Text>
            <Text style={styles.noticeTitle}>Detection is not cancellation</Text>
            <Text style={styles.noticeText}>Posted can identify likely recurring charges, but cancellation still happens with the merchant. Apple Pay does not expose a universal cross-merchant subscription ledger.</Text>
          </View>
        </View>
      </View>
    </AppShell>
  );
}

function monthlyEquivalent(frequency: string, amount: number) {
  if (frequency === 'weekly') return (amount * 52) / 12;
  if (frequency === 'biweekly') return (amount * 26) / 12;
  if (frequency === 'quarterly') return amount / 3;
  if (frequency === 'annual') return amount / 12;
  return amount;
}

function Insight({ icon, title, caption }: { icon: React.ReactNode; title: string; caption: string }) {
  return (
    <View style={styles.insightRow}>
      <View style={styles.insightIcon}>{icon}</View>
      <View style={styles.insightCopy}>
        <Text style={styles.insightTitle}>{title}</Text>
        <Text style={styles.insightCaption}>{caption}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  summaryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  layout: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' },
  stack: { flexDirection: 'column' },
  listPanel: { flex: 1.45, width: '100%' },
  insightsColumn: { flex: 1, width: '100%', gap: spacing.md },
  insightRow: { minHeight: 84, padding: spacing.md, borderBottomWidth: 1, borderBottomColor: roles.borderHairline, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  insightIcon: { width: 36, height: 36, backgroundColor: colors.tealSoft, alignItems: 'center', justifyContent: 'center' },
  insightCopy: { flex: 1 },
  insightTitle: { color: colors.ink, fontSize: 12, fontWeight: '700' },
  insightCaption: { color: colors.inkMuted, fontSize: 10, lineHeight: 15, marginTop: 4 },
  notice: { padding: spacing.md, borderLeftWidth: 3, borderLeftColor: colors.warning, backgroundColor: colors.warningSoft },
  noticeLabel: { color: colors.warning, fontSize: 8, fontWeight: '800', letterSpacing: 1 },
  noticeTitle: { color: colors.ink, fontSize: 13, fontWeight: '700', marginTop: 8 },
  noticeText: { color: colors.inkMuted, fontSize: 10, lineHeight: 16, marginTop: 6 },
});
