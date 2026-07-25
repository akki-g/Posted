import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { Landmark, MessageSquare, Rss, UserRoundSearch } from 'lucide-react-native';
import { useEffect } from 'react';
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import { BrandMark } from '@/components/BrandMark';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { colors, radius, spacing, type as typeTokens } from '@/theme/tokens';

const features = [
  {
    icon: Landmark,
    title: 'Banking + investing, one view',
    caption: 'Plaid and Schwab feed the same dashboard — no more switching apps.',
  },
  {
    icon: Rss,
    title: 'Impact feed',
    caption: 'Portfolio news filtered down to what actually moves your holdings.',
  },
  {
    icon: MessageSquare,
    title: 'Ask Posted',
    caption: 'An assistant grounded in your real balances, not generic advice.',
  },
  {
    icon: UserRoundSearch,
    title: 'Insider activity',
    caption: 'See what company insiders are doing with stock you own.',
  },
];

export default function LoginScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const desktop = width >= 920;
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
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.rootContent}
      showsVerticalScrollIndicator={false}>
      <View style={styles.nav}>
        <BrandMark compact />
        <Text style={styles.navWordmark}>POSTED</Text>
      </View>

      <View style={[styles.hero, desktop && styles.heroDesktop]}>
        <View style={[styles.column, desktop && styles.columnMain]}>
          <View style={styles.eyebrowRow}>
            <View style={styles.eyebrowDot} />
            <Text style={styles.eyebrow}>MONEY &amp; INVESTING, UNIFIED</Text>
          </View>

          <Text style={[styles.headline, desktop && styles.headlineDesktop]}>
            Your money and your portfolio, <Text style={styles.headlineAccent}>finally together.</Text>
          </Text>

          <Text style={styles.subheadline}>
            Posted connects your bank accounts and brokerage into a single dashboard, with an
            AI assistant that actually knows your numbers and a feed that filters out the noise.
          </Text>

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
            <Text style={styles.ctaCaption}>
              Takes ten seconds. We only ever store your name and email.
            </Text>
            {authorize.isError ? <Text style={styles.error}>{authorize.error.message}</Text> : null}
          </View>
        </View>

        <View style={[styles.column, styles.card, desktop && styles.columnAside]}>
          <Text style={styles.cardLabel}>WHAT POSTED DOES</Text>
          {features.map(({ icon: Icon, title, caption }) => (
            <View key={title} style={styles.featureRow}>
              <View style={styles.featureIcon}>
                <Icon size={16} color={colors.tealDark} strokeWidth={1.8} />
              </View>
              <View style={styles.featureCopy}>
                <Text style={styles.featureTitle}>{title}</Text>
                <Text style={styles.featureCaption}>{caption}</Text>
              </View>
            </View>
          ))}
        </View>
      </View>

      <Text style={styles.disclaimer}>
        Posted categorizes financial activity for planning purposes. Verify important amounts
        with your financial institution.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.canvas,
  },
  rootContent: {
    flexGrow: 1,
    alignItems: 'center',
    padding: spacing.lg,
  },
  nav: {
    width: '100%',
    maxWidth: 1040,
    paddingVertical: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  navWordmark: {
    color: colors.ink,
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 2.4,
  },
  hero: {
    width: '100%',
    maxWidth: 1040,
    flex: 1,
    gap: spacing.xl,
    paddingTop: spacing.lg,
  },
  heroDesktop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  column: { gap: spacing.md },
  columnMain: { flex: 1.3, paddingRight: spacing.xl },
  columnAside: { flex: 1, marginTop: spacing.xxl },
  eyebrowRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  eyebrowDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.teal },
  eyebrow: {
    color: colors.inkMuted,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.6,
  },
  headline: {
    color: colors.ink,
    fontSize: 40,
    lineHeight: 46,
    fontWeight: '700',
    letterSpacing: -1,
    marginTop: spacing.sm,
  },
  headlineDesktop: { fontSize: 56, lineHeight: 60 },
  headlineAccent: { color: colors.tealDark },
  subheadline: {
    color: colors.inkMuted,
    fontSize: typeTokens.bodyLarge,
    lineHeight: 24,
    maxWidth: 480,
    marginTop: spacing.xs,
  },
  ctaBlock: { marginTop: spacing.lg, gap: spacing.xs, alignItems: 'flex-start' },
  button: {
    height: 48,
    minWidth: 240,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    backgroundColor: colors.teal,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonPressed: { opacity: 0.85 },
  buttonText: { color: colors.white, fontSize: typeTokens.body, fontWeight: '700' },
  ctaCaption: { color: colors.inkFaint, fontSize: typeTokens.caption },
  error: { color: colors.negative, fontSize: typeTokens.caption, marginTop: spacing.xs },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderTopWidth: 3,
    borderTopColor: colors.ink,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  cardLabel: {
    color: colors.inkFaint,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.4,
    marginBottom: spacing.sm,
  },
  featureRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  featureIcon: {
    width: 30,
    height: 30,
    borderRadius: radius.sm,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  featureCopy: { flex: 1 },
  featureTitle: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  featureCaption: { color: colors.inkMuted, fontSize: 11, lineHeight: 15, marginTop: 2 },
  disclaimer: {
    width: '100%',
    maxWidth: 1040,
    color: colors.inkFaint,
    fontSize: 10,
    lineHeight: 15,
    paddingVertical: spacing.xl,
  },
});
