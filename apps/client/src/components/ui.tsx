import { AlertCircle, RefreshCw, TrendingDown, TrendingUp, Unlink } from 'lucide-react-native';
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { colors, elevation, radius, roles, size, spacing, textStyle } from '@/theme/tokens';

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

const HIT_SLOP = (size.touchMin - size.controlSm) / 2;

/** Replaces the bordered/shadowed container previously retyped verbatim in 9+ screen files. */
export function Panel({
  children,
  variant = 'default',
  tone = 'neutral',
  style,
}: {
  children: ReactNode;
  variant?: 'default' | 'inverted';
  tone?: 'neutral' | 'stale' | 'demo';
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View
      style={[
        styles.panel,
        variant === 'inverted' && styles.panelInverted,
        tone === 'stale' && styles.panelStaleRule,
        tone === 'demo' && styles.panelDemoRule,
        style,
      ]}>
      {tone === 'demo' ? (
        <View style={styles.demoChip}>
          <Text style={styles.demoChipText}>DEMO</Text>
        </View>
      ) : null}
      {children}
    </View>
  );
}

function formatMasked(value: string): string {
  const trimmed = value.trim();
  const sign = trimmed.startsWith('+') || trimmed.startsWith('-') ? trimmed[0] : '';
  const rest = sign ? trimmed.slice(1) : trimmed;
  const currency = rest.startsWith('$') ? '$' : '';
  return `${sign}${currency}••••`;
}

/** Replaces the label/value/caption stat block independently reimplemented in 7+ screen files. */
export function StatTile({
  label,
  value,
  caption,
  tone = 'neutral',
  size: tileSize = 'default',
  masked = false,
}: {
  label: string;
  value: string;
  caption?: string;
  tone?: 'neutral' | 'positive' | 'negative';
  size?: 'default' | 'primary';
  masked?: boolean;
}) {
  const Icon = tone === 'positive' ? TrendingUp : tone === 'negative' ? TrendingDown : null;
  const toneColor = tone === 'positive' ? colors.positive : tone === 'negative' ? colors.negative : colors.ink;
  return (
    <View style={styles.statTile}>
      <Text style={styles.statLabel}>{label}</Text>
      <View style={styles.statValueRow}>
        {Icon ? <Icon size={tileSize === 'primary' ? 16 : 14} color={toneColor} /> : null}
        <Text
          numberOfLines={1}
          style={[
            styles.statValue,
            tileSize === 'primary' && styles.statValuePrimary,
            { color: toneColor },
          ]}>
          {masked ? formatMasked(value) : value}
        </Text>
      </View>
      {caption ? <Text style={styles.statCaption}>{caption}</Text> : null}
    </View>
  );
}

/** Replaces the 38x38/40x40 icon-only button drifting across 5+ screen files, all under the 44x44 touch-target floor. */
export function IconButton({
  icon,
  onPress,
  accessibilityLabel,
  active = false,
  disabled = false,
}: {
  icon: ReactNode;
  onPress: () => void;
  accessibilityLabel: string;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled, selected: active }}
      disabled={disabled}
      hitSlop={HIT_SLOP}
      onPress={onPress}
      style={({ pressed }) => [
        styles.iconButton,
        active && styles.iconButtonActive,
        pressed && styles.iconButtonPressed,
        disabled && styles.iconButtonDisabled,
      ]}>
      {icon}
    </Pressable>
  );
}

/** Replaces settings.tsx's ~90%-duplicated banking/investing connection row pair. */
export function ConnectionRow({
  name,
  meta,
  status,
  onSync,
  onUnlink,
  syncing = false,
  unlinking = false,
}: {
  name: string;
  meta: string;
  status: 'live' | 'stale' | 'demo' | 'error';
  onSync?: () => void;
  onUnlink?: () => void;
  syncing?: boolean;
  unlinking?: boolean;
}) {
  return (
    <View style={styles.connectionRow}>
      <View style={styles.connectionIdentity}>
        <Text style={styles.connectionName}>{name}</Text>
        <Text style={styles.connectionMeta}>{meta}</Text>
      </View>
      {status === 'demo' ? (
        <View style={styles.demoChip}>
          <Text style={styles.demoChipText}>DEMO</Text>
        </View>
      ) : (
        <View style={styles.connectionActions}>
          {status === 'stale' ? <View style={styles.staleDot} /> : null}
          {onSync ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Sync ${name}`}
              disabled={syncing}
              onPress={onSync}
              style={styles.syncButton}>
              <RefreshCw size={12} color={colors.tealDark} />
              <Text style={styles.syncButtonText}>{syncing ? 'SYNCING' : 'SYNC'}</Text>
            </Pressable>
          ) : null}
          {onUnlink ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Unlink ${name}`}
              disabled={unlinking}
              onPress={onUnlink}
              style={({ pressed }) => [styles.unlinkButton, pressed && styles.unlinkButtonPressed]}>
              <Unlink size={12} color={colors.negative} />
              <Text style={styles.unlinkButtonText}>{unlinking ? 'REMOVING' : 'UNLINK'}</Text>
            </Pressable>
          ) : null}
        </View>
      )}
    </View>
  );
}

/** Unifies feed.tsx's navy-fill filter chip and transactions.tsx's tealSoft-fill filter chip into one treatment (the latter, kept — navy fill collides with navy meaning "hero/summary panel" elsewhere). */
export function FilterChip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={[styles.filterChip, active && styles.filterChipActive]}>
      <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  panel: {
    borderWidth: 1,
    borderColor: roles.borderHairline,
    backgroundColor: roles.surface,
    borderRadius: radius.lg,
    overflow: 'hidden',
    ...elevation.raised,
  },
  panelInverted: {
    borderWidth: 0,
    backgroundColor: roles.surfaceInverted,
    borderRadius: radius.xl,
  },
  panelStaleRule: { borderTopWidth: 2, borderTopColor: roles.stale },
  panelDemoRule: { borderTopWidth: 2, borderTopColor: roles.demo },
  demoChip: {
    alignSelf: 'flex-start',
    margin: spacing.sm,
    backgroundColor: colors.tealDark,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  demoChipText: { color: colors.white, ...textStyle.label },
  statTile: { padding: spacing.md },
  statLabel: { color: roles.textTertiary, ...textStyle.labelWide },
  statValueRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: spacing.xs },
  statValue: { ...textStyle.statValue, fontVariant: ['tabular-nums'] },
  statValuePrimary: { ...textStyle.statValueLarge },
  statCaption: { color: roles.textSecondary, ...textStyle.caption, marginTop: 4 },
  iconButton: {
    width: size.controlSm,
    height: size.controlSm,
    borderWidth: 1,
    borderColor: roles.borderHairline,
    backgroundColor: roles.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.sm,
  },
  iconButtonActive: { backgroundColor: roles.accentSoft, borderColor: roles.accentSoftBorder },
  iconButtonPressed: { backgroundColor: roles.surfaceSunken },
  iconButtonDisabled: { opacity: 0.5 },
  connectionRow: {
    minHeight: 84,
    padding: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  connectionIdentity: { flex: 1, minWidth: 0 },
  connectionName: { color: roles.textPrimary, fontSize: 13, fontWeight: '700' },
  connectionMeta: { color: roles.textSecondary, fontSize: 10, marginTop: 5 },
  connectionActions: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  staleDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: roles.stale },
  syncButton: {
    paddingHorizontal: 9,
    height: 28,
    borderWidth: 1,
    borderColor: roles.accent,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  syncButtonText: { color: colors.tealDark, fontSize: 8, fontWeight: '800', letterSpacing: 0.7 },
  unlinkButton: {
    paddingHorizontal: 9,
    height: 28,
    borderWidth: 1,
    borderColor: roles.negative,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  unlinkButtonPressed: { opacity: 0.55, backgroundColor: 'rgba(0,0,0,0.03)' },
  unlinkButtonText: { color: colors.negative, fontSize: 8, fontWeight: '800', letterSpacing: 0.7 },
  filterChip: {
    height: 32,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderColor: roles.borderHairline,
    backgroundColor: roles.surface,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterChipActive: { backgroundColor: roles.accentSoft, borderColor: roles.accentSoftBorder },
  filterChipText: { color: roles.textSecondary, fontSize: 11, fontWeight: '600' },
  filterChipTextActive: { color: roles.accent },
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
