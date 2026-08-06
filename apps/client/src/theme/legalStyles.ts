import { StyleSheet } from 'react-native';

import { colors, roles, spacing } from '@/theme/tokens';

/** Shared layout for the public legal pages (privacy.tsx, terms.tsx) — plain
 * prose screens with no design-system chrome beyond the app's typography. */
export const legalStyles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.canvas },
  rootContent: { flexGrow: 1, alignItems: 'center', padding: spacing.lg },
  page: { width: '100%', maxWidth: 640, paddingBottom: spacing.xxl },
  nav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.lg,
  },
  backLink: { paddingVertical: spacing.xs, paddingHorizontal: spacing.sm },
  backLinkText: { color: roles.accent, fontSize: 13, fontWeight: '700' },
  title: { color: colors.ink, marginTop: spacing.md },
  updated: { color: colors.inkFaint, fontSize: 12, marginTop: spacing.xs, marginBottom: spacing.lg },
  h2: {
    color: colors.ink,
    fontSize: 16,
    fontWeight: '700',
    marginTop: spacing.lg,
    marginBottom: spacing.xs,
  },
  paragraph: {
    color: colors.inkMuted,
    fontSize: 14,
    lineHeight: 21,
    marginBottom: spacing.sm,
  },
});
