import { useQuery } from '@tanstack/react-query';
import { CalendarClock, CircleDollarSign, ShieldCheck } from 'lucide-react-native';
import { useEffect } from 'react';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { SubscriptionList } from '@/components/MoneyLists';
import { ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { money } from '@/lib/format';
import { colors } from '@/theme/tokens';

export default function SubscriptionsScreen() {
  useEffect(() => setAssistantSection('money'), []);
  const { width } = useWindowDimensions();
  const desktop = width >= 900;
  const mobile = width < 700;
  const query = useQuery({ queryKey: ['subscriptions'], queryFn: api.subscriptions });
  const monthly = (query.data ?? []).reduce(
    (total, stream) => total + monthlyEquivalent(stream.frequency, Number(stream.average_amount)),
    0,
  );
  const next = query.data?.[0];

  return (
    <AppShell
      title={mobile ? 'Recurring' : 'Recurring charges'}
      eyebrow="PREDICTABLE BILLS"
      refreshing={query.isRefetching}
      onRefresh={() => query.refetch()}>
      {mobile ? (
        <>
          <View style={styles.mobileHero}>
            <Text style={styles.mobileHeroLabel}>ESTIMATED MONTHLY</Text>
            <Text style={styles.mobileHeroValue}>{money(monthly)}</Text>
            <Text style={styles.mobileHeroCaption}>{money(monthly * 12)} per year</Text>
          </View>
          <View style={styles.mobileSummaryRow}>
            <SummaryMetric label="ACTIVE" value={String(query.data?.length ?? '—')} caption="streams" compact />
            <SummaryMetric
              label="NEXT"
              value={next ? money(next.average_amount) : '—'}
              caption={next?.merchant_name ?? 'Nothing upcoming'}
              compact
            />
          </View>
        </>
      ) : (
        <View style={styles.summaryRow}>
          <SummaryMetric label="MONTHLY COMMITMENT" value={money(monthly)} caption={`${money(monthly * 12)} annualized`} />
          <SummaryMetric label="ACTIVE STREAMS" value={String(query.data?.length ?? '—')} caption="Detected from posted activity" />
          <SummaryMetric label="NEXT EXPECTED" value={next ? money(next.average_amount) : '—'} caption={next?.merchant_name ?? 'No upcoming charge'} />
        </View>
      )}

      <View style={[styles.layout, !desktop && styles.stack]}>
        <View style={[styles.panel, styles.listPanel, mobile && styles.mobilePanel]}>
          <SectionHeader title="Detected recurring activity" caption="Review before treating a charge as a subscription" />
          {query.isLoading ? <LoadingState label="Detecting recurring charges" /> : null}
          {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
          {query.data ? <SubscriptionList streams={query.data} /> : null}
        </View>

        <View style={styles.insightsColumn}>
          <View style={[styles.panel, mobile && styles.mobilePanel]}>
            <SectionHeader title="How detection works" caption="Evidence, not a provider label" />
            <Insight icon={<CalendarClock size={17} color={colors.tealDark} />} title="Timing cadence" caption="Looks for consistent gaps such as monthly or annual billing." />
            <Insight icon={<CircleDollarSign size={17} color={colors.tealDark} />} title="Amount stability" caption="Allows small changes without grouping unrelated purchases." />
            <Insight icon={<ShieldCheck size={17} color={colors.tealDark} />} title="Confidence score" caption="Requires repeated posted outflows and never counts pending charges." />
          </View>
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

function SummaryMetric({ label, value, caption, compact = false }: { label: string; value: string; caption: string; compact?: boolean }) {
  return (
    <View style={[styles.summaryTile, compact && styles.summaryTileCompact]}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={styles.summaryValue}>{value}</Text>
      <Text style={styles.summaryCaption}>{caption}</Text>
    </View>
  );
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
  summaryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 1, backgroundColor: colors.line, marginBottom: 16 },
  summaryTile: { flex: 1, minWidth: 220, height: 118, padding: 18, backgroundColor: colors.surface },
  summaryTileCompact: { minWidth: 0, height: 104, padding: 14, borderWidth: 1, borderColor: colors.line, borderRadius: 12 },
  mobileHero: { backgroundColor: colors.navy, borderRadius: 16, padding: 22, marginBottom: 10 },
  mobileHeroLabel: { color: '#8FA0B7', fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  mobileHeroValue: { color: colors.white, fontSize: 34, fontWeight: '700', marginTop: 9, fontVariant: ['tabular-nums'] },
  mobileHeroCaption: { color: '#AAB5C4', fontSize: 10, marginTop: 5 },
  mobileSummaryRow: { flexDirection: 'row', gap: 10, marginBottom: 14 },
  summaryLabel: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  summaryValue: { color: colors.ink, fontSize: 24, fontWeight: '700', marginTop: 15, fontVariant: ['tabular-nums'] },
  summaryCaption: { color: colors.inkMuted, fontSize: 10, marginTop: 5 },
  layout: { flexDirection: 'row', gap: 16, alignItems: 'flex-start' },
  stack: { flexDirection: 'column' },
  panel: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  mobilePanel: { borderRadius: 12, overflow: 'hidden' },
  listPanel: { flex: 1.45, width: '100%' },
  insightsColumn: { flex: 1, width: '100%', gap: 16 },
  insightRow: { minHeight: 84, padding: 16, borderBottomWidth: 1, borderBottomColor: colors.line, flexDirection: 'row', alignItems: 'center', gap: 12 },
  insightIcon: { width: 36, height: 36, backgroundColor: colors.tealSoft, alignItems: 'center', justifyContent: 'center' },
  insightCopy: { flex: 1 },
  insightTitle: { color: colors.ink, fontSize: 12, fontWeight: '700' },
  insightCaption: { color: colors.inkMuted, fontSize: 10, lineHeight: 15, marginTop: 4 },
  notice: { padding: 18, borderLeftWidth: 3, borderLeftColor: colors.warning, backgroundColor: colors.warningSoft },
  noticeLabel: { color: colors.warning, fontSize: 8, fontWeight: '800', letterSpacing: 1 },
  noticeTitle: { color: colors.ink, fontSize: 13, fontWeight: '700', marginTop: 8 },
  noticeText: { color: colors.inkMuted, fontSize: 10, lineHeight: 16, marginTop: 6 },
});
