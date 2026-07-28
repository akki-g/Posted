import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react-native';
import { useMemo, useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';

import { EventList } from '@/components/EventList';
import { ErrorState, FilterChip, LoadingState, Panel } from '@/components/ui';
import { api } from '@/lib/api';
import { colors, roles, spacing } from '@/theme/tokens';

const filters = ['all', 'urgent', 'important', 'notable'] as const;
type Filter = (typeof filters)[number];

// Extracted from the former app/feed.tsx. Renders without page chrome — the
// /portfolio container owns AppShell, the page header, and the tab row.
export function FeedTab() {
  const [filter, setFilter] = useState<Filter>('all');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const query = useQuery({
    queryKey: ['feed', filter, unreadOnly],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filter !== 'all') params.set('level', filter);
      if (unreadOnly) params.set('unread_only', 'true');
      const suffix = params.toString() ? `?${params}` : '';
      return api.feed(suffix);
    },
  });
  const events = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) return query.data?.items ?? [];
    return (query.data?.items ?? []).filter(
      (event) =>
        event.headline.toLowerCase().includes(normalized) ||
        event.securities.some((security) => security.symbol.toLowerCase().includes(normalized)),
    );
  }, [query.data, search]);

  return (
    <>
      <Text style={styles.intro}>
        Events ranked by materiality, portfolio exposure, source confidence, recency, and novelty.
      </Text>
      <View style={styles.toolbar}>
        <View style={[styles.searchBox, searchFocused && styles.searchBoxFocused]}>
          <Search size={16} color={colors.inkFaint} />
          <TextInput
            value={search}
            onChangeText={setSearch}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            placeholder="Search companies or headlines"
            placeholderTextColor={colors.inkFaint}
            style={styles.searchInput}
          />
        </View>
        <View style={styles.filterRow}>
          {filters.map((item) => (
            <FilterChip key={item} label={item.toUpperCase()} active={filter === item} onPress={() => setFilter(item)} />
          ))}
          <FilterChip label="UNREAD" active={unreadOnly} onPress={() => setUnreadOnly((value) => !value)} />
        </View>
      </View>
      <Panel style={styles.panel}>
        <View style={styles.resultHeader}>
          <Text style={styles.resultTitle}>{events.length} updates</Text>
          <Text style={styles.resultCaption}>Highest impact first</Text>
        </View>
        {query.isLoading ? <LoadingState label="Loading impact feed" /> : null}
        {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
        {query.data ? <EventList events={events} /> : null}
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  intro: { color: colors.inkMuted, fontSize: 13, lineHeight: 20, maxWidth: 720, marginBottom: 20 },
  toolbar: {
    borderWidth: 1,
    borderColor: roles.borderHairline,
    borderBottomWidth: 0,
    backgroundColor: colors.surface,
    padding: spacing.sm,
    gap: 10,
  },
  searchBox: {
    height: 42,
    borderWidth: 1,
    borderColor: roles.borderHairline,
    backgroundColor: colors.canvas,
    paddingHorizontal: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  searchBoxFocused: { outlineWidth: 2, outlineColor: roles.focusRing, outlineStyle: 'solid', outlineOffset: 2 } as never,
  searchInput: { flex: 1, color: colors.ink, fontSize: 13, outlineStyle: 'none' } as never,
  filterRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  panel: { borderTopWidth: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 },
  resultHeader: {
    minHeight: 52,
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: roles.borderHairline,
  },
  resultTitle: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  resultCaption: { color: colors.inkFaint, fontSize: 10 },
});
