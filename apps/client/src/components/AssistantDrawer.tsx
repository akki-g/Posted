import { Sparkles, X } from 'lucide-react-native';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AssistantChat } from '@/components/AssistantChat';
import type { AssistantSection } from '@/lib/assistantSection';
import { colors, radius } from '@/theme/tokens';

type Props = {
  contextLabel: string;
  initialSection: AssistantSection;
  onClose: () => void;
  screenContext: string;
};

export function AssistantDrawer({
  contextLabel,
  initialSection,
  onClose,
  screenContext,
}: Props) {
  const { width } = useWindowDimensions();
  const desktop = width >= 920;

  return (
    <View style={styles.overlay}>
      <Pressable
        accessible={false}
        onPress={onClose}
        style={styles.backdrop}
      />
      <View
        accessibilityViewIsModal
        style={[styles.drawer, desktop ? styles.drawerDesktop : styles.drawerMobile]}>
        <View style={styles.header}>
          <View style={styles.headerIcon}>
            <Sparkles size={18} color={colors.tealDark} />
          </View>
          <View style={styles.headerCopy}>
            <View style={styles.titleRow}>
              <Text style={styles.title}>Ask Posted</Text>
              <View style={styles.contextBadge}>
                <Text style={styles.contextBadgeText}>SCREEN-AWARE</Text>
              </View>
            </View>
            <Text style={styles.contextLabel} numberOfLines={1}>
              Context: {contextLabel}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Close Ask Posted"
            onPress={onClose}
            style={styles.closeButton}>
            <X size={18} color={colors.inkMuted} />
          </Pressable>
        </View>
        <AssistantChat
          compact
          initialSection={initialSection}
          screenContext={screenContext}
        />
        <Text style={styles.disclaimer}>
          Explanations are informational. Posted cannot place trades or guarantee outcomes.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    zIndex: 3000,
    pointerEvents: 'box-none',
  },
  backdrop: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    backgroundColor: 'rgba(14, 25, 43, 0.32)',
  },
  drawer: {
    position: 'absolute',
    backgroundColor: colors.surface,
    borderColor: colors.line,
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 24,
    shadowOffset: { width: -6, height: 0 },
    elevation: 18,
    overflow: 'hidden',
  },
  drawerDesktop: {
    top: 0,
    right: 0,
    bottom: 0,
    width: 420,
    borderLeftWidth: 1,
  },
  drawerMobile: {
    top: 56,
    right: 0,
    bottom: 0,
    left: 0,
    borderTopWidth: 1,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    shadowOffset: { width: 0, height: -6 },
  },
  header: {
    minHeight: 72,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  headerIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerCopy: { flex: 1, minWidth: 0 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { color: colors.ink, fontSize: 16, fontWeight: '700' },
  contextBadge: {
    borderRadius: 10,
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  contextBadgeText: {
    color: colors.tealDark,
    fontSize: 7,
    fontWeight: '900',
    letterSpacing: 0.7,
  },
  contextLabel: { color: colors.inkMuted, fontSize: 10, marginTop: 3 },
  closeButton: {
    width: 36,
    height: 36,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disclaimer: {
    color: colors.inkFaint,
    backgroundColor: colors.canvas,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    fontSize: 9,
    lineHeight: 13,
    paddingHorizontal: 14,
    paddingVertical: 7,
    textAlign: 'center',
  },
});
