import type { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { useBreakpoint } from '@/theme/useBreakpoint';
import { colors, roles, spacing } from '@/theme/tokens';

/**
 * The Position Spine's primary band shape — full-width, no card boundary,
 * a fixed-width legend rail beside (desktop) or above (mobile) the content.
 * Deliberately not a `Panel`: bands are a flatter, second geometry reserved
 * for this one screen shape (see design/approved-design-system.md).
 */
export function Band({
  label,
  children,
  first = false,
}: {
  label: string;
  children: ReactNode;
  first?: boolean;
}) {
  const { desktop } = useBreakpoint();
  return (
    <View style={[styles.band, !first && styles.bandRule, desktop ? styles.bandRow : styles.bandColumn]}>
      <View style={desktop ? styles.legendRail : styles.legendRailCompact}>
        <Text style={styles.legendLabel}>{label}</Text>
      </View>
      <View style={styles.bandContent}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  band: { paddingVertical: spacing.md },
  bandRule: { borderTopWidth: 1, borderTopColor: roles.borderHairline },
  bandRow: { flexDirection: 'row', gap: spacing.lg },
  bandColumn: { flexDirection: 'column', gap: spacing.xs },
  legendRail: { width: 128, flexShrink: 0, paddingTop: 2 },
  legendRailCompact: {},
  legendLabel: {
    color: colors.inkFaint,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.4,
  },
  bandContent: { flex: 1, minWidth: 0 },
});
