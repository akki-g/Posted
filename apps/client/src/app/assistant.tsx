import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Send, Trash2 } from 'lucide-react-native';
import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { ErrorState, LoadingState } from '@/components/ui';
import { api } from '@/lib/api';
import { useAssistantSection, type AssistantSection } from '@/lib/assistantSection';
import { colors } from '@/theme/tokens';
import type { AssistantMessageSummary } from '@/lib/types';

const SECTION_OPTIONS: { label: string; value: AssistantSection }[] = [
  { label: 'General', value: 'general' },
  { label: 'Money', value: 'money' },
  { label: 'Investing', value: 'investing' },
];

export default function AssistantScreen() {
  const trackedSection = useAssistantSection();
  const [section, setSection] = useState<AssistantSection>(trackedSection);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState<AssistantMessageSummary[]>([]);
  const scrollRef = useRef<ScrollView>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    setSection(trackedSection);
  }, [trackedSection]);

  const conversation = useQuery({
    queryKey: ['assistant-messages'],
    queryFn: api.assistantConversation,
  });

  const send = useMutation({
    mutationFn: (message: string) => api.sendAssistantMessage(message, section),
    onMutate: async (message) => {
      setPending((current) => [
        ...current,
        {
          id: `local-${Date.now()}`,
          role: 'user',
          content: message,
          section,
          created_at: new Date().toISOString(),
        },
      ]);
    },
    onSuccess: async () => {
      setPending([]);
      await queryClient.invalidateQueries({ queryKey: ['assistant-messages'] });
    },
    onError: () => setPending([]),
  });

  const clear = useMutation({
    mutationFn: api.clearAssistantConversation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['assistant-messages'] });
    },
  });

  const messages = [...(conversation.data?.messages ?? []), ...pending];

  const submit = () => {
    const trimmed = draft.trim();
    if (!trimmed || send.isPending) return;
    setDraft('');
    send.mutate(trimmed);
  };

  return (
    <AppShell
      title="Assistant"
      eyebrow="AI · BUDGETING & INVESTING"
      headerAction={
        <Pressable
          onPress={() => clear.mutate()}
          disabled={clear.isPending || messages.length === 0}
          style={styles.clearButton}>
          <Trash2 size={15} color={colors.inkMuted} />
          <Text style={styles.clearText}>Clear</Text>
        </Pressable>
      }>
      <Text style={styles.intro}>
        Ask about your spending, subscriptions, portfolio, or recent market news — the assistant
        pulls your real account data live. It never places trades or recommends a specific buy or
        sell.
      </Text>

      <View style={styles.sectionRow}>
        {SECTION_OPTIONS.map((option) => (
          <Pressable
            key={option.value}
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

      <View style={styles.chatPanel}>
        <ScrollView
          ref={scrollRef}
          style={styles.messageScroll}
          contentContainerStyle={styles.messageScrollContent}
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}>
          {conversation.isLoading ? <LoadingState label="Loading conversation" /> : null}
          {conversation.isError ? (
            <ErrorState message={conversation.error.message} retry={() => conversation.refetch()} />
          ) : null}
          {messages.length === 0 && !conversation.isLoading ? (
            <Text style={styles.emptyText}>
              Ask something like "how much did I spend on subscriptions this month?" or "what's
              driving my portfolio today?"
            </Text>
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
                  message.role === 'user' ? styles.bubbleUser : styles.bubbleAssistant,
                ]}>
                <Text
                  style={[
                    styles.bubbleText,
                    message.role === 'user' && styles.bubbleTextUser,
                  ]}>
                  {message.content}
                </Text>
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

        <View style={styles.composer}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Ask about budgeting, spending, or your portfolio…"
            placeholderTextColor={colors.inkFaint}
            style={styles.input}
            onSubmitEditing={submit}
            returnKeyType="send"
          />
          <Pressable
            onPress={submit}
            disabled={send.isPending || !draft.trim()}
            style={[styles.sendButton, (send.isPending || !draft.trim()) && styles.sendButtonDisabled]}>
            <Send size={16} color={colors.white} />
          </Pressable>
        </View>
      </View>
    </AppShell>
  );
}

const styles = StyleSheet.create({
  intro: { color: colors.inkMuted, fontSize: 13, lineHeight: 20, maxWidth: 720, marginTop: -12 },
  sectionRow: { flexDirection: 'row', gap: 6, marginTop: 16, marginBottom: 4 },
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
    height: 38,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  clearText: { color: colors.inkMuted, fontSize: 11, fontWeight: '700' },
  chatPanel: {
    marginTop: 16,
    height: 560,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  messageScroll: { flex: 1 },
  messageScrollContent: { padding: 16, gap: 10, flexGrow: 1 },
  emptyText: { color: colors.inkFaint, fontSize: 12, lineHeight: 19, padding: 8 },
  messageRow: { flexDirection: 'row', marginBottom: 10 },
  messageRowUser: { justifyContent: 'flex-end' },
  messageRowAssistant: { justifyContent: 'flex-start' },
  bubble: { maxWidth: '75%', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 4 },
  bubbleUser: { backgroundColor: colors.teal },
  bubbleAssistant: { backgroundColor: colors.canvas, borderWidth: 1, borderColor: colors.line },
  bubbleText: { color: colors.ink, fontSize: 13, lineHeight: 20 },
  bubbleTextUser: { color: colors.white },
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
