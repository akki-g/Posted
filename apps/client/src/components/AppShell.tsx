import { usePathname, useRouter } from 'expo-router';
import {
  Compass,
  LayoutDashboard,
  ReceiptText,
  Repeat2,
  Settings2,
  Sparkles,
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
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AssistantDrawer } from '@/components/AssistantDrawer';
import { BrandMark } from '@/components/BrandMark';
import { useAuth } from '@/lib/AuthContext';
import type { AssistantSection } from '@/lib/assistantSection';
import { useBreakpoint } from '@/theme/useBreakpoint';
import { colors, radius, roles, spacing } from '@/theme/tokens';

type AppPath = '/portfolio' | '/transactions' | '/subscriptions' | '/settings';

type ExploreItem = {
  label: string;
  href: AppPath;
  icon: typeof LayoutDashboard;
};

// The "encyclopedic" destinations — reached from the Explore panel rather
// than as sidebar peers, per the approved IA (they're drill-downs on one
// portfolio story, not co-equal top-level sections). Holdings / Feed / News /
// Insider activity collapsed into the tabbed "Portfolio detail" destination.
const exploreItems: ExploreItem[] = [
  { label: 'Portfolio detail', href: '/portfolio', icon: WalletCards },
  { label: 'Transactions', href: '/transactions', icon: ReceiptText },
  { label: 'Subscriptions', href: '/subscriptions', icon: Repeat2 },
  { label: 'Settings', href: '/settings', icon: Settings2 },
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
  /** Overrides the pathname-derived default — the Spine screen sets this per lens, since one route now covers what used to be two. */
  assistantSection?: AssistantSection;
};

function assistantSectionForPath(pathname: string): AssistantSection {
  if (pathname.startsWith('/transactions') || pathname.startsWith('/subscriptions')) {
    return 'money';
  }
  if (
    pathname === '/' ||
    pathname.startsWith('/portfolio') ||
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
  assistantSection: assistantSectionOverride,
}: Props) {
  const { desktop } = useBreakpoint();
  const router = useRouter();
  const pathname = usePathname();

  const { user, isLoading, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [exploreOpen, setExploreOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/login');
    }
  }, [isLoading, user, router]);
  const assistantSection = assistantSectionOverride ?? assistantSectionForPath(pathname);
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
        <View style={styles.topbar}>
          <Pressable accessibilityRole="link" onPress={() => router.push('/')}>
            <BrandMark compact={!desktop} />
          </Pressable>
          <View style={styles.topbarSpacer} />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={exploreOpen ? 'Close Explore' : 'Open Explore'}
            accessibilityState={{ expanded: exploreOpen }}
            onPress={() => {
              setMenuOpen(false);
              setExploreOpen((open) => !open);
            }}
            style={({ pressed }) => [
              styles.iconButton,
              exploreOpen && styles.iconButtonActive,
              pressed && styles.iconButtonPressed,
            ]}>
            <Compass size={17} color={exploreOpen ? colors.tealDark : colors.inkMuted} />
            {desktop ? <Text style={styles.iconButtonLabel}>Explore</Text> : null}
          </Pressable>
          {pathname !== '/assistant' ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={assistantOpen ? 'Close Ask Posted' : 'Open Ask Posted'}
              accessibilityState={{ expanded: assistantOpen }}
              onPress={() => {
                setMenuOpen(false);
                setExploreOpen(false);
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
            onPress={() => {
              setExploreOpen(false);
              setMenuOpen((open) => !open);
            }}
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

        {exploreOpen ? (
          <>
            <Pressable style={styles.menuBackdrop} onPress={() => setExploreOpen(false)} />
            <View style={styles.exploreMenu} accessibilityRole="menu">
              <Text style={styles.exploreMenuLabel}>EXPLORE</Text>
              {exploreItems.map((item) => {
                const Icon = item.icon;
                const active = pathname.startsWith(item.href);
                return (
                  <Pressable
                    key={item.href}
                    accessibilityRole="menuitem"
                    accessibilityState={{ selected: active }}
                    onPress={() => {
                      setExploreOpen(false);
                      router.push(item.href);
                    }}
                    style={({ pressed }) => [
                      styles.exploreItem,
                      active && styles.exploreItemActive,
                      pressed && styles.exploreItemPressed,
                    ]}>
                    <Icon size={16} color={active ? colors.tealDark : colors.inkMuted} />
                    <Text style={[styles.exploreItemText, active && styles.exploreItemTextActive]}>
                      {item.label}
                    </Text>
                  </Pressable>
                );
              })}
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
            <Pressable
              accessibilityRole="tab"
              accessibilityState={{ selected: pathname === '/' }}
              onPress={() => router.push('/')}
              style={styles.bottomNavItem}>
              <LayoutDashboard
                size={20}
                color={pathname === '/' ? colors.teal : colors.inkFaint}
                strokeWidth={pathname === '/' ? 2.2 : 1.8}
              />
              <Text style={[styles.bottomNavText, pathname === '/' && styles.bottomNavTextActive]}>
                Home
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="tab"
              accessibilityState={{ selected: exploreOpen }}
              onPress={() => {
                setMenuOpen(false);
                setExploreOpen((open) => !open);
              }}
              style={styles.bottomNavItem}>
              <Compass
                size={20}
                color={exploreOpen ? colors.teal : colors.inkFaint}
                strokeWidth={exploreOpen ? 2.2 : 1.8}
              />
              <Text style={[styles.bottomNavText, exploreOpen && styles.bottomNavTextActive]}>
                Explore
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="tab"
              accessibilityState={{ selected: assistantOpen }}
              onPress={() => {
                setExploreOpen(false);
                setAssistantOpen((open) => !open);
              }}
              style={styles.bottomNavItem}>
              <Sparkles
                size={20}
                color={assistantOpen ? colors.teal : colors.inkFaint}
                strokeWidth={assistantOpen ? 2.2 : 1.8}
              />
              <Text style={[styles.bottomNavText, assistantOpen && styles.bottomNavTextActive]}>
                Ask
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="tab"
              accessibilityState={{ selected: pathname.startsWith('/settings') }}
              onPress={() => router.push('/settings')}
              style={styles.bottomNavItem}>
              <Settings2
                size={20}
                color={pathname.startsWith('/settings') ? colors.teal : colors.inkFaint}
                strokeWidth={pathname.startsWith('/settings') ? 2.2 : 1.8}
              />
              <Text
                style={[
                  styles.bottomNavText,
                  pathname.startsWith('/settings') && styles.bottomNavTextActive,
                ]}>
                Settings
              </Text>
            </Pressable>
          </View>
        ) : null}

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
  safeArea: { flex: 1, backgroundColor: colors.surface },
  authGate: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.canvas },
  root: { flex: 1, backgroundColor: colors.canvas },
  topbar: {
    height: 64,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: roles.borderHairline,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    gap: 8,
  },
  topbarSpacer: { flex: 1 },
  iconButton: {
    height: 38,
    borderWidth: 1,
    borderColor: roles.borderHairline,
    borderRadius: radius.sm,
    backgroundColor: roles.surface,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
  },
  iconButtonActive: { backgroundColor: roles.accentSoft, borderColor: roles.accentSoftBorder },
  iconButtonPressed: { backgroundColor: roles.surfaceSunken },
  iconButtonLabel: { color: colors.inkMuted, fontSize: 12, fontWeight: '600' },
  assistantButton: {
    height: 38,
    borderWidth: 1,
    borderColor: colors.teal,
    borderRadius: radius.sm,
    backgroundColor: colors.tealSoft,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
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
    borderColor: roles.borderHairline,
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
    borderBottomColor: roles.borderHairline,
  },
  userMenuName: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  userMenuEmail: { color: colors.inkMuted, fontSize: 11, marginTop: 2 },
  userMenuItem: { paddingHorizontal: 14, height: 40, justifyContent: 'center' },
  userMenuItemText: { color: colors.ink, fontSize: 13, fontWeight: '500' },
  exploreMenu: {
    position: 'absolute',
    top: 64 + 8,
    right: 20,
    width: 250,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: roles.borderHairline,
    borderRadius: radius.md,
    paddingVertical: 8,
    zIndex: 11,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  exploreMenuLabel: {
    color: colors.inkFaint,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1.2,
    paddingHorizontal: 14,
    paddingBottom: 6,
  },
  exploreItem: {
    height: 42,
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  exploreItemActive: { backgroundColor: roles.accentSoft },
  exploreItemPressed: { backgroundColor: roles.surfaceSunken },
  exploreItemText: { color: colors.ink, fontSize: 13, fontWeight: '500' },
  exploreItemTextActive: { color: colors.tealDark, fontWeight: '700' },
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
    borderTopColor: roles.borderHairline,
    flexDirection: 'row',
  },
  bottomNavItem: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4 },
  bottomNavText: { color: colors.inkFaint, fontSize: 10, fontWeight: '600' },
  bottomNavTextActive: { color: colors.teal },
});
