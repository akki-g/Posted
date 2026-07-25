import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react-native';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { HoldingsList } from '@/components/HoldingsList';
import { MarketSearch } from '@/components/MarketSearch';
import { ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { money } from '@/lib/format';
import { colors } from '@/theme/tokens';

export default function HoldingsScreen() {
  useEffect(() => setAssistantSection('investing'), []);
  const [search, setSearch] = useState('');
  const query = useQuery({ queryKey: ['holdings'], queryFn: api.holdings });
  const holdings = useMemo(() => {
    const value = search.trim().toLowerCase();
    if (!value) return query.data ?? [];
    return (query.data ?? []).filter(
      (holding) =>
        holding.symbol.toLowerCase().includes(value) || holding.name.toLowerCase().includes(value),
    );
  }, [query.data, search]);
  const invested = (query.data ?? [])
    .filter((item) => item.asset_type !== 'cash')
    .reduce((total, item) => total + Number(item.market_value), 0);

  return (
    <AppShell title="Holdings" eyebrow="POSITIONS ACROSS ALL ACCOUNTS">
      <MarketSearch />
      <View style={styles.summaryRow}>
        <View style={styles.summaryTile}>
          <Text style={styles.summaryLabel}>INVESTED ASSETS</Text>
          <Text style={styles.summaryValue}>{money(invested)}</Text>
        </View>
        <View style={styles.summaryTile}>
          <Text style={styles.summaryLabel}>SECURITIES</Text>
          <Text style={styles.summaryValue}>{query.data?.length ?? '—'}</Text>
        </View>
        <View style={styles.summaryTile}>
          <Text style={styles.summaryLabel}>LARGEST POSITION</Text>
          <Text style={styles.summaryValue}>{query.data?.[0]?.symbol ?? '—'}</Text>
          <Text style={styles.summaryCaption}>{query.data?.[0] ? `${Number(query.data[0].portfolio_weight).toFixed(1)}% of portfolio` : ''}</Text>
        </View>
      </View>
      <View style={styles.panel}>
        <SectionHeader
          title="All securities"
          caption="Aggregated across brokerage accounts"
          action={
            <View style={styles.searchBox}>
              <Search size={15} color={colors.inkFaint} />
              <TextInput
                value={search}
                onChangeText={setSearch}
                placeholder="Search"
                placeholderTextColor={colors.inkFaint}
                style={styles.searchInput}
              />
            </View>
          }
        />
        {query.isLoading ? <LoadingState label="Loading holdings" /> : null}
        {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
        {query.data ? <HoldingsList holdings={holdings} /> : null}
      </View>
    </AppShell>
  );
}

const styles = StyleSheet.create({
  summaryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 1, backgroundColor: colors.line, marginBottom: 16 },
  summaryTile: { flex: 1, minWidth: 210, height: 112, padding: 17, backgroundColor: colors.surface },
  summaryLabel: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  summaryValue: { color: colors.ink, fontSize: 22, fontWeight: '700', marginTop: 14, fontVariant: ['tabular-nums'] },
  summaryCaption: { color: colors.inkMuted, fontSize: 10, marginTop: 5 },
  panel: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  searchBox: {
    width: 190,
    maxWidth: '100%',
    height: 34,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.canvas,
    paddingHorizontal: 9,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  searchInput: { flex: 1, color: colors.ink, fontSize: 11, outlineStyle: 'none' } as never,
});
