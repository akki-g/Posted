import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useEffect } from 'react';
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { BrandMark } from '@/components/BrandMark';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { useBreakpoint } from '@/theme/useBreakpoint';
import { colors, radius, roles, spacing, textStyle } from '@/theme/tokens';

const PREVIEW_HOLDINGS = [
  { symbol: 'AAPL', value: '$32,904.00', change: '+2.1%' },
  { symbol: 'MSFT', value: '$27,140.16', change: '+0.4%' },
  { symbol: 'GOOGL', value: '$19,880.00', change: '−0.6%' },
];

export default function LoginScreen() {
  const router = useRouter();
  const { desktop } = useBreakpoint();
  const { user } = useAuth();

  useEffect(() => {
    if (user) router.replace('/');
  }, [user, router]);

  const authorize = useMutation({
    mutationFn: api.authorizeGoogle,
    onSuccess: ({ authorization_url }) => {
      if (Platform.OS === 'web') window.location.href = authorization_url;
    },
  });

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.rootContent} showsVerticalScrollIndicator={false}>
      <View style={styles.page}>
        <View style={styles.nav}>
          <BrandMark />
        </View>

        <Text style={[textStyle.display, desktop && textStyle.displayDesktop, styles.headline]}>
          One statement for your cash and your portfolio.
        </Text>
        <Text style={styles.subheadline}>
          Posted syncs your bank and brokerage into a single record and answers questions
          against your real numbers — not general advice.
        </Text>

        <View style={styles.preview}>
          <View style={styles.previewHeader}>
            <Text style={styles.previewEyebrow}>WHAT YOU'LL SEE · EXAMPLE DATA</Text>
          </View>
          <View style={styles.previewRule}>
            <Text style={styles.previewLabel}>TOTAL NET WORTH</Text>
            <Text style={styles.previewValue}>$151,070.55</Text>
            <Text style={styles.previewCaption}>$142,830.44 invested · $8,240.11 cash</Text>
          </View>
          <View style={styles.previewRule}>
            <Text style={styles.previewLabel}>LARGEST HOLDINGS</Text>
            {PREVIEW_HOLDINGS.map((holding) => (
              <View key={holding.symbol} style={styles.previewRow}>
                <Text style={styles.previewSymbol}>{holding.symbol}</Text>
                <Text style={styles.previewRowValue}>{holding.value}</Text>
                <Text
                  style={[
                    styles.previewRowChange,
                    { color: holding.change.startsWith('−') ? colors.negative : colors.positive },
                  ]}>
                  {holding.change}
                </Text>
              </View>
            ))}
          </View>
        </View>

        <View style={styles.ctaBlock}>
          {Platform.OS === 'web' ? (
            <Pressable
              accessibilityRole="button"
              disabled={authorize.isPending}
              onPress={() => authorize.mutate()}
              style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}>
              <Text style={styles.buttonText}>
                {authorize.isPending ? 'Redirecting…' : 'Continue with Google'}
              </Text>
            </Pressable>
          ) : (
            <Text style={styles.subheadline}>Sign-in is available on the web app for now.</Text>
          )}
          <Text style={styles.ctaCaption}>Takes ten seconds. We only ever store your name and email.</Text>
          {authorize.isError ? <Text style={styles.error}>{authorize.error.message}</Text> : null}
        </View>

        <Text style={styles.disclaimer}>
          Posted categorizes financial activity for planning purposes. Verify important amounts
          with your financial institution.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.canvas },
  rootContent: { flexGrow: 1, alignItems: 'center', padding: spacing.lg },
  page: { width: '100%', maxWidth: 640 },
  nav: { paddingVertical: spacing.lg },
  headline: { color: colors.ink, marginTop: spacing.md },
  subheadline: {
    color: colors.inkMuted,
    fontSize: 15,
    lineHeight: 22,
    marginTop: spacing.sm,
  },
  preview: {
    marginTop: spacing.xl,
    borderWidth: 1,
    borderColor: roles.borderHairline,
  },
  previewHeader: { paddingHorizontal: spacing.md, paddingTop: spacing.sm },
  previewEyebrow: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1.2 },
  previewRule: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: roles.borderHairline,
    marginTop: spacing.sm,
  },
  previewLabel: { color: colors.inkFaint, fontSize: 9, fontWeight: '800', letterSpacing: 1.2, marginBottom: spacing.xs },
  previewValue: { color: colors.ink, fontSize: 30, fontWeight: '700', letterSpacing: -0.4, fontVariant: ['tabular-nums'] },
  previewCaption: { color: colors.inkMuted, fontSize: 11, marginTop: 4 },
  previewRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, gap: spacing.sm },
  previewSymbol: { color: colors.ink, fontSize: 12, fontWeight: '700', width: 60 },
  previewRowValue: { flex: 1, color: colors.ink, fontSize: 12, fontVariant: ['tabular-nums'] },
  previewRowChange: { fontSize: 12, fontWeight: '700', fontVariant: ['tabular-nums'] },
  ctaBlock: { marginTop: spacing.xl, gap: spacing.xs, alignItems: 'flex-start' },
  button: {
    height: 48,
    minWidth: 240,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.sm,
    backgroundColor: colors.teal,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonPressed: { opacity: 0.85 },
  buttonText: { color: colors.white, fontSize: 14, fontWeight: '700' },
  ctaCaption: { color: colors.inkFaint, fontSize: 12 },
  error: { color: colors.negative, fontSize: 12, marginTop: spacing.xs },
  disclaimer: {
    color: colors.inkFaint,
    fontSize: 10,
    lineHeight: 15,
    paddingVertical: spacing.xl,
  },
});
