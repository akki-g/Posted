import { usePathname, useRouter } from 'expo-router';
import {
  Landmark,
  LayoutDashboard,
  Newspaper,
  ReceiptText,
  Repeat2,
  Rss,
  Sparkles,
  TrendingUp,
  UserRoundSearch,
  WalletCards,
} from 'lucide-react-native';
import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AssistantDrawer } from '@/components/AssistantDrawer';
import { BrandMark } from '@/components/BrandMark';
import { useAuth } from '@/lib/AuthContext';
import type { AssistantSection } from '@/lib/assistantSection';
import { breakpoints, colors, radius, spacing } from '@/theme/tokens';

type AppPath =
  | '/'
  | '/feed'
  | '/holdings'
  | '/money'
  | '/transactions'
  | '/subscriptions'
  | '/invest'
  | '/news'
  | '/insiders'
  | '/assistant'
  | '/settings';

type NavItem = {
  label: string;
  href: AppPath;
  icon: typeof LayoutDashboard;
};

const portfolioNav: NavItem[] = [
  { label: 'Portfolio overview', href: '/', icon: LayoutDashboard },
  { label: 'Impact feed', href: '/feed', icon: Newspaper },
  { label: 'News', href: '/news', icon: Rss },
  { label: 'Holdings', href: '/holdings', icon: WalletCards },
  { label: 'Insider activity', href: '/insiders', icon: UserRoundSearch },
];

const moneyNav: NavItem[] = [
  { label: 'Money overview', href: '/money', icon: Landmark },
  { label: 'Transactions', href: '/transactions', icon: ReceiptText },
  { label: 'Subscriptions', href: '/subscriptions', icon: Repeat2 },
];

const mobileNav: NavItem[] = [
  { label: 'Home', href: '/money', icon: Landmark },
  { label: 'Activity', href: '/transactions', icon: ReceiptText },
  { label: 'Invest', href: '/invest', icon: TrendingUp },
  { label: 'Recurring', href: '/subscriptions', icon: Repeat2 },
];

type Props = {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  headerAction?: ReactNode;
  scroll?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
  assistantContext?: string | (() => string);
  assistantContextLabel?: string;
};

function assistantSectionForPath(pathname: string): AssistantSection {
  if (
    pathname.startsWith('/money') ||
    pathname.startsWith('/transactions') ||
    pathname.startsWith('/subscriptions')
  ) {
    return 'money';
  }
  if (
    pathname === '/' ||
    pathname.startsWith('/feed') ||
    pathname.startsWith('/holdings') ||
    pathname.startsWith('/invest') ||
    pathname.startsWith('/news') ||
    pathname.startsWith('/insiders') ||
    pathname.startsWith('/stock')
  ) {
    return 'investing';
  }
  return 'general';
}

export function AppShell({
  title,
  eyebrow,
  children,
  headerAction,
  scroll = true,
  refreshing = false,
  onRefresh,
  assistantContext,
  assistantContextLabel,
}: Props) {
  const { width } = useWindowDimensions();
  const router = useRouter();
  const pathname = usePathname();
  const desktop = width >= breakpoints.mobileNav;

  const { user, isLoading, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/login');
    }
  }, [isLoading, user, router]);
  const assistantSection = assistantSectionForPath(pathname);
  const resolvedAssistantContext =
    assistantContext ??
    `The user is viewing the "${title}" screen at ${pathname}. ${
      eyebrow ? `The screen is grouped under "${eyebrow}". ` : ''
    }Use this page identity only to resolve references such as "this page" or "what I am looking at"; fetch current financial facts with the available tools.`;

  const initials = user
    ? user.display_name
        .split(' ')
        .map((part) => part[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'PU';

  const content = (
    <View style={[styles.content, desktop ? styles.contentDesktop : styles.contentMobile]}>
      <View style={styles.pageHeader}>
        <View style={styles.headingBlock}>
          {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
          <Text style={[styles.title, !desktop && styles.titleMobile]}>{title}</Text>
        </View>
        {headerAction}
      </View>
      {children}
    </View>
  );

  if (isLoading || !user) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
        <View style={styles.authGate}>
          <ActivityIndicator color={colors.teal} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
      <View style={styles.root}>
        {desktop ? (
          <View style={styles.sidebar}>
            <View style={styles.brandArea}>
              <BrandMark />
            </View>
            {[
              { label: 'MONEY', items: moneyNav },
              { label: 'INVESTING', items: portfolioNav },
            ].map((group) => (
              <View key={group.label} style={styles.navGroup}>
                <Text style={styles.navLabel}>{group.label}</Text>
                {group.items.map((item) => {
                  const active =
                    item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
                  const Icon = item.icon;
                  return (
                    <Pressable
                      key={item.href}
                      accessibilityRole="link"
                      onPress={() => router.push(item.href)}
                      style={({ pressed }) => [
                        styles.navItem,
                        active && styles.navItemActive,
                        pressed && styles.navItemPressed,
                      ]}>
                      <View style={[styles.navIndicator, active && styles.navIndicatorActive]} />
                      <Icon
                        size={18}
                        color={active ? colors.white : '#9DA9B9'}
                        strokeWidth={1.8}
                      />
                      <Text style={[styles.navText, active && styles.navTextActive]}>
                        {item.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            ))}
            <View style={styles.sidebarFooter}>
              <View style={styles.marketStatus}>
                <View style={styles.statusDot} />
                <View>
                  <Text style={styles.marketStatusTitle}>Financial data</Text>
                  <Text style={styles.marketStatusCaption}>Demo environment</Text>
                </View>
              </View>
            </View>
          </View>
        ) : null}

        <View style={styles.main}>
          <View style={styles.topbar}>
            {!desktop ? <BrandMark compact /> : null}
            <View style={styles.topbarSpacer} />
            {pathname !== '/assistant' ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={assistantOpen ? 'Close Ask Posted' : 'Open Ask Posted'}
                accessibilityState={{ expanded: assistantOpen }}
                onPress={() => {
                  setMenuOpen(false);
                  setAssistantOpen((open) => !open);
                }}
                style={({ pressed }) => [
                  styles.assistantButton,
                  assistantOpen && styles.assistantButtonActive,
                  pressed && styles.assistantButtonPressed,
                ]}>
                <Sparkles
                  size={16}
                  color={assistantOpen ? colors.white : colors.tealDark}
                  strokeWidth={2}
                />
                <Text
                  style={[
                    styles.assistantButtonText,
                    assistantOpen && styles.assistantButtonTextActive,
                  ]}>
                  {desktop ? 'Ask Posted' : 'Ask'}
                </Text>
              </Pressable>
            ) : null}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Account menu"
              onPress={() => setMenuOpen((open) => !open)}
              style={styles.avatar}>
              <Text style={styles.avatarText}>{initials}</Text>
            </Pressable>
          </View>

          {menuOpen ? (
            <>
              <Pressable style={styles.menuBackdrop} onPress={() => setMenuOpen(false)} />
              <View style={styles.userMenu}>
                <View style={styles.userMenuHeader}>
                  <Text style={styles.userMenuName} numberOfLines={1}>
                    {user ? user.display_name : 'Not signed in'}
                  </Text>
                  {user ? (
                    <Text style={styles.userMenuEmail} numberOfLines={1}>
                      {user.email}
                    </Text>
                  ) : null}
                </View>
                <Pressable
                  style={styles.userMenuItem}
                  onPress={() => {
                    setMenuOpen(false);
                    router.push('/settings');
                  }}>
                  <Text style={styles.userMenuItemText}>Settings</Text>
                </Pressable>
                {user ? (
                  <Pressable
                    style={styles.userMenuItem}
                    onPress={() => {
                      setMenuOpen(false);
                      signOut();
                      router.replace('/');
                    }}>
                    <Text style={styles.userMenuItemText}>Sign out</Text>
                  </Pressable>
                ) : (
                  <Pressable
                    style={styles.userMenuItem}
                    onPress={() => {
                      setMenuOpen(false);
                      router.push('/login');
                    }}>
                    <Text style={styles.userMenuItemText}>Sign in with Google</Text>
                  </Pressable>
                )}
              </View>
            </>
          ) : null}

          {scroll ? (
            <ScrollView
              style={styles.scroll}
              contentContainerStyle={styles.scrollContent}
              refreshControl={
                onRefresh ? (
                  <RefreshControl
                    refreshing={refreshing}
                    onRefresh={onRefresh}
                    tintColor={colors.teal}
                    colors={[colors.teal]}
                  />
                ) : undefined
              }
              showsVerticalScrollIndicator={false}>
              {content}
            </ScrollView>
          ) : (
            content
          )}

          {!desktop ? (
            <View style={styles.bottomNav}>
              {mobileNav.map((item) => {
                const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Pressable
                    key={item.href}
                    accessibilityRole="tab"
                    onPress={() => router.push(item.href)}
                    style={styles.bottomNavItem}>
                    <Icon
                      size={20}
                      color={active ? colors.teal : colors.inkFaint}
                      strokeWidth={active ? 2.2 : 1.8}
                    />
                    <Text style={[styles.bottomNavText, active && styles.bottomNavTextActive]}>
                      {item.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          ) : null}
        </View>

        {assistantOpen ? (
          <AssistantDrawer
            contextLabel={assistantContextLabel ?? title}
            initialSection={assistantSection}
            onClose={() => setAssistantOpen(false)}
            screenContext={resolvedAssistantContext}
          />
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.navy },
  authGate: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.canvas },
  root: { flex: 1, flexDirection: 'row', backgroundColor: colors.canvas },
  sidebar: { width: 224, backgroundColor: colors.navy, minHeight: '100%' },
  brandArea: {
    height: 64,
    paddingHorizontal: 22,
    justifyContent: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#263247',
  },
  navGroup: { paddingTop: 24 },
  navLabel: {
    color: '#6F7C8F',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.6,
    paddingHorizontal: 24,
    marginBottom: 10,
  },
  navItem: {
    height: 48,
    paddingRight: 18,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 13,
  },
  navItemActive: { backgroundColor: colors.navyRaised },
  navItemPressed: { opacity: 0.8 },
  navIndicator: { width: 3, height: 48, backgroundColor: colors.transparent },
  navIndicatorActive: { backgroundColor: '#29B8B5' },
  navText: { color: '#AAB4C1', fontSize: 14, fontWeight: '500' },
  navTextActive: { color: colors.white, fontWeight: '600' },
  sidebarFooter: { marginTop: 'auto', padding: 16 },
  marketStatus: {
    borderTopWidth: 1,
    borderTopColor: '#263247',
    paddingTop: 17,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  statusDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#32C98C' },
  marketStatusTitle: { color: '#D5DBE4', fontSize: 12, fontWeight: '600' },
  marketStatusCaption: { color: '#768397', fontSize: 10, marginTop: 2 },
  main: { flex: 1, backgroundColor: colors.canvas },
  topbar: {
    height: 64,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  topbarSpacer: { flex: 1 },
  assistantButton: {
    height: 38,
    borderWidth: 1,
    borderColor: colors.teal,
    borderRadius: 4,
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    marginRight: 10,
  },
  assistantButtonActive: { backgroundColor: colors.teal, borderColor: colors.teal },
  assistantButtonPressed: { opacity: 0.82 },
  assistantButtonText: { color: colors.tealDark, fontSize: 11, fontWeight: '800' },
  assistantButtonTextActive: { color: colors.white },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { color: colors.tealDark, fontSize: 11, fontWeight: '800' },
  menuBackdrop: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 10,
  },
  userMenu: {
    position: 'absolute',
    top: 64 + 8,
    right: 20,
    width: 220,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingVertical: 6,
    zIndex: 11,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  userMenuHeader: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  userMenuName: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  userMenuEmail: { color: colors.inkMuted, fontSize: 11, marginTop: 2 },
  userMenuItem: { paddingHorizontal: 14, height: 40, justifyContent: 'center' },
  userMenuItemText: { color: colors.ink, fontSize: 13, fontWeight: '500' },
  scroll: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  content: {
    width: '100%',
    maxWidth: 1440,
    alignSelf: 'center',
    overflow: 'visible',
  },
  contentDesktop: { paddingHorizontal: 32, paddingTop: 30, paddingBottom: 48 },
  contentMobile: { paddingHorizontal: 16, paddingTop: 22, paddingBottom: 102 },
  pageHeader: {
    position: 'relative',
    zIndex: 1000,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginBottom: 24,
  },
  headingBlock: { flexShrink: 1 },
  eyebrow: {
    color: colors.inkMuted,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.4,
    marginBottom: 7,
  },
  title: { color: colors.ink, fontSize: 30, lineHeight: 36, fontWeight: '600', letterSpacing: -0.7 },
  titleMobile: { fontSize: 25, lineHeight: 31 },
  bottomNav: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: Platform.OS === 'ios' ? 78 : 66,
    paddingBottom: Platform.OS === 'ios' ? 12 : 2,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    flexDirection: 'row',
  },
  bottomNavItem: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4 },
  bottomNavText: { color: colors.inkFaint, fontSize: 10, fontWeight: '600' },
  bottomNavTextActive: { color: colors.teal },
});
