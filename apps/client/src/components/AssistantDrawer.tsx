import { Sparkles, X } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AssistantChat } from '@/components/AssistantChat';
import type { AssistantSection } from '@/lib/assistantSection';
import { breakpoints, colors, radius } from '@/theme/tokens';

type Props = {
  contextLabel: string;
  initialSection: AssistantSection;
  onClose: () => void;
  screenContext: string | (() => string);
};

export function AssistantDrawer({
  contextLabel,
  initialSection,
  onClose,
  screenContext,
}: Props) {
  const { width } = useWindowDimensions();
  const docked = width >= breakpoints.assistantDock;
  // Any width that shows AppShell's bottom tab bar must use the compact
  // variant, which floats above the bar instead of covering it.
  const compact = width < breakpoints.mobileNav;

  return (
    <View
      accessibilityLabel="Ask Posted contextual assistant"
      style={[
        styles.panel,
        docked
          ? styles.panelDocked
          : compact
            ? styles.panelFloatingCompact
            : styles.panelFloating,
      ]}>
      <View style={styles.header}>
        <View style={styles.headerIcon}>
          <Sparkles size={16} color={colors.tealDark} />
        </View>
        <View style={styles.headerCopy}>
          <View style={styles.titleRow}>
            <Text style={styles.title}>Ask Posted</Text>
            <View style={styles.contextBadge}>
              <View style={styles.contextDot} />
              <Text style={styles.contextBadgeText}>IN CONTEXT</Text>
            </View>
          </View>
          <Text style={styles.contextLabel} numberOfLines={1}>
            {contextLabel}
          </Text>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Close Ask Posted"
          onPress={onClose}
          style={({ pressed }) => [styles.closeButton, pressed && styles.closeButtonPressed]}>
          <X size={17} color={colors.inkMuted} />
        </Pressable>
      </View>
      <AssistantChat
        compact
        initialSection={initialSection}
        screenContext={screenContext}
      />
      <Text style={styles.disclaimer}>
        Informational only · Posted never places trades
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: colors.surface,
    borderColor: colors.line,
    zIndex: 3000,
    overflow: 'hidden',
  },
  panelDocked: {
    width: 360,
    minHeight: '100%',
    borderLeftWidth: 1,
  },
  panelFloating: {
    position: 'absolute',
    right: 18,
    bottom: 18,
    width: 372,
    height: '72%',
    maxHeight: 640,
    minHeight: 440,
    borderWidth: 1,
    borderRadius: radius.lg,
    shadowColor: '#07101E',
    shadowOpacity: 0.2,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 },
    elevation: 18,
  },
  panelFloatingCompact: {
    position: 'absolute',
    right: 10,
    bottom: 76,
    left: 10,
    height: '58%',
    minHeight: 360,
    maxHeight: 590,
    borderWidth: 1,
    borderRadius: radius.lg,
    shadowColor: '#07101E',
    shadowOpacity: 0.22,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 8 },
    elevation: 18,
  },
  header: {
    minHeight: 64,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    paddingHorizontal: 13,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  headerIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerCopy: { flex: 1, minWidth: 0 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  title: { color: colors.ink, fontSize: 14, fontWeight: '700' },
  contextBadge: {
    borderRadius: 10,
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 6,
    paddingVertical: 3,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  contextDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.positive },
  contextBadgeText: {
    color: colors.tealDark,
    fontSize: 7,
    fontWeight: '900',
    letterSpacing: 0.6,
  },
  contextLabel: { color: colors.inkMuted, fontSize: 9, marginTop: 3 },
  closeButton: {
    width: 32,
    height: 32,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeButtonPressed: { backgroundColor: colors.canvas },
  disclaimer: {
    color: colors.inkFaint,
    backgroundColor: colors.canvas,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    fontSize: 8,
    lineHeight: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
    textAlign: 'center',
  },
});
