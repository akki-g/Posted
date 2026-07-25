import { useQuery } from '@tanstack/react-query';
import { Search, SlidersHorizontal } from 'lucide-react-native';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, useWindowDimensions, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { TransactionList } from '@/components/MoneyLists';
import { ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { money } from '@/lib/format';
import { colors } from '@/theme/tokens';

const FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'Spending', value: 'outflow' },
  { label: 'Income', value: 'inflow' },
  { label: 'Recurring', value: 'recurring' },
  { label: 'Pending', value: 'pending' },
] as const;

export default function TransactionsScreen() {
  useEffect(() => setAssistantSection('money'), []);
  const { width } = useWindowDimensions();
  const compact = width < 680;
  const [search, setSearch] = useState('');
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

  return (
    <AppShell title="Transactions" eyebrow="SEARCHABLE ACTIVITY ACROSS ACCOUNTS">
      <View style={styles.summaryRow}>
        <View style={[styles.summaryTile, compact && styles.summaryTileCompact]}>
          <Text style={styles.summaryLabel}>VISIBLE ACTIVITY</Text>
          <Text style={styles.summaryValue}>{transactions.length}</Text>
          <Text style={styles.summaryCaption}>of {query.data?.total ?? '—'} transactions</Text>
        </View>
        <View style={[styles.summaryTile, compact && styles.summaryTileCompact]}>
          <Text style={styles.summaryLabel}>VISIBLE OUTFLOWS</Text>
          <Text style={styles.summaryValue}>{money(totalOutflow)}</Text>
          <Text style={styles.summaryCaption}>Transfers excluded</Text>
        </View>
        {!compact ? (
          <View style={styles.summaryTile}>
            <Text style={styles.summaryLabel}>DATA SOURCES</Text>
            <Text style={styles.summaryValue}>Plaid</Text>
            <Text style={styles.summaryCaption}>FinanceKit adapter planned</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.panel}>
        <SectionHeader
          title="All activity"
          caption="Pending items may change when they post"
          action={!compact ? (
            <View style={[styles.searchBox, compact && styles.searchBoxCompact]}>
              <Search size={15} color={colors.inkFaint} />
              <TextInput
                value={search}
                onChangeText={setSearch}
                placeholder="Merchant or category"
                placeholderTextColor={colors.inkFaint}
                style={styles.searchInput}
              />
            </View>
          ) : undefined}
        />
        {compact ? (
          <View style={styles.mobileSearchWrap}>
            <View style={[styles.searchBox, styles.mobileSearchBox]}>
              <Search size={15} color={colors.inkFaint} />
              <TextInput
                value={search}
                onChangeText={setSearch}
                placeholder="Search merchant or category"
                placeholderTextColor={colors.inkFaint}
                style={styles.searchInput}
              />
            </View>
          </View>
        ) : null}
        <View style={styles.filters}>
          <SlidersHorizontal size={14} color={colors.inkMuted} />
          {FILTERS.map((item) => (
            <Pressable
              key={item.value}
              onPress={() => setFilter(item.value)}
              style={[styles.filter, filter === item.value && styles.filterActive]}>
              <Text style={[styles.filterText, filter === item.value && styles.filterTextActive]}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
        {query.isLoading ? <LoadingState label="Loading transactions" /> : null}
        {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
        {query.data ? <TransactionList transactions={transactions} /> : null}
      </View>
    </AppShell>
  );
}

const styles = StyleSheet.create({
  summaryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 1, backgroundColor: colors.line, marginBottom: 16 },
  summaryTile: { flex: 1, minWidth: 210, height: 112, padding: 17, backgroundColor: colors.surface },
  summaryTileCompact: { minWidth: 0, height: 104, padding: 14 },
  summaryLabel: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  summaryValue: { color: colors.ink, fontSize: 22, fontWeight: '700', marginTop: 14, fontVariant: ['tabular-nums'] },
  summaryCaption: { color: colors.inkMuted, fontSize: 10, marginTop: 5 },
  panel: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  searchBox: { width: 230, height: 34, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.canvas, paddingHorizontal: 9, flexDirection: 'row', alignItems: 'center', gap: 7 },
  searchBoxCompact: { width: 150 },
  mobileSearchWrap: { padding: 12, borderBottomWidth: 1, borderBottomColor: colors.line },
  mobileSearchBox: { width: '100%', height: 42, backgroundColor: colors.canvas },
  searchInput: { flex: 1, color: colors.ink, fontSize: 11, outlineStyle: 'none' } as never,
  filters: { minHeight: 56, paddingHorizontal: 16, paddingVertical: 10, flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 7, borderBottomWidth: 1, borderBottomColor: colors.line },
  filter: { height: 29, paddingHorizontal: 10, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  filterActive: { backgroundColor: colors.tealSoft, borderColor: '#A6D9D9' },
  filterText: { color: colors.inkMuted, fontSize: 9, fontWeight: '700' },
  filterTextActive: { color: colors.tealDark },
});
