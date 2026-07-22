import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ArrowLeft, ExternalLink } from 'lucide-react-native';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { ErrorState, LevelPill, LoadingState } from '@/components/ui';
import { api } from '@/lib/api';
import { relativeTime } from '@/lib/format';
import { colors } from '@/theme/tokens';

export default function EventDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['event', id], queryFn: () => api.event(id), enabled: Boolean(id) });
  const markRead = useMutation({
    mutationFn: () => api.markRead(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['event', id] }),
        queryClient.invalidateQueries({ queryKey: ['feed'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      ]);
    },
  });

  return (
    <AppShell
      title="Event analysis"
      eyebrow="IMPACT DETAIL"
      headerAction={
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <ArrowLeft size={16} color={colors.ink} />
          <Text style={styles.backText}>Back</Text>
        </Pressable>
      }>
      {query.isLoading ? <LoadingState label="Loading event analysis" /> : null}
      {query.isError ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : null}
      {query.data ? (
        <View style={styles.layout}>
          <View style={styles.mainPanel}>
            <View style={styles.articleHeader}>
              <View style={styles.metaRow}>
                <LevelPill level={query.data.level} />
                <Text style={styles.metaText}>{relativeTime(query.data.occurred_at)}</Text>
                {query.data.is_demo ? <Text style={styles.demoText}>DEMO RECORD</Text> : null}
              </View>
              <Text style={styles.headline}>{query.data.headline}</Text>
              <Text style={styles.summary}>{query.data.summary}</Text>
              <View style={styles.sourceRow}>
                <Text style={styles.sourceLabel}>PRIMARY SOURCE</Text>
                <Text style={styles.sourceName}>{query.data.source_name}</Text>
                {query.data.source_url ? (
                  <Pressable onPress={() => Linking.openURL(query.data.source_url!)} style={styles.sourceLink}>
                    <ExternalLink size={13} color={colors.tealDark} />
                    <Text style={styles.sourceLinkText}>Open source</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
            <View style={styles.reasonSection}>
              <Text style={styles.sectionKicker}>WHY THIS MATTERS</Text>
              {query.data.reasons.map((reason, index) => (
                <View key={`${reason.code}-${index}`} style={styles.reasonRow}>
                  <Text style={styles.reasonIndex}>{String(index + 1).padStart(2, '0')}</Text>
                  <View style={styles.reasonCopy}>
                    <Text style={styles.reasonCode}>{reason.code.replaceAll('_', ' ').toUpperCase()}</Text>
                    <Text style={styles.reasonMessage}>{reason.message}</Text>
                  </View>
                </View>
              ))}
            </View>
          </View>
          <View style={styles.sidePanel}>
            <View style={styles.scoreCard}>
              <Text style={styles.scoreLabel}>PORTFOLIO IMPACT</Text>
              <Text style={styles.score}>{Math.round(Number(query.data.score))}</Text>
              <Text style={styles.scoreOutOf}>OUT OF 100</Text>
              <View style={styles.scoreTrack}>
                <View style={[styles.scoreFill, { width: `${Math.min(100, Number(query.data.score))}%` }]} />
              </View>
              <Text style={styles.confidence}>{Math.round(Number(query.data.confidence) * 100)}% source confidence</Text>
            </View>
            <View style={styles.exposureCard}>
              <Text style={styles.scoreLabel}>AFFECTED HOLDINGS</Text>
              {query.data.securities.map((security) => (
                <View key={security.security_id} style={styles.securityRow}>
                  <View>
                    <Text style={styles.securitySymbol}>{security.symbol}</Text>
                    <Text style={styles.securityName}>{security.name}</Text>
                  </View>
                  <Text style={styles.securityWeight}>{Number(security.effective_weight).toFixed(1)}%</Text>
                </View>
              ))}
            </View>
            {query.data.unread ? (
              <Pressable onPress={() => markRead.mutate()} style={styles.readButton}>
                <Text style={styles.readButtonText}>{markRead.isPending ? 'Updating…' : 'Mark as read'}</Text>
              </Pressable>
            ) : null}
          </View>
        </View>
      ) : null}
    </AppShell>
  );
}

const styles = StyleSheet.create({
  backButton: { height: 38, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center', gap: 7 },
  backText: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  layout: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-start', gap: 16 },
  mainPanel: { flex: 2, minWidth: 300, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  sidePanel: { flex: 1, minWidth: 270, gap: 12 },
  articleHeader: { padding: 24, borderBottomWidth: 1, borderBottomColor: colors.line },
  metaRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 9 },
  metaText: { color: colors.inkFaint, fontSize: 10 },
  demoText: { color: colors.tealDark, fontSize: 8, fontWeight: '800', letterSpacing: 0.8 },
  headline: { color: colors.ink, fontSize: 27, lineHeight: 35, fontWeight: '600', letterSpacing: -0.4, marginTop: 20 },
  summary: { color: colors.inkMuted, fontSize: 14, lineHeight: 23, marginTop: 17 },
  sourceRow: { marginTop: 25, paddingTop: 15, borderTopWidth: 1, borderTopColor: colors.line, flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 9 },
  sourceLabel: { color: colors.inkFaint, fontSize: 8, fontWeight: '800', letterSpacing: 0.9 },
  sourceName: { color: colors.ink, fontSize: 11, fontWeight: '600' },
  sourceLink: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 5 },
  sourceLinkText: { color: colors.tealDark, fontSize: 10, fontWeight: '700' },
  reasonSection: { padding: 24 },
  sectionKicker: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1.2, marginBottom: 5 },
  reasonRow: { paddingVertical: 17, borderBottomWidth: 1, borderBottomColor: colors.line, flexDirection: 'row', gap: 14 },
  reasonIndex: { color: colors.teal, fontSize: 11, fontWeight: '800', fontVariant: ['tabular-nums'] },
  reasonCopy: { flex: 1 },
  reasonCode: { color: colors.ink, fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
  reasonMessage: { color: colors.inkMuted, fontSize: 12, lineHeight: 18, marginTop: 6 },
  scoreCard: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.navy, padding: 20 },
  scoreLabel: { color: '#8F9BAA', fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  score: { color: colors.white, fontSize: 58, fontWeight: '600', marginTop: 14, fontVariant: ['tabular-nums'] },
  scoreOutOf: { color: '#8F9BAA', fontSize: 8, fontWeight: '800', letterSpacing: 0.8 },
  scoreTrack: { height: 4, backgroundColor: '#303D50', marginTop: 20 },
  scoreFill: { height: 4, backgroundColor: '#35BBB8' },
  confidence: { color: '#AEB7C3', fontSize: 10, marginTop: 12 },
  exposureCard: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, paddingTop: 18 },
  securityRow: { minHeight: 68, paddingHorizontal: 18, borderTopWidth: 1, borderTopColor: colors.line, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 15 },
  securitySymbol: { color: colors.ink, fontSize: 13, fontWeight: '800' },
  securityName: { color: colors.inkMuted, fontSize: 9, marginTop: 3, maxWidth: 180 },
  securityWeight: { color: colors.tealDark, fontSize: 15, fontWeight: '700', fontVariant: ['tabular-nums'] },
  readButton: { height: 44, backgroundColor: colors.teal, alignItems: 'center', justifyContent: 'center' },
  readButtonText: { color: colors.white, fontSize: 11, fontWeight: '700' },
});

