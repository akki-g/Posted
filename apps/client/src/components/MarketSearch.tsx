import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { ArrowRight, BriefcaseBusiness, Search, X } from 'lucide-react-native';
import { useEffect, useMemo, useState } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';

import { marketApi } from '@/lib/marketApi';
import { symbolColor } from '@/lib/symbolColor';
import { colors } from '@/theme/tokens';

export function MarketSearch({
  compact = false,
  initialValue = '',
  destination = 'stock',
}: {
  compact?: boolean;
  initialValue?: string;
  destination?: 'stock' | 'insiders';
}) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const stacked = width < 720 && !compact;
  const mobileCompact = width < 760 && compact;
  const [value, setValue] = useState(initialValue);
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    setValue(initialValue);
    setQuery(initialValue.trim());
  }, [initialValue]);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(value.trim()), 240);
    return () => clearTimeout(timer);
  }, [value]);

  const results = useQuery({
    queryKey: ['market-search', query.toLowerCase()],
    queryFn: () => marketApi.search(query),
    enabled: query.length > 0,
    staleTime: 5 * 60_000,
  });
  const visible = focused && query.length > 0;
  const exactSymbol = useMemo(
    () => results.data?.find((item) => item.symbol === query.toUpperCase()),
    [query, results.data],
  );

  const openSymbol = (symbol: string) => {
    setFocused(false);
    setValue(symbol);
    if (destination === 'insiders') {
      router.push({ pathname: '/portfolio', params: { tab: 'insiders', symbol } });
    } else {
      router.push({ pathname: '/stock/[symbol]', params: { symbol } });
    }
  };

  return (
    <View
      style={[
        styles.root,
        stacked && styles.rootStacked,
        compact && styles.rootCompact,
        mobileCompact && styles.rootMobileCompact,
      ]}>
      {!compact ? (
        <View style={styles.copy}>
          <Text style={styles.eyebrow}>STOCK RESEARCH</Text>
          <Text style={styles.title}>Look up any equity or ETF</Text>
          <Text style={styles.caption}>
            Search by ticker or company name, then open its price history, earnings, and news.
          </Text>
        </View>
      ) : null}
      <View
        style={[
          styles.searchWrap,
          stacked && styles.searchWrapStacked,
          compact && styles.searchWrapCompact,
        ]}>
        <View style={[styles.inputShell, focused && styles.inputShellFocused]}>
          <Search size={17} color={focused ? colors.teal : colors.inkFaint} />
          <TextInput
            accessibilityLabel="Search stocks"
            autoCapitalize="characters"
            autoCorrect={false}
            onBlur={() => setTimeout(() => setFocused(false), 180)}
            onChangeText={setValue}
            onFocus={() => setFocused(true)}
            onSubmitEditing={() => {
              const target = exactSymbol ?? results.data?.[0];
              if (target) openSymbol(target.symbol);
            }}
            placeholder={compact ? 'Search stocks' : 'Try AAPL or Microsoft'}
            placeholderTextColor={colors.inkFaint}
            returnKeyType="search"
            style={styles.input}
            value={value}
          />
          {value ? (
            <Pressable
              accessibilityLabel="Clear stock search"
              onPress={() => {
                setValue('');
                setQuery('');
              }}>
              <X size={16} color={colors.inkFaint} />
            </Pressable>
          ) : null}
        </View>
        {visible ? (
          <View style={styles.results}>
            {results.isLoading ? (
              <Text style={styles.stateText}>Searching market symbols…</Text>
            ) : null}
            {results.isError ? (
              <Text style={styles.errorText}>{results.error.message}</Text>
            ) : null}
            {results.data?.map((item) => {
              const { background, foreground } = symbolColor(item.symbol);
              return (
              <Pressable
                accessibilityRole="link"
                key={item.symbol}
                onPress={() => openSymbol(item.symbol)}
                style={({ pressed }) => [styles.resultRow, pressed && styles.resultPressed]}>
                <View style={[styles.symbolBadge, { backgroundColor: background }]}>
                  <Text style={[styles.symbolBadgeText, { color: foreground }]}>{item.symbol.slice(0, 2)}</Text>
                </View>
                <View style={styles.resultCopy}>
                  <View style={styles.resultTitleRow}>
                    <Text style={styles.symbol}>{item.symbol}</Text>
                    {item.in_portfolio ? (
                      <View style={styles.ownedPill}>
                        <BriefcaseBusiness size={10} color={colors.tealDark} />
                        <Text style={styles.ownedText}>OWNED</Text>
                      </View>
                    ) : null}
                  </View>
                  <Text numberOfLines={1} style={styles.name}>
                    {item.name}
                  </Text>
                </View>
                <View style={styles.resultMeta}>
                  <Text style={styles.exchange}>{item.exchange ?? item.asset_type}</Text>
                  <ArrowRight size={15} color={colors.inkFaint} />
                </View>
              </Pressable>
              );
            })}
            {!results.isLoading && results.data?.length === 0 ? (
              <Text style={styles.stateText}>No matching US equities or ETFs.</Text>
            ) : null}
          </View>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    position: 'relative',
    zIndex: 1100,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.navy,
    padding: 20,
    marginBottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 28,
  },
  rootCompact: {
    width: 290,
    maxWidth: '100%',
    borderWidth: 0,
    backgroundColor: colors.transparent,
    padding: 0,
    marginBottom: 0,
  },
  rootMobileCompact: { width: '100%' },
  rootStacked: { flexDirection: 'column', alignItems: 'stretch', gap: 16 },
  copy: { flex: 1, minWidth: 230 },
  eyebrow: {
    color: '#75D4D1',
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1.2,
  },
  title: { color: colors.white, fontSize: 18, fontWeight: '700', marginTop: 6 },
  caption: { color: '#AAB4C1', fontSize: 11, lineHeight: 16, marginTop: 5 },
  searchWrap: { width: '48%', minWidth: 280, position: 'relative', zIndex: 1110 },
  searchWrapStacked: { width: '100%', minWidth: 0 },
  searchWrapCompact: { width: '100%', minWidth: 0 },
  inputShell: {
    height: 44,
    borderWidth: 1,
    borderColor: '#455167',
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  inputShellFocused: { borderColor: colors.teal, borderWidth: 2 },
  input: {
    flex: 1,
    color: colors.ink,
    fontSize: 12,
    outlineStyle: 'none',
  } as never,
  results: {
    position: 'absolute',
    top: 48,
    left: 0,
    right: 0,
    zIndex: 1120,
    borderWidth: 1,
    borderColor: colors.lineStrong,
    backgroundColor: colors.surface,
    elevation: 8,
  },
  resultRow: {
    minHeight: 64,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  resultPressed: { backgroundColor: colors.tealSoft },
  symbolBadge: {
    width: 34,
    height: 34,
    borderRadius: 3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  symbolBadgeText: { fontSize: 10, fontWeight: '800' },
  resultCopy: { flex: 1, minWidth: 0 },
  resultTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  symbol: { color: colors.ink, fontSize: 12, fontWeight: '800' },
  name: { color: colors.inkMuted, fontSize: 10, marginTop: 3 },
  ownedPill: {
    height: 18,
    paddingHorizontal: 5,
    backgroundColor: colors.tealSoft,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  ownedText: { color: colors.tealDark, fontSize: 7, fontWeight: '800', letterSpacing: 0.5 },
  resultMeta: { alignItems: 'flex-end', gap: 5 },
  exchange: { color: colors.inkFaint, fontSize: 9 },
  stateText: { color: colors.inkMuted, fontSize: 11, padding: 16 },
  errorText: { color: colors.negative, fontSize: 11, padding: 16 },
});
