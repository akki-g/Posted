import { useQuery } from '@tanstack/react-query';
import { Search, SlidersHorizontal } from 'lucide-react-native';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { TransactionList } from '@/components/MoneyLists';
import { ErrorState, FilterChip, LoadingState, Panel, SectionHeader, StatTile } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { money } from '@/lib/format';
import { useBreakpoint } from '@/theme/useBreakpoint';
import { colors, roles, spacing } from '@/theme/tokens';

const FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'Spending', value: 'outflow' },
  { label: 'Income', value: 'inflow' },
  { label: 'Recurring', value: 'recurring' },
  { label: 'Pending', value: 'pending' },
] as const;

export default function TransactionsScreen() {
  useEffect(() => setAssistantSection('money'), []);
  const { compact } = useBreakpoint();
  const [search, setSearch] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]['value']>('all');
  const query = useQuery({
    queryKey: ['money-transactions'],
    queryFn: () => api.moneyTransactions('?limit=500'),
  });
  const transactions = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (query.data?.items ?? []).filter((transaction) => {
      const searchMatch =
        !needle ||
        transaction.merchant_name.toLowerCase().includes(needle) ||
        transaction.description.toLowerCase().includes(needle) ||
        transaction.category.toLowerCase().includes(needle);
      const filterMatch =
        filter === 'all' ||
        (filter === 'outflow' &&
          transaction.direction === 'outflow' &&
          transaction.status === 'posted' &&
          !transaction.is_transfer) ||
        (filter === 'inflow' && transaction.direction === 'inflow' && !transaction.is_transfer) ||
        (filter === 'recurring' && transaction.is_recurring) ||
        (filter === 'pending' && transaction.status === 'pending');
      return searchMatch && filterMatch;
    });
  }, [filter, query.data, search]);
  const totalOutflow = transactions
    .filter(
      (transaction) =>
        transaction.direction === 'outflow' &&
        transaction.status === 'posted' &&
        !transaction.is_transfer,
    )
    .reduce((total, transaction) => total + Number(transaction.amount), 0);

  const searchBox = (
    <View style={[styles.searchBox, searchFocused && styles.searchBoxFocused, compact && styles.searchBoxCompact]}>
      <Search size={15} color={colors.inkFaint} />
      <TextInput
        value={search}
        onChangeText={setSearch}
        onFocus={() => setSearchFocused(true)}
        onBlur={() => setSearchFocused(false)}
        placeholder={compact ? 'Search merchant or category' : 'Merchant or category'}
        placeholderTextColor={colors.inkFaint}
        style={styles.searchInput}
      />
    </View>
  );

  return (
    <AppShell title="Transactions" eyebrow="SEARCHABLE ACTIVITY ACROSS ACCOUNTS">
      <View style={styles.summaryRow}>
        <StatTile label="VISIBLE ACTIVITY" value={String(transactions.length)} caption={`of ${query.data?.total ?? '—'} transactions`} />
        <StatTile label="VISIBLE OUTFLOWS" value={money(totalOutflow)} caption="Transfers excluded" />
        {!compact ? <StatTile label="DATA SOURCES" value="Plaid" caption="FinanceKit adapter planned" /> : null}
      </View>

      <Panel>
        <SectionHeader
          title="All activity"
          caption="Pending items may change when they post"
          action={!compact ? searchBox : undefined}
        />
        {compact ? <View style={styles.mobileSearchWrap}>{searchBox}</View> : null}
        <View style={styles.filters}>
          <SlidersHorizontal size={14} color={colors.inkMuted} />
          {FILTERS.map((item) => (
            <FilterChip key={item.value} label={item.label} active={filter === item.value} onPress={() => setFilter(item.value)} />
          ))}
        </View>
        {query.isLoading ? <LoadingState label="Loading transactions" /> : null}
        {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
        {query.data ? <TransactionList transactions={transactions} /> : null}
      </Panel>
    </AppShell>
  );
}

const styles = StyleSheet.create({
  summaryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  searchBox: {
    width: 230,
    height: 34,
    borderWidth: 1,
    borderColor: roles.borderHairline,
    backgroundColor: colors.canvas,
    paddingHorizontal: 9,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  searchBoxFocused: { outlineWidth: 2, outlineColor: roles.focusRing, outlineStyle: 'solid', outlineOffset: 2 } as never,
  searchBoxCompact: { width: 150 },
  mobileSearchWrap: { padding: spacing.sm, borderBottomWidth: 1, borderBottomColor: roles.borderHairline },
  searchInput: { flex: 1, color: colors.ink, fontSize: 11, outlineStyle: 'none' } as never,
  filters: {
    minHeight: 56,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 7,
    borderBottomWidth: 1,
    borderBottomColor: roles.borderHairline,
  },
});
