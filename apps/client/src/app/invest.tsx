import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import {
  ArrowRight,
  Eye,
  EyeOff,
  RefreshCw,
  Settings2,
  UserRoundSearch,
} from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { HoldingsList } from '@/components/HoldingsList';
import { MarketSearch } from '@/components/MarketSearch';
import { ActionButton, DemoBanner, ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { money, percent, relativeTime, signedMoney } from '@/lib/format';
import { cardShadow, colors, radius } from '@/theme/tokens';

export default function InvestScreen() {
  useEffect(() => setAssistantSection('investing'), []);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [privateMode, setPrivateMode] = useState(false);
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard });
  const connections = useQuery({ queryKey: ['connections'], queryFn: api.connections });
  const liveConnections = connections.data?.filter((item) => !item.demo_mode) ?? [];
  const connection = liveConnections[0] ?? connections.data?.[0];

  const sync = useMutation({
    mutationFn: async () => {
      const targets =
        liveConnections.length > 0 ? liveConnections : connection ? [connection] : [];
      if (targets.length === 0) throw new Error('Connect a brokerage before synchronizing');
      const results = await Promise.all(targets.map((item) => api.sync(item.id)));
      return results[results.length - 1];
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['connections'] }),
        queryClient.invalidateQueries({ queryKey: ['holdings'] }),
      ]);
    },
  });

  const refresh = async () => {
    await Promise.all([dashboard.refetch(), connections.refetch()]);
  };

  return (
    <AppShell
      title="Investing"
      eyebrow="PORTFOLIO"
      refreshing={dashboard.isRefetching || connections.isRefetching}
      onRefresh={() => void refresh()}
      headerAction={
        <Pressable
          accessibilityLabel={privateMode ? 'Show balances' : 'Hide balances'}
          onPress={() => setPrivateMode((value) => !value)}
          style={styles.iconButton}>
          {privateMode ? (
            <EyeOff size={17} color={colors.inkMuted} />
          ) : (
            <Eye size={17} color={colors.inkMuted} />
          )}
        </Pressable>
      }>
      {dashboard.isLoading || connections.isLoading ? (
        <LoadingState label="Loading investments" />
      ) : null}
      {dashboard.isError ? (
        <ErrorState message={dashboard.error.message} retry={() => dashboard.refetch()} />
      ) : null}

      {dashboard.data ? (
        <>
          {dashboard.data.portfolio.demo_mode ? (
            <DemoBanner message="Sample investments. Connect a brokerage in Settings, then sync to replace them." />
          ) : null}

          <MarketSearch />

          <Pressable onPress={() => router.push('/insiders')} style={styles.insiderLink}>
            <View style={styles.insiderLinkIcon}>
              <UserRoundSearch size={18} color={colors.tealDark} />
            </View>
            <View style={styles.insiderLinkCopy}>
              <Text style={styles.insiderLinkTitle}>Insider activity & sentiment</Text>
              <Text style={styles.insiderLinkText}>
                Track reported transactions, monthly MSPR, and portfolio-aware AI analysis.
              </Text>
            </View>
            <ArrowRight size={16} color={colors.tealDark} />
          </Pressable>

          <View style={styles.hero}>
            <Text style={styles.heroLabel}>TOTAL PORTFOLIO</Text>
            <Text style={styles.heroValue}>
              {privateMode ? '$••••••' : money(dashboard.data.portfolio.total_value)}
            </Text>
            <View style={styles.heroFooter}>
              <Text style={styles.heroMeta}>
                {dashboard.data.accounts.length} accounts
              </Text>
              <Text style={styles.heroMeta}>
                {dashboard.data.portfolio.last_synced_at
                  ? `Updated ${relativeTime(dashboard.data.portfolio.last_synced_at)}`
                  : 'Not synced yet'}
              </Text>
            </View>
          </View>

          <View style={styles.metricRow}>
            <View style={styles.metricCard}>
              <Text style={styles.metricLabel}>TODAY</Text>
              <Text
                style={[
                  styles.metricValue,
                  Number(dashboard.data.portfolio.day_change.amount) >= 0
                    ? styles.positive
                    : styles.negative,
                ]}>
                {privateMode
                  ? '••••'
                  : signedMoney(dashboard.data.portfolio.day_change.amount)}
              </Text>
              <Text style={styles.metricCaption}>
                {percent(dashboard.data.portfolio.day_change.percent)}
              </Text>
            </View>
            <View style={styles.metricCard}>
              <Text style={styles.metricLabel}>TOTAL RETURN</Text>
              <Text style={styles.metricValue}>
                {privateMode
                  ? '••••'
                  : signedMoney(dashboard.data.portfolio.total_gain.amount)}
              </Text>
              <Text style={styles.metricCaption}>
                {percent(dashboard.data.portfolio.total_gain.percent)}
              </Text>
            </View>
          </View>

          <View style={styles.actionRow}>
            <ActionButton
              label={sync.isPending ? 'Syncing…' : 'Sync all'}
              disabled={sync.isPending || !connection}
              onPress={() => sync.mutate()}
              icon={<RefreshCw size={14} color={colors.white} />}
            />
            <Pressable onPress={() => router.push('/settings')} style={styles.settingsButton}>
              <Settings2 size={15} color={colors.tealDark} />
              <Text style={styles.settingsButtonText}>Connection</Text>
            </Pressable>
          </View>
          {sync.isError ? <Text style={styles.error}>{sync.error.message}</Text> : null}
          {sync.isSuccess ? <Text style={styles.success}>{sync.data.message}</Text> : null}

          <View style={styles.panel}>
            <SectionHeader
              title="Largest holdings"
              caption="Market value from your latest snapshot"
            />
            <HoldingsList holdings={dashboard.data.top_holdings} limit={6} />
          </View>

          <View style={styles.panel}>
            <SectionHeader title="Accounts" caption="Authorized brokerage accounts" />
            {dashboard.data.accounts.map((account) => (
              <View key={account.id} style={styles.accountRow}>
                <View style={styles.accountMark}>
                  <Text style={styles.accountMarkText}>S</Text>
                </View>
                <View style={styles.accountCopy}>
                  <Text style={styles.accountName}>{account.name}</Text>
                  <Text style={styles.accountType}>{account.account_type}</Text>
                </View>
                <Text style={styles.accountBalance}>
                  {privateMode ? '$••••' : money(account.balance)}
                </Text>
              </View>
            ))}
          </View>
        </>
      ) : null}
    </AppShell>
  );
}

const styles = StyleSheet.create({
  iconButton: {
    width: 38,
    height: 38,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  insiderLink: {
    minHeight: 70,
    borderWidth: 1,
    borderColor: '#A6D9D9',
    backgroundColor: colors.tealSoft,
    padding: 13,
    marginBottom: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  insiderLinkIcon: {
    width: 38,
    height: 38,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  insiderLinkCopy: { flex: 1, minWidth: 0 },
  insiderLinkTitle: { color: colors.tealDark, fontSize: 12, fontWeight: '800' },
  insiderLinkText: { color: colors.tealDark, fontSize: 9, lineHeight: 14, marginTop: 3 },
  hero: {
    backgroundColor: colors.navy,
    borderRadius: 16,
    padding: 22,
    marginBottom: 12,
  },
  heroLabel: {
    color: '#9EABBD',
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1.3,
  },
  heroValue: {
    color: colors.white,
    fontSize: 36,
    lineHeight: 43,
    fontWeight: '700',
    marginTop: 10,
    fontVariant: ['tabular-nums'],
  },
  heroFooter: {
    borderTopWidth: 1,
    borderTopColor: '#2D394C',
    marginTop: 18,
    paddingTop: 13,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  heroMeta: { color: '#B7C1CE', fontSize: 10 },
  metricRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  metricCard: {
    flex: 1,
    minHeight: 112,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 15,
  },
  metricLabel: {
    color: colors.inkFaint,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1,
  },
  metricValue: {
    color: colors.ink,
    fontSize: 19,
    fontWeight: '700',
    marginTop: 14,
    fontVariant: ['tabular-nums'],
  },
  metricCaption: { color: colors.inkMuted, fontSize: 10, marginTop: 5 },
  positive: { color: colors.positive },
  negative: { color: colors.negative },
  actionRow: { flexDirection: 'row', gap: 9, marginBottom: 12 },
  settingsButton: {
    minHeight: 38,
    borderWidth: 1,
    borderColor: colors.teal,
    paddingHorizontal: 13,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
  },
  settingsButtonText: { color: colors.tealDark, fontSize: 11, fontWeight: '700' },
  error: { color: colors.negative, fontSize: 11, lineHeight: 16, marginBottom: 12 },
  success: { color: colors.positive, fontSize: 11, lineHeight: 16, marginBottom: 12 },
  panel: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    marginBottom: 14,
    borderRadius: radius.lg,
    overflow: 'hidden',
    ...cardShadow,
  },
  accountRow: {
    minHeight: 72,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  accountMark: {
    width: 34,
    height: 34,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  accountMarkText: { color: colors.tealDark, fontSize: 13, fontWeight: '800' },
  accountCopy: { flex: 1, minWidth: 0 },
  accountName: { color: colors.ink, fontSize: 12, fontWeight: '700' },
  accountType: { color: colors.inkMuted, fontSize: 10, marginTop: 4 },
  accountBalance: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
});
