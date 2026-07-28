import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ArrowRight, Eye, EyeOff } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { Band } from '@/components/spine/Band';
import { SyncSpine, type SyncTick } from '@/components/spine/SyncSpine';
import { HoldingsList } from '@/components/HoldingsList';
import { MoneyAccountList, TransactionList } from '@/components/MoneyLists';
import { DemoBanner, ErrorState, FilterChip, IconButton, LoadingState, Panel, StatTile } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { daysUntil, daysUntilNumber, money, relativeTime, signedMoney } from '@/lib/format';
import { useConnectionSync } from '@/lib/useConnectionSync';
import type { DashboardResponse, MoneyOverviewResponse } from '@/lib/types';
import { colors, roles, spacing } from '@/theme/tokens';

type Lens = 'everything' | 'cash' | 'investments';

const LENS_LABEL: Record<Lens, string> = {
  everything: 'Everything',
  cash: 'Cash',
  investments: 'Investments',
};

function timeOfDayGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'GOOD MORNING';
  if (hour < 18) return 'GOOD AFTERNOON';
  return 'GOOD EVENING';
}

function investmentMovementNote(dashboard: DashboardResponse): string | null {
  const notable = dashboard.important_events.find(
    (event) => event.unread && (event.level === 'urgent' || event.level === 'important') && event.securities.length > 0,
  );
  if (!notable) return null;
  return `mostly ${notable.securities[0].symbol} — ${notable.headline}`;
}

function cashMovementNote(overview: MoneyOverviewResponse): string | null {
  const top = overview.spending_by_category[0];
  if (top && Number(top.percent) >= 30) {
    return `${top.label.toLowerCase()} is ${Math.round(Number(top.percent))}% of the week's spending`;
  }
  return null;
}

export default function SpineScreen() {
  const params = useLocalSearchParams<{ lens?: string }>();
  const router = useRouter();
  const lens: Lens = params.lens === 'cash' || params.lens === 'investments' ? params.lens : 'everything';
  const [privateMode, setPrivateMode] = useState(false);

  useEffect(() => {
    setAssistantSection(lens === 'cash' ? 'money' : lens === 'investments' ? 'investing' : 'general');
  }, [lens]);

  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard });
  const connections = useQuery({ queryKey: ['connections'], queryFn: api.connections });
  const moneyOverview = useQuery({ queryKey: ['money-overview'], queryFn: api.moneyOverview });
  const moneyConnections = useQuery({ queryKey: ['money-connections'], queryFn: api.moneyConnections });

  const brokerageSync = useConnectionSync({
    connections: connections.data?.map((connection) => ({
      id: connection.id,
      last_synced_at: connection.last_synced_at,
      demo: connection.demo_mode,
    })),
    syncFn: api.sync,
    invalidateKeys: [['dashboard'], ['connections'], ['holdings']],
  });
  const moneySync = useConnectionSync({
    connections: moneyConnections.data?.map((connection) => ({
      id: connection.id,
      last_synced_at: connection.last_synced_at,
      demo: connection.is_demo,
    })),
    syncFn: api.syncMoneyConnection,
    invalidateKeys: [
      ['money-overview'],
      ['money-connections'],
      ['money-transactions'],
      ['subscriptions'],
    ],
  });

  const setLens = (next: Lens) => router.setParams({ lens: next });

  const loading = dashboard.isLoading || moneyOverview.isLoading;
  const loadError = dashboard.error ?? moneyOverview.error;
  const data = dashboard.data && moneyOverview.data ? { dashboard: dashboard.data, money: moneyOverview.data } : null;

  const headerAction = (
    <IconButton
      icon={
        privateMode ? (
          <EyeOff size={17} color={colors.inkMuted} />
        ) : (
          <Eye size={17} color={privateMode ? colors.tealDark : colors.inkMuted} />
        )
      }
      accessibilityLabel={privateMode ? 'Show balances' : 'Hide balances'}
      active={privateMode}
      onPress={() => setPrivateMode((value) => !value)}
    />
  );

  return (
    <AppShell
      title="Overview"
      eyebrow={`${timeOfDayGreeting()} · ${LENS_LABEL[lens].toUpperCase()}`}
      headerAction={headerAction}
      assistantSection={lens === 'cash' ? 'money' : lens === 'investments' ? 'investing' : 'general'}
      assistantContext={`The user is viewing their net-worth overview, lensed to "${LENS_LABEL[lens]}". The screen includes position (net worth), day/week movement, per-connection sync freshness, items needing attention, and a ledger of holdings or transactions. Fetch current financial facts with the available tools before answering.`}
      assistantContextLabel={`Overview · ${LENS_LABEL[lens]} lens`}
      refreshing={brokerageSync.isPending || moneySync.isPending || dashboard.isRefetching || moneyOverview.isRefetching}
      onRefresh={() => {
        brokerageSync.mutate();
        moneySync.mutate();
        void dashboard.refetch();
        void moneyOverview.refetch();
      }}>
      <View accessibilityRole="tablist" style={styles.lensRow}>
        {(['everything', 'cash', 'investments'] as Lens[]).map((option) => (
          <FilterChip
            key={option}
            label={LENS_LABEL[option]}
            active={lens === option}
            onPress={() => setLens(option)}
          />
        ))}
      </View>

      {loading ? <LoadingState label="Loading your overview" /> : null}
      {loadError ? <ErrorState message={loadError.message} retry={() => { void dashboard.refetch(); void moneyOverview.refetch(); }} /> : null}

      {data ? (
        <>
          {data.dashboard.portfolio.demo_mode || data.money.demo_mode ? (
            <DemoBanner message="Sample money and portfolio data. Connect Plaid and Schwab in Settings to replace it." />
          ) : null}

          <PositionBand lens={lens} dashboard={data.dashboard} money={data.money} privateMode={privateMode} />
          <MovementBand lens={lens} dashboard={data.dashboard} money={data.money} privateMode={privateMode} />
          <SyncBand lens={lens} connections={connections.data ?? []} moneyConnections={moneyConnections.data ?? []} />
          <AttentionBand dashboard={data.dashboard} money={data.money} />
          <LedgerBand lens={lens} dashboard={data.dashboard} money={data.money} />
        </>
      ) : null}
    </AppShell>
  );
}

function PositionBand({
  lens,
  dashboard,
  money: moneyData,
  privateMode,
}: {
  lens: Lens;
  dashboard: DashboardResponse;
  money: MoneyOverviewResponse;
  privateMode: boolean;
}) {
  if (lens === 'cash') {
    return (
      <Band label="POSITION" first>
        <StatTile
          label="NET CASH POSITION"
          value={money(moneyData.net_cash_position)}
          caption={`${money(moneyData.cash_balance)} cash less ${money(moneyData.card_balance)} on cards`}
          size="primary"
          masked={privateMode}
        />
      </Band>
    );
  }
  if (lens === 'investments') {
    return (
      <Band label="POSITION" first>
        <StatTile
          label="TOTAL PORTFOLIO VALUE"
          value={money(dashboard.portfolio.total_value)}
          caption={`Across ${dashboard.accounts.length} account${dashboard.accounts.length === 1 ? '' : 's'}`}
          size="primary"
          masked={privateMode}
        />
      </Band>
    );
  }
  const total = Number(dashboard.portfolio.total_value) + Number(moneyData.net_cash_position);
  return (
    <Band label="POSITION" first>
      <StatTile
        label="TOTAL NET WORTH"
        value={money(total)}
        caption={`${money(dashboard.portfolio.total_value)} invested · ${money(moneyData.net_cash_position)} cash`}
        size="primary"
        masked={privateMode}
      />
    </Band>
  );
}

function MovementBand({
  lens,
  dashboard,
  money: moneyData,
  privateMode,
}: {
  lens: Lens;
  dashboard: DashboardResponse;
  money: MoneyOverviewResponse;
  privateMode: boolean;
}) {
  const investingRow = (
    <View style={styles.movementRow}>
      <StatTile
        label="TODAY"
        value={signedMoney(dashboard.portfolio.day_change.amount)}
        tone={Number(dashboard.portfolio.day_change.amount) >= 0 ? 'positive' : 'negative'}
        masked={privateMode}
      />
      <StatTile
        label="ALL TIME"
        value={signedMoney(dashboard.portfolio.total_gain.amount)}
        tone={Number(dashboard.portfolio.total_gain.amount) >= 0 ? 'positive' : 'negative'}
        masked={privateMode}
      />
    </View>
  );
  const cashRow = (
    <View style={styles.movementRow}>
      <StatTile label="SPENT THIS WEEK" value={money(moneyData.weekly_spending)} masked={privateMode} />
      <StatTile label="INCOME RECEIVED" value={money(moneyData.weekly_income)} masked={privateMode} />
    </View>
  );
  const note = lens === 'cash' ? cashMovementNote(moneyData) : investmentMovementNote(dashboard);
  return (
    <Band label="MOVEMENT">
      {lens === 'cash' ? cashRow : lens === 'investments' ? investingRow : (
        <>
          {investingRow}
          {cashRow}
        </>
      )}
      {note ? <Text style={styles.movementNote}>{note}</Text> : null}
    </Band>
  );
}

function SyncBand({
  lens,
  connections,
  moneyConnections,
}: {
  lens: Lens;
  connections: { id: string; display_name: string; last_synced_at: string | null; account_count: number; demo_mode: boolean }[];
  moneyConnections: { id: string; display_name: string; last_synced_at: string | null; account_count: number; is_demo: boolean }[];
}) {
  const brokerageTicks: SyncTick[] = connections.map((connection) => ({
    id: connection.id,
    label: connection.display_name,
    lastSyncedAt: connection.last_synced_at,
    accountCount: connection.account_count,
    demo: connection.demo_mode,
  }));
  const bankTicks: SyncTick[] = moneyConnections.map((connection) => ({
    id: connection.id,
    label: connection.display_name,
    lastSyncedAt: connection.last_synced_at,
    accountCount: connection.account_count,
    demo: connection.is_demo,
  }));
  const ticks = lens === 'cash' ? bankTicks : lens === 'investments' ? brokerageTicks : [...bankTicks, ...brokerageTicks];
  return (
    <Band label="SYNC">
      <SyncSpine ticks={ticks} />
    </Band>
  );
}

function AttentionBand({ dashboard, money: moneyData }: { dashboard: DashboardResponse; money: MoneyOverviewResponse }) {
  const router = useRouter();
  const events = dashboard.important_events
    .filter((event) => event.unread)
    .slice(0, 5)
    .map((event) => ({
      id: `event-${event.id}`,
      label: event.headline,
      meta: relativeTime(event.occurred_at),
      urgent: event.level === 'urgent',
    }));
  const subscriptions = moneyData.subscriptions
    .filter((stream) => daysUntilNumber(stream.next_expected_date) <= 7)
    .slice(0, 5)
    .map((stream) => ({
      id: `sub-${stream.id}`,
      label: `${stream.merchant_name} renews`,
      meta: `${daysUntil(stream.next_expected_date)} · ${money(stream.average_amount)}`,
      urgent: false,
    }));
  const items = [...events, ...subscriptions];
  return (
    <Band label={`ATTENTION${items.length > 0 ? ` (${items.length})` : ''}`}>
      {items.length === 0 ? (
        <Text style={styles.attentionEmpty}>Nothing needs a decision right now.</Text>
      ) : (
        <>
          {items.map((item) => (
            <View key={item.id} style={styles.attentionRow}>
              <View style={[styles.attentionMark, item.urgent && styles.attentionMarkUrgent]} />
              <Text style={styles.attentionLabel} numberOfLines={1}>
                {item.label}
              </Text>
              <Text style={styles.attentionMeta}>{item.meta}</Text>
            </View>
          ))}
          {events.length > 0 ? (
            <View style={styles.attentionFooter}>
              <TextLink label="Open feed" onPress={() => router.push('/feed')} />
            </View>
          ) : null}
        </>
      )}
    </Band>
  );
}

function LedgerBand({ lens, dashboard, money: moneyData }: { lens: Lens; dashboard: DashboardResponse; money: MoneyOverviewResponse }) {
  const router = useRouter();
  const holdings = (
    <Panel style={styles.ledgerPanel}>
      <View style={styles.ledgerHeader}>
        <Text style={styles.ledgerTitle}>Holdings</Text>
        <TextLink label="All holdings" onPress={() => router.push('/holdings')} />
      </View>
      <HoldingsList holdings={dashboard.top_holdings} limit={6} compact />
    </Panel>
  );
  const transactions = (
    <Panel style={styles.ledgerPanel}>
      <View style={styles.ledgerHeader}>
        <Text style={styles.ledgerTitle}>Recent transactions</Text>
        <TextLink label="All transactions" onPress={() => router.push('/transactions')} />
      </View>
      <TransactionList transactions={moneyData.recent_transactions.slice(0, 6)} />
    </Panel>
  );
  const accounts = (
    <Panel style={styles.ledgerPanel}>
      <View style={styles.ledgerHeader}>
        <Text style={styles.ledgerTitle}>Accounts</Text>
        <TextLink label="Manage" onPress={() => router.push('/settings')} />
      </View>
      <MoneyAccountList accounts={moneyData.accounts} />
    </Panel>
  );
  return (
    <Band label="LEDGER">
      {lens === 'investments' ? holdings : lens === 'cash' ? (
        <>
          {transactions}
          {accounts}
        </>
      ) : (
        <>
          {holdings}
          {transactions}
        </>
      )}
    </Band>
  );
}

function TextLink({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="link" onPress={onPress} style={styles.textLink}>
      <Text style={styles.textLinkLabel}>{label}</Text>
      <ArrowRight size={13} color={colors.tealDark} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  lensRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.md },
  movementRow: { flexDirection: 'row', gap: spacing.lg, flexWrap: 'wrap' },
  movementNote: { color: roles.textSecondary, fontSize: 12, lineHeight: 17, marginTop: spacing.xs },
  attentionEmpty: { color: roles.textSecondary, fontSize: 12 },
  attentionRow: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 34 },
  attentionMark: { width: 6, height: 6, borderRadius: 3, backgroundColor: roles.attentionNotable },
  attentionMarkUrgent: { backgroundColor: roles.attentionUrgent },
  attentionLabel: { flex: 1, minWidth: 0, color: colors.ink, fontSize: 12, fontWeight: '600' },
  attentionMeta: { color: roles.textSecondary, fontSize: 10 },
  attentionFooter: { marginTop: spacing.xs },
  ledgerPanel: { marginBottom: spacing.sm },
  ledgerHeader: {
    minHeight: 44,
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: roles.borderHairline,
  },
  ledgerTitle: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  textLink: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  textLinkLabel: { color: colors.tealDark, fontSize: 11, fontWeight: '700' },
});
