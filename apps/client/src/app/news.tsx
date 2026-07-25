import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, RefreshCw, X } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { EventList } from '@/components/EventList';
import { ErrorState, LevelPill, LoadingState } from '@/components/ui';
import { api } from '@/lib/api';
import { setAssistantSection } from '@/lib/assistantSection';
import { relativeTime } from '@/lib/format';
import { colors } from '@/theme/tokens';

export default function NewsScreen() {
  useEffect(() => setAssistantSection('investing'), []);
  const { width } = useWindowDimensions();
  const desktop = width >= 920;
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const feed = useQuery({ queryKey: ['feed', 'news-tab'], queryFn: () => api.feed('?limit=100') });
  const detail = useQuery({
    queryKey: ['event', selectedId],
    queryFn: () => api.event(selectedId!),
    enabled: Boolean(selectedId),
  });
  const refreshNews = useMutation({
    mutationFn: api.refreshNews,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });

  const refresh = async () => {
    await refreshNews.mutateAsync();
    await feed.refetch();
  };

  return (
    <AppShell
      title="News stories"
      eyebrow="MARKET NEWS"
      onRefresh={() => void refresh()}
      refreshing={feed.isRefetching || refreshNews.isPending}>
      <Text style={styles.intro}>
        Every story feeding the impact feed. Click one for the full picture: an AI overview,
        what it means for your decisions, and its portfolio impact score.
      </Text>
      <View style={[styles.layout, !desktop && styles.stack]}>
        <View style={styles.listPanel}>
          <View style={styles.panelHeader}>
            <View>
              <Text style={styles.panelTitle}>{feed.data?.total ?? 0} stories</Text>
              <Text style={styles.panelCaption}>Highest impact first</Text>
            </View>
            <Pressable
              disabled={refreshNews.isPending}
              onPress={() => void refresh()}
              style={styles.refreshButton}>
              <RefreshCw size={13} color={colors.tealDark} />
              <Text style={styles.refreshText}>
                {refreshNews.isPending ? 'Refreshing…' : 'Refresh providers'}
              </Text>
            </Pressable>
          </View>
          {refreshNews.data ? (
            <Text style={styles.syncStatus}>
              {refreshNews.data.providers.length
                ? `${refreshNews.data.providers.join(' + ')} · ${refreshNews.data.fetched} fetched · ${refreshNews.data.inserted} new`
                : refreshNews.data.warnings[0] ?? 'No live news providers configured.'}
            </Text>
          ) : null}
          {refreshNews.isError ? (
            <Text style={styles.syncError}>{refreshNews.error.message}</Text>
          ) : null}
          {feed.isLoading ? <LoadingState label="Loading news" /> : null}
          {feed.isError ? (
            <ErrorState message={feed.error.message} retry={() => feed.refetch()} />
          ) : null}
          {feed.data ? (
            <EventList
              events={feed.data.items}
              onSelect={setSelectedId}
              selectedId={selectedId ?? undefined}
            />
          ) : null}
        </View>

        {selectedId ? (
          <View style={styles.detailPanel}>
            <View style={styles.detailHeaderRow}>
              <Text style={styles.detailKicker}>STORY DETAIL</Text>
              <Pressable onPress={() => setSelectedId(null)} style={styles.closeButton}>
                <X size={16} color={colors.inkMuted} />
              </Pressable>
            </View>
            <View style={styles.detailBody}>
              {detail.isLoading ? <LoadingState label="Loading story" /> : null}
              {detail.isError ? (
                <ErrorState message={detail.error.message} retry={() => detail.refetch()} />
              ) : null}
              {detail.data ? (
                <>
                  <View style={styles.metaRow}>
                    <LevelPill level={detail.data.level} />
                    <Text style={styles.metaText}>{relativeTime(detail.data.occurred_at)}</Text>
                  </View>
                  <Text style={styles.headline}>{detail.data.headline}</Text>
                  <Text style={styles.summary}>{detail.data.summary}</Text>

                  <View style={styles.scoreCard}>
                    <Text style={styles.scoreLabel}>PORTFOLIO IMPACT SCORE</Text>
                    <Text style={styles.score}>{Math.round(Number(detail.data.score))}</Text>
                    <View style={styles.scoreTrack}>
                      <View
                        style={[
                          styles.scoreFill,
                          { width: `${Math.min(100, Number(detail.data.score))}%` },
                        ]}
                      />
                    </View>
                  </View>

                  {detail.data.ai_insight ? (
                    <View style={styles.aiCard}>
                      <Text style={styles.aiKicker}>AI INSIGHT · WHAT THIS MEANS FOR YOU</Text>
                      <Text style={styles.aiText}>{detail.data.ai_insight}</Text>
                    </View>
                  ) : (
                    <View style={styles.aiCard}>
                      <Text style={styles.aiKicker}>AI INSIGHT</Text>
                      <Text style={styles.aiText}>
                        {detail.isFetching
                          ? 'Generating…'
                          : 'AI insight unavailable — add an Anthropic API key to enable this.'}
                      </Text>
                    </View>
                  )}

                  {detail.data.securities.length > 0 ? (
                    <View style={styles.holdingsSection}>
                      <Text style={styles.sectionKicker}>AFFECTED HOLDINGS</Text>
                      {detail.data.securities.map((security) => (
                        <View key={security.security_id} style={styles.holdingRow}>
                          <Text style={styles.holdingSymbol}>{security.symbol}</Text>
                          <Text style={styles.holdingWeight}>
                            {Number(security.effective_weight).toFixed(1)}% of portfolio
                          </Text>
                        </View>
                      ))}
                    </View>
                  ) : null}

                  <View style={styles.holdingsSection}>
                    <Text style={styles.sectionKicker}>WHY THIS SCORE</Text>
                    {detail.data.reasons.map((reason, index) => (
                      <Text key={`${reason.code}-${index}`} style={styles.reasonText}>
                        · {reason.message}
                      </Text>
                    ))}
                  </View>

                  <View style={styles.sourceRow}>
                    <Text style={styles.sourceName}>{detail.data.source_name}</Text>
                    {detail.data.source_url ? (
                      <Pressable
                        onPress={() => Linking.openURL(detail.data!.source_url!)}
                        style={styles.sourceLink}>
                        <ExternalLink size={13} color={colors.tealDark} />
                        <Text style={styles.sourceLinkText}>Open source</Text>
                      </Pressable>
                    ) : null}
                  </View>
                </>
              ) : null}
            </View>
          </View>
        ) : null}
      </View>
    </AppShell>
  );
}

const styles = StyleSheet.create({
  intro: {
    color: colors.inkMuted,
    fontSize: 13,
    lineHeight: 20,
    maxWidth: 720,
    marginTop: -12,
    marginBottom: 20,
  },
  layout: { flexDirection: 'row', gap: 16, alignItems: 'flex-start' },
  stack: { flexDirection: 'column' },
  listPanel: { flex: 1, minWidth: 300, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  panelHeader: {
    minHeight: 52,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  panelTitle: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  panelCaption: { color: colors.inkFaint, fontSize: 10, marginTop: 2 },
  refreshButton: {
    height: 31,
    borderWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: 9,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  refreshText: { color: colors.tealDark, fontSize: 9, fontWeight: '700' },
  syncStatus: {
    color: colors.tealDark,
    fontSize: 9,
    lineHeight: 14,
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 16,
    paddingVertical: 7,
  },
  syncError: {
    color: colors.negative,
    fontSize: 9,
    lineHeight: 14,
    backgroundColor: colors.negativeSoft,
    paddingHorizontal: 16,
    paddingVertical: 7,
  },
  detailPanel: {
    flex: 1,
    minWidth: 320,
    maxWidth: 460,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  detailHeaderRow: {
    minHeight: 52,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  detailKicker: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  closeButton: {
    width: 30,
    height: 30,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.line,
  },
  detailBody: { padding: 20 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  metaText: { color: colors.inkFaint, fontSize: 10 },
  headline: { color: colors.ink, fontSize: 19, lineHeight: 25, fontWeight: '600', marginTop: 12 },
  summary: { color: colors.inkMuted, fontSize: 13, lineHeight: 20, marginTop: 10 },
  scoreCard: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.navy,
    padding: 16,
    marginTop: 18,
  },
  scoreLabel: { color: '#8F9BAA', fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  score: { color: colors.white, fontSize: 36, fontWeight: '600', marginTop: 8, fontVariant: ['tabular-nums'] },
  scoreTrack: { height: 4, backgroundColor: '#303D50', marginTop: 12 },
  scoreFill: { height: 4, backgroundColor: '#35BBB8' },
  aiCard: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.tealSoft,
    padding: 16,
    marginTop: 12,
  },
  aiKicker: { color: colors.tealDark, fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  aiText: { color: colors.ink, fontSize: 13, lineHeight: 20, marginTop: 8 },
  holdingsSection: { marginTop: 18 },
  sectionKicker: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1.1, marginBottom: 8 },
  holdingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  holdingSymbol: { color: colors.ink, fontSize: 12, fontWeight: '700' },
  holdingWeight: { color: colors.inkMuted, fontSize: 11 },
  reasonText: { color: colors.inkMuted, fontSize: 12, lineHeight: 19, marginBottom: 4 },
  sourceRow: {
    marginTop: 20,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sourceName: { color: colors.inkMuted, fontSize: 11, fontWeight: '600' },
  sourceLink: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  sourceLinkText: { color: colors.tealDark, fontSize: 11, fontWeight: '700' },
});
