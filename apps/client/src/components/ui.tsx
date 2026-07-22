import { AlertCircle, RefreshCw } from 'lucide-react-native';
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/theme/tokens';

export function SectionHeader({
  title,
  caption,
  action,
}: {
  title: string;
  caption?: string;
  action?: ReactNode;
}) {
  return (
    <View style={styles.sectionHeader}>
      <View style={styles.sectionHeading}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {caption ? <Text style={styles.sectionCaption}>{caption}</Text> : null}
      </View>
      {action}
    </View>
  );
}

export function ActionButton({
  label,
  onPress,
  icon,
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  icon?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.actionButton,
        disabled && styles.actionDisabled,
        pressed && styles.actionPressed,
      ]}>
      {icon}
      <Text style={styles.actionLabel}>{label}</Text>
    </Pressable>
  );
}

export function DemoBanner({
  message = 'Sample portfolio and events. Connect Schwab to replace this data.',
}: {
  message?: string;
}) {
  return (
    <View style={styles.demoBanner}>
      <View style={styles.demoBadge}>
        <Text style={styles.demoBadgeText}>DEMO</Text>
      </View>
      <Text style={styles.demoText}>{message}</Text>
    </View>
  );
}

export function LoadingState({ label = 'Loading portfolio' }: { label?: string }) {
  return (
    <View style={styles.stateBox}>
      <ActivityIndicator color={colors.teal} />
      <Text style={styles.stateText}>{label}</Text>
    </View>
  );
}

export function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return (
    <View style={styles.errorBox}>
      <AlertCircle size={22} color={colors.negative} />
      <View style={styles.errorCopy}>
        <Text style={styles.errorTitle}>Couldn’t reach the Posted API</Text>
        <Text style={styles.errorText}>{message}</Text>
      </View>
      <Pressable onPress={retry} style={styles.retryButton}>
        <RefreshCw size={15} color={colors.ink} />
        <Text style={styles.retryText}>Retry</Text>
      </Pressable>
    </View>
  );
}

export function LevelPill({ level }: { level: string }) {
  const palette =
    level === 'urgent'
      ? { background: colors.negativeSoft, foreground: colors.negative }
      : level === 'important'
        ? { background: colors.warningSoft, foreground: colors.warning }
        : level === 'notable'
          ? { background: colors.blueSoft, foreground: colors.blue }
          : { background: colors.surfaceMuted, foreground: colors.inkMuted };
  return (
    <View style={[styles.levelPill, { backgroundColor: palette.background }]}>
      <View style={[styles.levelDot, { backgroundColor: palette.foreground }]} />
      <Text style={[styles.levelText, { color: palette.foreground }]}>{level.toUpperCase()}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  sectionHeader: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 14,
    paddingHorizontal: 18,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  sectionHeading: { flexShrink: 1 },
  sectionTitle: { color: colors.ink, fontSize: 15, fontWeight: '700' },
  sectionCaption: { color: colors.inkMuted, fontSize: 11, marginTop: 3 },
  actionButton: {
    minHeight: 38,
    backgroundColor: colors.teal,
    paddingHorizontal: 14,
    borderRadius: 4,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  actionDisabled: { opacity: 0.55 },
  actionPressed: { backgroundColor: colors.tealDark },
  actionLabel: { color: colors.white, fontSize: 12, fontWeight: '700' },
  demoBanner: {
    minHeight: 42,
    borderWidth: 1,
    borderColor: '#A6D9D9',
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 13,
    paddingVertical: 9,
    marginBottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  demoBadge: { backgroundColor: colors.tealDark, paddingHorizontal: 6, paddingVertical: 3 },
  demoBadgeText: { color: colors.white, fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  demoText: { flex: 1, color: colors.tealDark, fontSize: 12, lineHeight: 17 },
  stateBox: {
    minHeight: 260,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  stateText: { color: colors.inkMuted, fontSize: 13 },
  errorBox: {
    minHeight: 130,
    borderWidth: 1,
    borderColor: '#E8B9BE',
    backgroundColor: colors.negativeSoft,
    padding: 18,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 13,
  },
  errorCopy: { flex: 1 },
  errorTitle: { color: colors.ink, fontSize: 14, fontWeight: '700' },
  errorText: { color: colors.inkMuted, fontSize: 12, marginTop: 4 },
  retryButton: {
    borderWidth: 1,
    borderColor: colors.lineStrong,
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    height: 36,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  retryText: { color: colors.ink, fontSize: 11, fontWeight: '700' },
  levelPill: {
    alignSelf: 'flex-start',
    height: 23,
    borderRadius: 2,
    paddingHorizontal: 7,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  levelDot: { width: 5, height: 5, borderRadius: 3 },
  levelText: { fontSize: 9, fontWeight: '800', letterSpacing: 0.7 },
});
