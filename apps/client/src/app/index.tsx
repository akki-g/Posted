import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Redirect, useRouter } from 'expo-router';
import { ArrowRight, Eye, EyeOff, RefreshCw } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { EventList } from '@/components/EventList';
import { HoldingsList } from '@/components/HoldingsList';
import { PortfolioChart } from '@/components/PortfolioChart';
import { ActionButton, DemoBanner, ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { money, percent, relativeTime, signedMoney } from '@/lib/format';
import { colors } from '@/theme/tokens';

export default function DashboardScreen() {
  if (Platform.OS !== 'web') {
    return <Redirect href="/money" />;
  }

  return <PortfolioDashboard />;
}

function PortfolioDashboard() {
  useEffect(() => setAssistantSection('investing'), []);
  const { width } = useWindowDimensions();
  const desktop = width >= 1080;
  const router = useRouter();
  const queryClient = useQueryClient();
  const [privateMode, setPrivateMode] = useState(false);
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard });
  const connections = useQuery({ queryKey: ['connections'], queryFn: api.connections });
  const debrief = useQuery({ queryKey: ['morning-debrief'], queryFn: api.morningDebrief });
  const sync = useMutation({
    mutationFn: async () => {
      const connection = connections.data?.[0];
      if (!connection) throw new Error('No brokerage connection found');
      return api.sync(connection.id);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['connections'] }),
      ]);
    },
  });

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
        label={sync.isPending ? 'Syncing' : 'Sync now'}
        disabled={sync.isPending}
        onPress={() => sync.mutate()}
        icon={<RefreshCw size={14} color={colors.white} />}
      />
    </View>
  );

  return (
    <AppShell title="Portfolio overview" eyebrow="GOOD MORNING, ALEX" headerAction={headerAction}>
      {dashboard.isLoading ? <LoadingState /> : null}
      {dashboard.isError ? (
        <ErrorState message={dashboard.error.message} retry={() => dashboard.refetch()} />
      ) : null}
      {dashboard.data ? (
        <>
          {dashboard.data.portfolio.demo_mode ? <DemoBanner /> : null}

          {debrief.data?.available && debrief.data.summary ? (
            <View style={styles.debriefCard}>
              <Text style={styles.debriefKicker}>MORNING DEBRIEF · AI</Text>
              <Text style={styles.debriefText}>{debrief.data.summary}</Text>
            </View>
          ) : null}

          <View style={[styles.metrics, !desktop && styles.metricsWrapped]}>
            <View style={[styles.metricCard, styles.primaryMetric]}>
              <Text style={styles.metricLabel}>TOTAL PORTFOLIO VALUE</Text>
              <Text style={styles.portfolioValue}>
                {privateMode ? '$••••••' : money(dashboard.data.portfolio.total_value)}
              </Text>
              <Text style={styles.metricCaption}>
                Across {dashboard.data.accounts.length} Schwab accounts
              </Text>
            </View>
            <View style={styles.metricCard}>
              <Text style={styles.metricLabel}>TODAY</Text>
              <Text style={styles.positiveValue}>
                {privateMode ? '••••' : signedMoney(dashboard.data.portfolio.day_change.amount)}
              </Text>
              <Text style={styles.positiveCaption}>
                {percent(dashboard.data.portfolio.day_change.percent)}
              </Text>
            </View>
            <View style={styles.metricCard}>
              <Text style={styles.metricLabel}>TOTAL RETURN</Text>
              <Text style={styles.metricValue}>
                {privateMode ? '••••' : signedMoney(dashboard.data.portfolio.total_gain.amount)}
              </Text>
              <Text style={styles.metricCaption}>
                {percent(dashboard.data.portfolio.total_gain.percent)} all time
              </Text>
            </View>
            <View style={styles.metricCard}>
              <Text style={styles.metricLabel}>ATTENTION NEEDED</Text>
              <Text style={styles.metricValue}>{dashboard.data.unread_event_count}</Text>
              <Text style={styles.metricCaption}>Unread material updates</Text>
            </View>
          </View>

          <View style={[styles.twoColumn, !desktop && styles.stack]}>
            <View style={[styles.panel, styles.chartPanel]}>
              <SectionHeader
                title="Portfolio performance"
                caption="Daily closing value · USD"
              />
              <PortfolioChart points={dashboard.data.history} />
            </View>
            <View style={[styles.panel, styles.accountPanel]}>
              <SectionHeader title="Accounts" caption="Consolidated from Schwab" />
              {dashboard.data.accounts.map((account) => (
                <View key={account.id} style={styles.accountRow}>
                  <View style={styles.accountMark} />
                  <View style={styles.accountIdentity}>
                    <Text style={styles.accountName}>{account.name}</Text>
                    <Text style={styles.accountType}>{account.account_type}</Text>
                  </View>
                  <View style={styles.accountValueBlock}>
                    <Text style={styles.accountValue}>
                      {privateMode ? '$••••' : money(account.balance)}
                    </Text>
                    <Text style={styles.accountChange}>{signedMoney(account.day_change)}</Text>
                  </View>
                </View>
              ))}
              <View style={styles.syncMeta}>
                <View style={styles.liveDot} />
                <Text style={styles.syncMetaText}>
                  Last synced {dashboard.data.portfolio.last_synced_at ? relativeTime(dashboard.data.portfolio.last_synced_at) : 'never'}
                </Text>
              </View>
            </View>
          </View>

          <View style={[styles.twoColumn, !desktop && styles.stack]}>
            <View style={[styles.panel, styles.holdingsPanel]}>
              <SectionHeader
                title="Largest holdings"
                caption="Sorted by market value"
                action={
                  <Pressable onPress={() => router.push('/holdings')} style={styles.textAction}>
                    <Text style={styles.textActionLabel}>All holdings</Text>
                    <ArrowRight size={14} color={colors.tealDark} />
                  </Pressable>
                }
              />
              <HoldingsList holdings={dashboard.data.top_holdings} limit={5} compact />
            </View>
            <View style={[styles.panel, styles.feedPanel]}>
              <SectionHeader
                title="Impact feed"
                caption="Ranked for your portfolio"
                action={
                  <Pressable onPress={() => router.push('/feed')} style={styles.textAction}>
                    <Text style={styles.textActionLabel}>Open feed</Text>
                    <ArrowRight size={14} color={colors.tealDark} />
                  </Pressable>
                }
              />
              <EventList events={dashboard.data.important_events.slice(0, 3)} />
            </View>
          </View>
        </>
      ) : null}
    </AppShell>
  );
}

const styles = StyleSheet.create({
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  privacyButton: {
    width: 38,
    height: 38,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 4,
  },
  debriefCard: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.tealSoft,
    padding: 16,
    marginBottom: 16,
  },
  debriefKicker: { color: colors.tealDark, fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  debriefText: { color: colors.ink, fontSize: 13, lineHeight: 20, marginTop: 8 },
  metrics: { flexDirection: 'row', marginBottom: 16, gap: 1, backgroundColor: colors.line },
  metricsWrapped: { flexWrap: 'wrap', gap: 1 },
  metricCard: {
    flex: 1,
    minWidth: 180,
    height: 134,
    backgroundColor: colors.surface,
    padding: 18,
  },
  primaryMetric: { flex: 1.5, minWidth: 270 },
  metricLabel: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  portfolioValue: { color: colors.ink, fontSize: 31, fontWeight: '600', marginTop: 14, fontVariant: ['tabular-nums'] },
  metricValue: { color: colors.ink, fontSize: 23, fontWeight: '700', marginTop: 18, fontVariant: ['tabular-nums'] },
  positiveValue: { color: colors.positive, fontSize: 23, fontWeight: '700', marginTop: 18, fontVariant: ['tabular-nums'] },
  metricCaption: { color: colors.inkMuted, fontSize: 11, marginTop: 7 },
  positiveCaption: { color: colors.positive, fontSize: 11, fontWeight: '600', marginTop: 7 },
  twoColumn: { flexDirection: 'row', gap: 16, marginBottom: 16, alignItems: 'stretch' },
  stack: { flexDirection: 'column' },
  panel: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  chartPanel: { flex: 1.65, minHeight: 320 },
  accountPanel: { flex: 1, minHeight: 320 },
  holdingsPanel: { flex: 1.25 },
  feedPanel: { flex: 1 },
  accountRow: {
    minHeight: 79,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  accountMark: { width: 3, height: 32, backgroundColor: colors.teal },
  accountIdentity: { flex: 1 },
  accountName: { color: colors.ink, fontSize: 12, fontWeight: '600' },
  accountType: { color: colors.inkMuted, fontSize: 10, marginTop: 4 },
  accountValueBlock: { alignItems: 'flex-end' },
  accountValue: { color: colors.ink, fontSize: 13, fontWeight: '700', fontVariant: ['tabular-nums'] },
  accountChange: { color: colors.positive, fontSize: 10, fontWeight: '600', marginTop: 4, fontVariant: ['tabular-nums'] },
  syncMeta: { flex: 1, minHeight: 52, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', gap: 8 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.positive },
  syncMetaText: { color: colors.inkMuted, fontSize: 10 },
  textAction: { minHeight: 36, flexDirection: 'row', alignItems: 'center', gap: 6 },
  textActionLabel: { color: colors.tealDark, fontSize: 11, fontWeight: '700' },
});
