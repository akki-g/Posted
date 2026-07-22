import { useRouter } from 'expo-router';
import { ChevronRight } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { relativeTime } from '@/lib/format';
import type { EventSummary } from '@/lib/types';
import { colors } from '@/theme/tokens';
import { LevelPill } from './ui';

export function EventList({ events }: { events: EventSummary[] }) {
  const router = useRouter();
  return (
    <View>
      {events.map((event) => (
        <Pressable
          key={event.id}
          onPress={() => router.push({ pathname: '/event/[id]', params: { id: event.id } })}
          style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}>
          <View style={[styles.scoreRail, railStyle[event.level]]} />
          <View style={styles.body}>
            <View style={styles.metaRow}>
              <LevelPill level={event.level} />
              <Text style={styles.time}>{relativeTime(event.occurred_at)}</Text>
              {event.unread ? <View style={styles.unreadDot} /> : null}
            </View>
            <Text style={styles.headline}>{event.headline}</Text>
            <View style={styles.footerRow}>
              <Text style={styles.symbols}>{event.securities.map((item) => item.symbol).join(', ')}</Text>
              <Text style={styles.source}>{event.source_name}</Text>
            </View>
          </View>
          <View style={styles.scoreBlock}>
            <Text style={styles.score}>{Math.round(Number(event.score))}</Text>
            <Text style={styles.scoreLabel}>IMPACT</Text>
          </View>
          <ChevronRight size={17} color={colors.inkFaint} />
        </Pressable>
      ))}
    </View>
  );
}

const railStyle = StyleSheet.create({
  urgent: { backgroundColor: colors.negative },
  important: { backgroundColor: colors.warning },
  notable: { backgroundColor: colors.blue },
  informational: { backgroundColor: colors.inkFaint },
});

const styles = StyleSheet.create({
  row: {
    minHeight: 112,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    paddingRight: 14,
  },
  rowPressed: { backgroundColor: '#F8F9FA' },
  scoreRail: { width: 3, alignSelf: 'stretch' },
  body: { flex: 1, minWidth: 0, paddingHorizontal: 14, paddingVertical: 14 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  time: { color: colors.inkFaint, fontSize: 10 },
  unreadDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.teal },
  headline: { color: colors.ink, fontSize: 13, lineHeight: 18, fontWeight: '600', marginTop: 9 },
  footerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  symbols: { color: colors.tealDark, fontSize: 10, fontWeight: '800', letterSpacing: 0.4 },
  source: { color: colors.inkFaint, fontSize: 10, flexShrink: 1 },
  scoreBlock: { width: 52, alignItems: 'center' },
  score: { color: colors.ink, fontSize: 20, fontWeight: '700', fontVariant: ['tabular-nums'] },
  scoreLabel: { color: colors.inkFaint, fontSize: 7, fontWeight: '800', letterSpacing: 0.8, marginTop: 2 },
});

