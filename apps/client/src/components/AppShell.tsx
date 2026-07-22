import { usePathname, useRouter } from 'expo-router';
import {
  Bell,
  ChartNoAxesCombined,
  Landmark,
  LayoutDashboard,
  Newspaper,
  ReceiptText,
  Repeat2,
  Settings,
  WalletCards,
} from 'lucide-react-native';
import type { ReactNode } from 'react';
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BrandMark } from '@/components/BrandMark';
import { colors, spacing } from '@/theme/tokens';

type AppPath =
  | '/'
  | '/feed'
  | '/holdings'
  | '/money'
  | '/transactions'
  | '/subscriptions'
  | '/settings';

type NavItem = {
  label: string;
  href: AppPath;
  icon: typeof LayoutDashboard;
};

const portfolioNav: NavItem[] = [
  { label: 'Portfolio overview', href: '/', icon: LayoutDashboard },
  { label: 'Impact feed', href: '/feed', icon: Newspaper },
  { label: 'Holdings', href: '/holdings', icon: WalletCards },
];

const moneyNav: NavItem[] = [
  { label: 'Money overview', href: '/money', icon: Landmark },
  { label: 'Transactions', href: '/transactions', icon: ReceiptText },
  { label: 'Subscriptions', href: '/subscriptions', icon: Repeat2 },
];

const mobileNav: NavItem[] = [
  { label: 'Overview', href: '/', icon: LayoutDashboard },
  { label: 'Money', href: '/money', icon: Landmark },
  { label: 'Feed', href: '/feed', icon: Newspaper },
  { label: 'Holdings', href: '/holdings', icon: WalletCards },
  { label: 'Settings', href: '/settings', icon: Settings },
];

type Props = {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  headerAction?: ReactNode;
  scroll?: boolean;
};

export function AppShell({ title, eyebrow, children, headerAction, scroll = true }: Props) {
  const { width } = useWindowDimensions();
  const router = useRouter();
  const pathname = usePathname();
  const desktop = width >= 920;

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

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
      <View style={styles.root}>
        {desktop ? (
          <View style={styles.sidebar}>
            <View style={styles.brandArea}>
              <BrandMark />
            </View>
            {[
              { label: 'PORTFOLIO', items: portfolioNav },
              { label: 'MONEY', items: moneyNav },
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
                  <Text style={styles.marketStatusTitle}>Market data</Text>
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
            <Pressable accessibilityLabel="Notifications" style={styles.iconButton}>
              <Bell size={18} color={colors.ink} strokeWidth={1.8} />
              <View style={styles.notificationDot} />
            </Pressable>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>AM</Text>
            </View>
          </View>

          {scroll ? (
            <ScrollView
              style={styles.scroll}
              contentContainerStyle={styles.scrollContent}
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
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.navy },
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
  iconButton: {
    width: 38,
    height: 38,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  notificationDot: {
    position: 'absolute',
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.negative,
    right: 8,
    top: 7,
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { color: colors.tealDark, fontSize: 11, fontWeight: '800' },
  scroll: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  content: { width: '100%', maxWidth: 1440, alignSelf: 'center' },
  contentDesktop: { paddingHorizontal: 32, paddingTop: 30, paddingBottom: 48 },
  contentMobile: { paddingHorizontal: 16, paddingTop: 22, paddingBottom: 102 },
  pageHeader: {
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
