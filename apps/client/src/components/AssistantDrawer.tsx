import { useRouter } from 'expo-router';
import { Maximize2, Sparkles, X } from 'lucide-react-native';
import { useEffect, useRef } from 'react';
import { Platform, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AssistantChat } from '@/components/AssistantChat';
import type { AssistantSection } from '@/lib/assistantSection';
import { breakpoints, colors, radius } from '@/theme/tokens';

type Props = {
  contextLabel: string;
  initialSection: AssistantSection;
  onClose: () => void;
  screenContext: string | (() => string);
};

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

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
  const router = useRouter();

  const panelRef = useRef<View>(null);
  const closeButtonRef = useRef<View>(null);

  // Web-only focus management: move focus in on open, trap Tab inside the
  // panel, close on Escape, and return focus to whatever opened the drawer.
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const closeNode = closeButtonRef.current as unknown as HTMLElement | null;
    closeNode?.focus?.();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const container = panelRef.current as unknown as HTMLElement | null;
      if (!container) return;
      const focusable = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused?.focus?.();
    };
    // Run once on mount/unmount only — re-running on every prop change would
    // re-steal focus away from wherever the user has since tabbed to.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const expand = () => {
    onClose();
    router.push({ pathname: '/assistant', params: { section: initialSection } });
  };

  return (
    <View
      ref={panelRef}
      accessibilityLabel="Ask Posted contextual assistant"
      accessibilityViewIsModal
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
        {!docked ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Expand to full assistant"
            onPress={expand}
            style={({ pressed }) => [styles.closeButton, pressed && styles.closeButtonPressed]}>
            <Maximize2 size={15} color={colors.inkMuted} />
          </Pressable>
        ) : null}
        <Pressable
          ref={closeButtonRef}
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
