import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Send, Trash2 } from 'lucide-react-native';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { ErrorState, LoadingState } from '@/components/ui';
import { api } from '@/lib/api';
import { useAssistantSection, type AssistantSection } from '@/lib/assistantSection';
import type { AssistantMessageSummary } from '@/lib/types';
import { colors } from '@/theme/tokens';

const SECTION_OPTIONS: { label: string; value: AssistantSection }[] = [
  { label: 'General', value: 'general' },
  { label: 'Money', value: 'money' },
  { label: 'Investing', value: 'investing' },
];

type Props = {
  compact?: boolean;
  initialSection?: AssistantSection;
  screenContext?: string;
};

function suggestedPrompts(section: AssistantSection, screenContext?: string): string[] {
  if (section === 'money') {
    return [
      'What changed most in my spending?',
      'Which recurring charges need attention?',
      'How is my cash flow trending?',
    ];
  }
  if (section === 'investing') {
    const normalizedContext = screenContext?.toLowerCase() ?? '';
    if (
      normalizedContext.includes('reviewing insider activity') ||
      normalizedContext.includes('on the insider activity tracker')
    ) {
      return [
        'What does this insider signal mean?',
        'Are these trades actually meaningful?',
        'What could confirm or contradict this signal?',
      ];
    }
    return [
      'Why is this investment moving?',
      'What risks matter most right now?',
      'How should I interpret the insider activity?',
    ];
  }
  return [
    'What needs my attention today?',
    'Summarize what I am looking at.',
    'What should I investigate next?',
  ];
}

export function AssistantChat({ compact = false, initialSection, screenContext }: Props) {
  const trackedSection = useAssistantSection();
  const preferredSection = initialSection ?? trackedSection;
  const [section, setSection] = useState<AssistantSection>(preferredSection);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState<AssistantMessageSummary[]>([]);
  const scrollRef = useRef<ScrollView>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    setSection(preferredSection);
  }, [preferredSection]);

  const conversation = useQuery({
    queryKey: ['assistant-messages'],
    queryFn: api.assistantConversation,
  });

  const send = useMutation({
    mutationFn: (message: string) => api.sendAssistantMessage(message, section, screenContext),
    onMutate: async (message) => {
      setPending((current) => [
        ...current,
        {
          id: `local-${Date.now()}`,
          role: 'user',
          content: message,
          section,
          sources: null,
          created_at: new Date().toISOString(),
        },
      ]);
    },
    onSuccess: async () => {
      setPending([]);
      await queryClient.invalidateQueries({ queryKey: ['assistant-messages'] });
    },
    onError: (_error, message) => {
      setPending([]);
      setDraft((current) => current || message);
    },
  });

  const clear = useMutation({
    mutationFn: api.clearAssistantConversation,
    onSuccess: async () => {
      setPending([]);
      await queryClient.invalidateQueries({ queryKey: ['assistant-messages'] });
    },
  });

  const messages = [...(conversation.data?.messages ?? []), ...pending];
  const prompts = useMemo(
    () => suggestedPrompts(section, screenContext),
    [screenContext, section],
  );

  const submit = () => {
    const trimmed = draft.trim();
    if (!trimmed || send.isPending) return;
    setDraft('');
    send.mutate(trimmed);
  };

  return (
    <View style={[styles.container, compact && styles.containerCompact]}>
      <View style={[styles.introRow, compact && styles.introRowCompact]}>
        <Text style={[styles.intro, compact && styles.introCompact]}>
          {compact
            ? 'Ask about this screen, your accounts, or the market. Posted will fetch current facts before explaining them.'
            : 'Ask about your spending, subscriptions, portfolio, or recent market news. Posted pulls your account data and current market context live, but never places trades.'}
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Clear assistant conversation"
          onPress={() => clear.mutate()}
          disabled={clear.isPending || messages.length === 0}
          style={[
            styles.clearButton,
            (clear.isPending || messages.length === 0) && styles.clearButtonDisabled,
          ]}>
          <Trash2 size={14} color={colors.inkMuted} />
          {!compact ? <Text style={styles.clearText}>Clear</Text> : null}
        </Pressable>
      </View>

      <View style={styles.sectionRow}>
        {SECTION_OPTIONS.map((option) => (
          <Pressable
            key={option.value}
            accessibilityRole="button"
            accessibilityState={{ selected: section === option.value }}
            onPress={() => setSection(option.value)}
            style={[styles.sectionPill, section === option.value && styles.sectionPillActive]}>
            <Text
              style={[
                styles.sectionPillText,
                section === option.value && styles.sectionPillTextActive,
              ]}>
              {option.label.toUpperCase()}
            </Text>
          </Pressable>
        ))}
      </View>

      <View style={[styles.chatPanel, compact && styles.chatPanelCompact]}>
        <ScrollView
          ref={scrollRef}
          style={styles.messageScroll}
          contentContainerStyle={[
            styles.messageScrollContent,
            compact && styles.messageScrollContentCompact,
          ]}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}>
          {conversation.isLoading ? <LoadingState label="Loading conversation" /> : null}
          {conversation.isError ? (
            <ErrorState message={conversation.error.message} retry={() => conversation.refetch()} />
          ) : null}
          {messages.length === 0 && !conversation.isLoading ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>Start with what is on your screen</Text>
              <Text style={styles.emptyText}>
                The assistant knows which page you opened it from and can use live tools to answer
                follow-up questions.
              </Text>
              <View style={styles.promptList}>
                {prompts.map((prompt) => (
                  <Pressable
                    key={prompt}
                    accessibilityRole="button"
                    accessibilityLabel={`Use suggested question: ${prompt}`}
                    onPress={() => setDraft(prompt)}
                    style={styles.prompt}>
                    <Text style={styles.promptText}>{prompt}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ) : null}
          {messages.map((message) => (
            <View
              key={message.id}
              style={[
                styles.messageRow,
                message.role === 'user' ? styles.messageRowUser : styles.messageRowAssistant,
              ]}>
              <View
                style={[
                  styles.bubble,
                  compact && styles.bubbleCompact,
                  message.role === 'user' ? styles.bubbleUser : styles.bubbleAssistant,
                ]}>
                <Text
                  style={[
                    styles.bubbleText,
                    message.role === 'user' && styles.bubbleTextUser,
                  ]}>
                  {message.content}
                </Text>
                {message.sources && message.sources.length > 0 ? (
                  <View style={styles.sourcesBlock}>
                    <Text style={styles.sourcesLabel}>SOURCES</Text>
                    {message.sources.map((source) => (
                      <Pressable
                        key={source.url}
                        accessibilityRole="link"
                        onPress={() => Linking.openURL(source.url)}
                        style={styles.sourceLink}>
                        <ExternalLink size={11} color={colors.tealDark} />
                        <Text style={styles.sourceLinkText} numberOfLines={1}>
                          {source.title}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                ) : null}
              </View>
            </View>
          ))}
          {send.isPending ? (
            <View style={[styles.messageRow, styles.messageRowAssistant]}>
              <View style={[styles.bubble, styles.bubbleAssistant]}>
                <Text style={styles.bubbleText}>Thinking…</Text>
              </View>
            </View>
          ) : null}
        </ScrollView>

        {send.isError ? (
          <Text style={styles.sendError}>
            That message did not send. Your question is still in the composer.
          </Text>
        ) : null}

        <View style={styles.composer}>
          <TextInput
            accessibilityLabel="Ask Posted a question"
            value={draft}
            onChangeText={setDraft}
            placeholder={
              compact
                ? 'Ask about what you are viewing…'
                : 'Ask about budgeting, spending, or your portfolio…'
            }
            placeholderTextColor={colors.inkFaint}
            style={styles.input}
            onSubmitEditing={submit}
            returnKeyType="send"
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Send message"
            onPress={submit}
            disabled={send.isPending || !draft.trim()}
            style={[
              styles.sendButton,
              (send.isPending || !draft.trim()) && styles.sendButtonDisabled,
            ]}>
            <Send size={16} color={colors.white} />
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { width: '100%' },
  containerCompact: { flex: 1, minHeight: 0 },
  introRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 16,
  },
  introRowCompact: { paddingHorizontal: 16, paddingTop: 14 },
  intro: { color: colors.inkMuted, fontSize: 13, lineHeight: 20, maxWidth: 720 },
  introCompact: { flex: 1, fontSize: 11, lineHeight: 17 },
  sectionRow: { flexDirection: 'row', gap: 6, marginTop: 14, marginBottom: 4 },
  sectionPill: {
    height: 30,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sectionPillActive: { borderColor: colors.navy, backgroundColor: colors.navy },
  sectionPillText: { color: colors.inkMuted, fontSize: 9, fontWeight: '800', letterSpacing: 0.6 },
  sectionPillTextActive: { color: colors.white },
  clearButton: {
    minWidth: 38,
    height: 34,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
  },
  clearButtonDisabled: { opacity: 0.45 },
  clearText: { color: colors.inkMuted, fontSize: 11, fontWeight: '700' },
  chatPanel: {
    marginTop: 16,
    height: 560,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  chatPanelCompact: {
    flex: 1,
    height: undefined,
    minHeight: 0,
    marginTop: 10,
    borderWidth: 0,
    borderTopWidth: 1,
  },
  messageScroll: { flex: 1 },
  messageScrollContent: { padding: 16, gap: 10, flexGrow: 1 },
  messageScrollContentCompact: { paddingHorizontal: 14, paddingVertical: 16 },
  emptyState: { padding: 4 },
  emptyTitle: { color: colors.ink, fontSize: 14, fontWeight: '700', marginBottom: 6 },
  emptyText: { color: colors.inkFaint, fontSize: 12, lineHeight: 18 },
  promptList: { gap: 7, marginTop: 14 },
  prompt: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 4,
    backgroundColor: colors.canvas,
    paddingHorizontal: 11,
    paddingVertical: 9,
  },
  promptText: { color: colors.tealDark, fontSize: 11, lineHeight: 16, fontWeight: '600' },
  messageRow: { flexDirection: 'row', marginBottom: 10 },
  messageRowUser: { justifyContent: 'flex-end' },
  messageRowAssistant: { justifyContent: 'flex-start' },
  bubble: { maxWidth: '75%', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 4 },
  bubbleCompact: { maxWidth: '88%' },
  bubbleUser: { backgroundColor: colors.teal },
  bubbleAssistant: { backgroundColor: colors.canvas, borderWidth: 1, borderColor: colors.line },
  bubbleText: { color: colors.ink, fontSize: 13, lineHeight: 20 },
  bubbleTextUser: { color: colors.white },
  sourcesBlock: {
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    gap: 4,
  },
  sourcesLabel: { color: colors.inkFaint, fontSize: 8, fontWeight: '800', letterSpacing: 0.9 },
  sourceLink: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  sourceLinkText: { color: colors.tealDark, fontSize: 10, fontWeight: '700', flexShrink: 1 },
  sendError: {
    color: colors.negative,
    fontSize: 10,
    lineHeight: 14,
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  input: {
    flex: 1,
    height: 42,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.canvas,
    paddingHorizontal: 12,
    color: colors.ink,
    fontSize: 13,
    outlineStyle: 'none',
  } as never,
  sendButton: {
    width: 42,
    height: 42,
    backgroundColor: colors.teal,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonDisabled: { opacity: 0.5 },
});
