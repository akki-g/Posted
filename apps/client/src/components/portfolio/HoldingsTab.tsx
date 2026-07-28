import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react-native';
import { useMemo, useState } from 'react';
import { StyleSheet, TextInput, View } from 'react-native';

import { HoldingsList } from '@/components/HoldingsList';
import { MarketSearch } from '@/components/MarketSearch';
import { ErrorState, LoadingState, Panel, SectionHeader, StatTile } from '@/components/ui';
import { api } from '@/lib/api';
import { money } from '@/lib/format';
import { colors, roles, spacing } from '@/theme/tokens';

// Extracted from the former app/holdings.tsx. Renders without page chrome — the
// /portfolio container owns AppShell, the page header, and the tab row.
export function HoldingsTab() {
  const [search, setSearch] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
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
    <>
      <MarketSearch />
      <View style={styles.summaryRow}>
        <StatTile label="INVESTED ASSETS" value={money(invested)} />
        <StatTile label="SECURITIES" value={String(query.data?.length ?? '—')} />
        <StatTile
          label="LARGEST POSITION"
          value={query.data?.[0]?.symbol ?? '—'}
          caption={query.data?.[0] ? `${Number(query.data[0].portfolio_weight).toFixed(1)}% of portfolio` : ''}
        />
      </View>
      <Panel>
        <SectionHeader
          title="All securities"
          caption="Aggregated across brokerage accounts"
          action={
            <View style={[styles.searchBox, searchFocused && styles.searchBoxFocused]}>
              <Search size={15} color={colors.inkFaint} />
              <TextInput
                value={search}
                onChangeText={setSearch}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setSearchFocused(false)}
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
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  summaryRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  searchBox: {
    width: 190,
    maxWidth: '100%',
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
  searchInput: { flex: 1, color: colors.ink, fontSize: 11, outlineStyle: 'none' } as never,
});
