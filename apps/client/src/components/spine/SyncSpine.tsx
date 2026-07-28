import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { relativeTime } from '@/lib/format';
import { colors, roles, spacing } from '@/theme/tokens';

export type SyncTick = {
  id: string;
  label: string;
  lastSyncedAt: string | null;
  accountCount: number;
  demo: boolean;
};

export type TickFreshness = 'fresh' | 'aging' | 'stale';

export function tickFreshness(tick: SyncTick): TickFreshness {
  if (tick.demo) return 'fresh';
  if (!tick.lastSyncedAt) return 'stale';
  const ageMinutes = (Date.now() - new Date(tick.lastSyncedAt).getTime()) / 60_000;
  if (ageMinutes < 15) return 'fresh';
  if (ageMinutes < 240) return 'aging';
  return 'stale';
}

const FRESHNESS_COLOR: Record<TickFreshness, string> = {
  fresh: colors.teal,
  aging: roles.stale,
  stale: colors.negative,
};

const FRESHNESS_LABEL: Record<TickFreshness, string> = {
  fresh: 'fresh',
  aging: 'aging',
  stale: 'stale',
};

/**
 * The signature interaction: one tick per connection, positioned/colored by
 * real sync recency (never decorative — see design/product-workflows.md
 * §4b for the "always-green dot" problem this replaces). Tapping a tick
 * expands what's actually known about that connection in place.
 */
export function SyncSpine({ ticks }: { ticks: SyncTick[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  if (ticks.length === 0) {
    return <Text style={styles.emptyText}>No connections yet — add one in Settings.</Text>;
  }
  const expanded = ticks.find((tick) => tick.id === expandedId);
  return (
    <View>
      <View style={styles.row}>
        {ticks.map((tick) => {
          const freshness = tickFreshness(tick);
          const color = FRESHNESS_COLOR[freshness];
          const isOpen = tick.id === expandedId;
          return (
            <Pressable
              key={tick.id}
              accessibilityRole="button"
              accessibilityLabel={`${tick.label}, ${tick.demo ? 'demo data' : FRESHNESS_LABEL[freshness]}, synced ${tick.lastSyncedAt ? relativeTime(tick.lastSyncedAt) : 'never'}`}
              accessibilityState={{ expanded: isOpen }}
              onPress={() => setExpandedId(isOpen ? null : tick.id)}
              style={({ pressed }) => [styles.tick, isOpen && styles.tickOpen, pressed && styles.tickPressed]}>
              <View style={[styles.tickMark, { backgroundColor: color }]} />
              <Text style={styles.tickLabel} numberOfLines={1}>
                {tick.label}
              </Text>
              <Text style={[styles.tickMeta, { color }]}>
                {tick.demo ? 'demo' : tick.lastSyncedAt ? relativeTime(tick.lastSyncedAt) : 'never'}
              </Text>
            </Pressable>
          );
        })}
      </View>
      {expanded ? (
        <View style={styles.detail}>
          <Text style={styles.detailText}>
            {expanded.label} · {expanded.accountCount} account{expanded.accountCount === 1 ? '' : 's'} ·{' '}
            {expanded.demo
              ? 'sample data, never syncs'
              : `${FRESHNESS_LABEL[tickFreshness(expanded)]} · last synced ${
                  expanded.lastSyncedAt ? relativeTime(expanded.lastSyncedAt) : 'never'
                }`}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  tick: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    height: 32,
    paddingHorizontal: 10,
    borderWidth: 1,
    borderColor: roles.borderHairline,
    backgroundColor: roles.surface,
  },
  tickOpen: { borderColor: roles.borderHairlineStrong },
  tickPressed: { backgroundColor: roles.surfaceSunken },
  tickMark: { width: 8, height: 8, borderRadius: 4 },
  tickLabel: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  tickMeta: { fontSize: 10, fontWeight: '600' },
  detail: {
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: 1,
    borderTopColor: roles.borderHairline,
  },
  detailText: { color: colors.inkMuted, fontSize: 11, lineHeight: 16 },
  emptyText: { color: colors.inkMuted, fontSize: 12 },
});
