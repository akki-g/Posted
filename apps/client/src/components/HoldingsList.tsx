import { useRouter } from 'expo-router';
import { ArrowUpRight } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { money, number, percent } from '@/lib/format';
import { symbolColor } from '@/lib/symbolColor';
import type { HoldingSummary } from '@/lib/types';
import { colors, radius } from '@/theme/tokens';

function AssetBadge({ symbol }: { symbol: string }) {
  if (symbol === 'CASH') {
    return (
      <View style={[styles.assetBadge, styles.assetBadgeCash]}>
        <Text style={[styles.assetBadgeText, { color: colors.inkMuted }]}>CA</Text>
      </View>
    );
  }
  const { background, foreground } = symbolColor(symbol);
  return (
    <View style={[styles.assetBadge, { backgroundColor: background }]}>
      <Text style={[styles.assetBadgeText, { color: foreground }]}>{symbol.slice(0, 2)}</Text>
    </View>
  );
}

export function HoldingsList({
  holdings,
  limit,
  compact = false,
}: {
  holdings: HoldingSummary[];
  limit?: number;
  compact?: boolean;
}) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const desktop = width >= 760;
  const visible = typeof limit === 'number' ? holdings.slice(0, limit) : holdings;

  if (!desktop) {
    return (
      <View>
        {visible.map((holding) => {
          const positive = Number(holding.day_change) >= 0;
          return (
            <Pressable
              accessibilityRole={holding.asset_type === 'cash' ? undefined : 'link'}
              key={holding.security_id}
              onPress={
                holding.asset_type === 'cash'
                  ? undefined
                  : () =>
                      router.push({
                        pathname: '/stock/[symbol]',
                        params: { symbol: holding.symbol },
                      })
              }
              style={styles.mobileRow}>
              <AssetBadge symbol={holding.symbol} />
              <View style={styles.mobileIdentity}>
                <Text style={styles.symbol}>{holding.symbol}</Text>
                <Text numberOfLines={1} style={styles.company}>{holding.name}</Text>
              </View>
              <View style={styles.mobileValue}>
                <Text style={styles.value}>{money(holding.market_value)}</Text>
                <Text style={[styles.delta, { color: positive ? colors.positive : colors.negative }]}>
                  {percent(holding.day_change_percent)}
                </Text>
              </View>
            </Pressable>
          );
        })}
      </View>
    );
  }

  return (
    <View>
      <View style={styles.tableHeader}>
        <Text style={[styles.columnHeader, styles.securityColumn]}>Security</Text>
        {!compact ? <Text style={[styles.columnHeader, styles.numberColumn]}>Quantity</Text> : null}
        {!compact ? <Text style={[styles.columnHeader, styles.numberColumn]}>Last price</Text> : null}
        <Text style={[styles.columnHeader, styles.numberColumn]}>Market value</Text>
        <Text style={[styles.columnHeader, styles.numberColumn]}>Today</Text>
        <Text style={[styles.columnHeader, styles.numberColumn]}>Weight</Text>
        <View style={styles.actionColumn} />
      </View>
      {visible.map((holding) => {
        const positive = Number(holding.day_change) >= 0;
        return (
          <Pressable
            accessibilityRole={holding.asset_type === 'cash' ? undefined : 'link'}
            key={holding.security_id}
            onPress={
              holding.asset_type === 'cash'
                ? undefined
                : () =>
                    router.push({
                      pathname: '/stock/[symbol]',
                      params: { symbol: holding.symbol },
                    })
            }
            style={({ pressed }) => [styles.tableRow, pressed && styles.rowPressed]}>
            <View style={[styles.identity, styles.securityColumn]}>
              <AssetBadge symbol={holding.symbol} />
              <View style={styles.identityText}>
                <Text style={styles.symbol}>{holding.symbol}</Text>
                <Text numberOfLines={1} style={styles.company}>{holding.name}</Text>
              </View>
            </View>
            {!compact ? (
              <Text style={[styles.cell, styles.numberColumn]}>{number(holding.quantity, 4)}</Text>
            ) : null}
            {!compact ? (
              <Text style={[styles.cell, styles.numberColumn]}>
                {holding.last_price ? money(holding.last_price) : '—'}
              </Text>
            ) : null}
            <Text style={[styles.cellStrong, styles.numberColumn]}>{money(holding.market_value)}</Text>
            <Text
              style={[
                styles.cellStrong,
                styles.numberColumn,
                { color: positive ? colors.positive : colors.negative },
              ]}>
              {percent(holding.day_change_percent)}
            </Text>
            <Text style={[styles.cell, styles.numberColumn]}>{Number(holding.portfolio_weight).toFixed(1)}%</Text>
            <View style={styles.actionColumn}>
              <ArrowUpRight size={15} color={colors.inkFaint} />
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  tableHeader: {
    height: 38,
    paddingHorizontal: 16,
    backgroundColor: colors.surfaceMuted,
    borderBottomWidth: 1,
    borderBottomColor: colors.lineStrong,
    flexDirection: 'row',
    alignItems: 'center',
  },
  columnHeader: { color: colors.inkMuted, fontSize: 9, fontWeight: '800', letterSpacing: 0.7 },
  securityColumn: { flex: 2.15, minWidth: 210 },
  numberColumn: { flex: 1, textAlign: 'right', fontVariant: ['tabular-nums'] },
  actionColumn: { width: 34, alignItems: 'flex-end' },
  tableRow: {
    minHeight: 62,
    paddingHorizontal: 16,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
  },
  rowPressed: { backgroundColor: '#F7F9FA' },
  identity: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  identityText: { flexShrink: 1 },
  assetBadge: {
    width: 34,
    height: 34,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetBadgeCash: { backgroundColor: colors.surfaceMuted },
  assetBadgeText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.3 },
  symbol: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  company: { color: colors.inkMuted, fontSize: 10, marginTop: 3 },
  cell: { color: colors.inkMuted, fontSize: 12 },
  cellStrong: { color: colors.ink, fontSize: 12, fontWeight: '600' },
  mobileRow: {
    minHeight: 68,
    paddingHorizontal: 14,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  mobileIdentity: { flex: 1, minWidth: 0 },
  mobileValue: { alignItems: 'flex-end' },
  value: { color: colors.ink, fontSize: 13, fontWeight: '700', fontVariant: ['tabular-nums'] },
  delta: { fontSize: 11, fontWeight: '700', marginTop: 4, fontVariant: ['tabular-nums'] },
});
