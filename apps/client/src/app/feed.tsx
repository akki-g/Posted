import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react-native';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { EventList } from '@/components/EventList';
import { ErrorState, LoadingState } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { colors } from '@/theme/tokens';

const filters = ['all', 'urgent', 'important', 'notable'] as const;
type Filter = (typeof filters)[number];

export default function FeedScreen() {
  useEffect(() => setAssistantSection('investing'), []);
  const [filter, setFilter] = useState<Filter>('all');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [search, setSearch] = useState('');
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
    <AppShell title="Impact feed" eyebrow="PORTFOLIO INTELLIGENCE">
      <Text style={styles.intro}>
        Events ranked by materiality, portfolio exposure, source confidence, recency, and novelty.
      </Text>
      <View style={styles.toolbar}>
        <View style={styles.searchBox}>
          <Search size={16} color={colors.inkFaint} />
          <TextInput
            value={search}
            onChangeText={setSearch}
            placeholder="Search companies or headlines"
            placeholderTextColor={colors.inkFaint}
            style={styles.searchInput}
          />
        </View>
        <View style={styles.filterRow}>
          {filters.map((item) => (
            <Pressable
              key={item}
              onPress={() => setFilter(item)}
              style={[styles.filter, filter === item && styles.filterActive]}>
              <Text style={[styles.filterText, filter === item && styles.filterTextActive]}>
                {item.toUpperCase()}
              </Text>
            </Pressable>
          ))}
          <Pressable
            onPress={() => setUnreadOnly((value) => !value)}
            style={[styles.filter, unreadOnly && styles.filterActive]}>
            <Text style={[styles.filterText, unreadOnly && styles.filterTextActive]}>UNREAD</Text>
          </Pressable>
        </View>
      </View>
      <View style={styles.panel}>
        <View style={styles.resultHeader}>
          <Text style={styles.resultTitle}>{events.length} updates</Text>
          <Text style={styles.resultCaption}>Highest impact first</Text>
        </View>
        {query.isLoading ? <LoadingState label="Loading impact feed" /> : null}
        {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
        {query.data ? <EventList events={events} /> : null}
      </View>
    </AppShell>
  );
}

const styles = StyleSheet.create({
  intro: { color: colors.inkMuted, fontSize: 13, lineHeight: 20, maxWidth: 720, marginTop: -12, marginBottom: 20 },
  toolbar: {
    borderWidth: 1,
    borderColor: colors.line,
    borderBottomWidth: 0,
    backgroundColor: colors.surface,
    padding: 12,
    gap: 10,
  },
  searchBox: {
    height: 42,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.canvas,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  searchInput: { flex: 1, color: colors.ink, fontSize: 13, outlineStyle: 'none' } as never,
  filterRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  filter: {
    height: 31,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterActive: { borderColor: colors.navy, backgroundColor: colors.navy },
  filterText: { color: colors.inkMuted, fontSize: 9, fontWeight: '800', letterSpacing: 0.7 },
  filterTextActive: { color: colors.white },
  panel: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  resultHeader: {
    minHeight: 52,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  resultTitle: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  resultCaption: { color: colors.inkFaint, fontSize: 10 },
});

