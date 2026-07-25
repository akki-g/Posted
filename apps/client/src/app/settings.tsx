import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import {
  Check,
  ChevronRight,
  Database,
  Landmark,
  LockKeyhole,
  RefreshCw,
  Smartphone,
  SunMedium,
  WalletCards,
} from 'lucide-react-native';
import { useEffect } from 'react';
import { Linking, Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { AppShell } from '@/components/AppShell';
import { PlaidLinkButton } from '@/components/PlaidLinkButton';
import { ErrorState, LoadingState, SectionHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { relativeTime } from '@/lib/format';
import type { UserPreferences } from '@/lib/types';
import { colors } from '@/theme/tokens';

export default function SettingsScreen() {
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ schwab?: string }>();
  const connections = useQuery({
    queryKey: ['connections'],
    queryFn: api.connections,
  });
  const schwabStatus = useQuery({
    queryKey: ['schwab-status'],
    queryFn: api.schwabStatus,
  });
  const moneyConnections = useQuery({
    queryKey: ['money-connections'],
    queryFn: api.moneyConnections,
  });
  const plaidStatus = useQuery({ queryKey: ['plaid-status'], queryFn: api.plaidStatus });
  const preferences = useQuery({ queryKey: ['preferences'], queryFn: api.preferences });
  const updatePreferences = useMutation({
    mutationFn: api.updatePreferences,
    onSuccess: (updated) => queryClient.setQueryData(['preferences'], updated),
  });
  const connectSchwab = useMutation({
    mutationFn: api.authorizeSchwab,
    onSuccess: async ({ authorization_url }) => Linking.openURL(authorization_url),
  });
  const syncInvesting = useMutation({
    mutationFn: api.sync,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['connections'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['holdings'] }),
      ]);
    },
  });
  const syncMoney = useMutation({
    mutationFn: api.syncMoneyConnection,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['money-connections'] }),
        queryClient.invalidateQueries({ queryKey: ['money-overview'] }),
        queryClient.invalidateQueries({ queryKey: ['money-transactions'] }),
        queryClient.invalidateQueries({ queryKey: ['subscriptions'] }),
      ]);
    },
  });

  const updatePreference = (changes: Partial<UserPreferences>) => {
    if (preferences.data) {
      updatePreferences.mutate({ ...preferences.data, ...changes });
    }
  };

  useEffect(() => {
    if (params.schwab === 'connected') {
      void queryClient.invalidateQueries({ queryKey: ['connections'] });
      void queryClient.invalidateQueries({ queryKey: ['schwab-status'] });
    }
  }, [params.schwab, queryClient]);

  return (
    <AppShell title="Settings" eyebrow="CONNECTIONS AND ALERTS">
      <View style={styles.settingsGrid}>
        <View style={styles.panel}>
          <SectionHeader title="Banking connections" caption="Your balances and transaction history" />
          {moneyConnections.isLoading ? <LoadingState label="Loading bank connections" /> : null}
          {moneyConnections.isError ? (
            <ErrorState
              message={moneyConnections.error.message}
              retry={() => moneyConnections.refetch()}
            />
          ) : null}
          {moneyConnections.data?.map((connection) => (
            <View key={connection.id} style={styles.connectionRow}>
              <View style={styles.providerMark}>
                <Landmark size={17} color={colors.tealDark} />
              </View>
              <View style={styles.connectionCopy}>
                <Text style={styles.connectionName}>{connection.display_name}</Text>
                <Text style={styles.connectionMeta}>
                  {connection.account_count} accounts · synced {connection.last_synced_at ? relativeTime(connection.last_synced_at) : 'never'}
                </Text>
              </View>
              {connection.is_demo ? (
                <View style={styles.demoStatus}>
                  <Check size={12} color={colors.tealDark} />
                  <Text style={styles.demoStatusText}>DEMO</Text>
                </View>
              ) : (
                <Pressable
                  accessibilityLabel={`Sync ${connection.display_name}`}
                  disabled={syncMoney.isPending}
                  onPress={() => syncMoney.mutate(connection.id)}
                  style={styles.syncButton}>
                  <RefreshCw size={12} color={colors.tealDark} />
                  <Text style={styles.syncButtonText}>
                    {syncMoney.isPending && syncMoney.variables === connection.id ? 'SYNCING' : 'SYNC'}
                  </Text>
                </Pressable>
              )}
            </View>
          ))}
          <View style={styles.integrationRow}>
            <View style={styles.integrationIcon}>
              <WalletCards size={17} color={colors.inkMuted} />
            </View>
            <View style={styles.connectionCopy}>
              <Text style={styles.connectionName}>Plaid Link</Text>
              <Text style={styles.connectionMeta}>
                {plaidStatus.data?.configured
                  ? `${plaidStatus.data.environment} credentials ready · native Link enabled`
                  : 'Add Sandbox credentials to the backend environment'}
              </Text>
            </View>
            <View style={[styles.readinessBadge, plaidStatus.data?.configured && styles.readinessBadgeReady]}>
              <Text style={[styles.readinessText, plaidStatus.data?.configured && styles.readinessTextReady]}>
                {plaidStatus.data?.configured ? 'READY' : 'SETUP'}
              </Text>
            </View>
          </View>
          <PlaidLinkButton disabled={!plaidStatus.data?.configured} />
          {syncMoney.isError ? (
            <Text style={styles.connectionError}>{syncMoney.error.message}</Text>
          ) : null}
        </View>

        <View style={styles.panel}>
          <SectionHeader title="Investing connections" caption="Read-only Schwab portfolio access" />
          {connections.isLoading ? <LoadingState label="Loading brokerage connections" /> : null}
          {connections.isError ? (
            <ErrorState message={connections.error.message} retry={() => connections.refetch()} />
          ) : null}
          {connections.data?.map((connection) => (
            <View key={connection.id} style={styles.connectionRow}>
              <View style={styles.providerMark}>
                <Text style={styles.providerMarkText}>S</Text>
              </View>
              <View style={styles.connectionCopy}>
                <Text style={styles.connectionName}>{connection.display_name}</Text>
                <Text style={styles.connectionMeta}>
                  {connection.account_count} accounts · synced {connection.last_synced_at ? relativeTime(connection.last_synced_at) : 'never'}
                </Text>
              </View>
              {connection.demo_mode ? (
                <View style={styles.demoStatus}>
                  <Check size={12} color={colors.tealDark} />
                  <Text style={styles.demoStatusText}>DEMO</Text>
                </View>
              ) : (
                <Pressable
                  accessibilityLabel={`Sync ${connection.display_name}`}
                  disabled={syncInvesting.isPending}
                  onPress={() => syncInvesting.mutate(connection.id)}
                  style={styles.syncButton}>
                  <RefreshCw size={12} color={colors.tealDark} />
                  <Text style={styles.syncButtonText}>
                    {syncInvesting.isPending && syncInvesting.variables === connection.id
                      ? 'SYNCING'
                      : 'SYNC'}
                  </Text>
                </Pressable>
              )}
            </View>
          ))}
          <View style={styles.integrationRow}>
            <View style={styles.integrationIcon}>
              <WalletCards size={17} color={colors.inkMuted} />
            </View>
            <View style={styles.connectionCopy}>
              <Text style={styles.connectionName}>Schwab Trader API</Text>
              <Text style={styles.connectionMeta}>
                {schwabStatus.data?.configured
                  ? 'Developer credentials ready · OAuth connection enabled'
                  : 'Add your approved app key and secret to the backend'}
              </Text>
            </View>
            <View
              style={[
                styles.readinessBadge,
                schwabStatus.data?.configured && styles.readinessBadgeReady,
              ]}>
              <Text
                style={[
                  styles.readinessText,
                  schwabStatus.data?.configured && styles.readinessTextReady,
                ]}>
                {schwabStatus.data?.configured ? 'READY' : 'SETUP'}
              </Text>
            </View>
          </View>
          <Pressable
            disabled={connectSchwab.isPending || !schwabStatus.data?.configured}
            onPress={() => connectSchwab.mutate()}
            style={[
              styles.connectButton,
              (!schwabStatus.data?.configured || connectSchwab.isPending) &&
                styles.connectButtonDisabled,
            ]}>
            <Text style={styles.connectButtonText}>
              {connectSchwab.isPending ? 'Opening Schwab…' : 'Connect or reconnect Schwab'}
            </Text>
            <ChevronRight size={16} color={colors.tealDark} />
          </Pressable>
          <Text style={styles.connectionHelp}>
            Authorization opens Schwab in your browser and returns to Posted after approval.
          </Text>
          {params.schwab === 'connected' ? (
            <Text style={styles.connectionSuccess}>
              Schwab connected. Tap Sync or open Investing to import your portfolio.
            </Text>
          ) : null}
          {params.schwab === 'error' ? (
            <Text style={styles.connectionError}>
              Schwab authorization was cancelled or rejected. You can try connecting again.
            </Text>
          ) : null}
          {connectSchwab.isError ? (
            <Text style={styles.connectionError}>{connectSchwab.error.message}</Text>
          ) : null}
          {syncInvesting.isError ? (
            <Text style={styles.connectionError}>{syncInvesting.error.message}</Text>
          ) : null}
        </View>

        <View style={styles.panel}>
          <SectionHeader title="Alert delivery" caption="Control how Posted reaches you" />
          <SettingRow
            icon={<Smartphone size={17} color={colors.inkMuted} />}
            title="Push notifications"
            caption="Upcoming bills and unusual money activity"
            control={
              <Switch
                value={preferences.data?.push_enabled ?? true}
                disabled={!preferences.data || updatePreferences.isPending}
                onValueChange={(value) => updatePreference({ push_enabled: value })}
                trackColor={{ true: colors.teal }}
              />
            }
          />
          <SettingRow
            icon={<SunMedium size={17} color={colors.inkMuted} />}
            title="Morning briefing"
            caption="Daily money summary at 8:00 AM"
            control={
              <Switch
                value={preferences.data?.email_digest_enabled ?? false}
                disabled={!preferences.data || updatePreferences.isPending}
                onValueChange={(value) => updatePreference({ email_digest_enabled: value })}
                trackColor={{ true: colors.teal }}
              />
            }
          />
        </View>

        <View style={styles.panel}>
          <SectionHeader title="Data and security" caption="How financial information is handled" />
          <SettingRow
            icon={<LockKeyhole size={17} color={colors.inkMuted} />}
            title="Bank connection credentials"
            caption="Access tokens remain encrypted on the backend and never enter this app"
            control={<ChevronRight size={16} color={colors.inkFaint} />}
          />
          <SettingRow
            icon={<Database size={17} color={colors.inkMuted} />}
            title="Data providers"
            caption="Plaid supplies money activity; Schwab supplies read-only investment positions"
            control={<ChevronRight size={16} color={colors.inkFaint} />}
          />
        </View>
      </View>
      <Text style={styles.disclaimer}>
        Posted categorizes financial activity for planning purposes. Verify important amounts with your financial institution.
      </Text>
    </AppShell>
  );
}

function SettingRow({
  icon,
  title,
  caption,
  control,
}: {
  icon: React.ReactNode;
  title: string;
  caption: string;
  control: React.ReactNode;
}) {
  return (
    <View style={styles.settingRow}>
      <View style={styles.settingIcon}>{icon}</View>
      <View style={styles.settingCopy}>
        <Text style={styles.settingTitle}>{title}</Text>
        <Text style={styles.settingCaption}>{caption}</Text>
      </View>
      {control}
    </View>
  );
}

const styles = StyleSheet.create({
  settingsGrid: { gap: 16, maxWidth: 920 },
  panel: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  connectionRow: { minHeight: 84, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 12 },
  providerMark: {
    width: 38,
    height: 38,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  providerMarkText: {
    color: colors.tealDark,
    fontSize: 15,
    fontWeight: '800',
  },
  connectionCopy: { flex: 1 },
  connectionName: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  connectionMeta: { color: colors.inkMuted, fontSize: 10, marginTop: 5 },
  demoStatus: { paddingHorizontal: 8, height: 25, backgroundColor: colors.tealSoft, flexDirection: 'row', alignItems: 'center', gap: 5 },
  demoStatusText: { color: colors.tealDark, fontSize: 8, fontWeight: '800', letterSpacing: 0.8 },
  syncButton: {
    paddingHorizontal: 9,
    height: 28,
    borderWidth: 1,
    borderColor: colors.teal,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  syncButtonText: { color: colors.tealDark, fontSize: 8, fontWeight: '800', letterSpacing: 0.7 },
  connectButton: { height: 45, borderTopWidth: 1, borderTopColor: colors.line, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  connectButtonText: { color: colors.tealDark, fontSize: 11, fontWeight: '700' },
  connectButtonDisabled: { opacity: 0.5 },
  connectionHelp: {
    color: colors.inkMuted,
    fontSize: 10,
    lineHeight: 15,
    paddingHorizontal: 16,
    paddingTop: 10,
  },
  connectionSuccess: {
    color: colors.positive,
    fontSize: 10,
    lineHeight: 15,
    fontWeight: '700',
    paddingHorizontal: 16,
    paddingTop: 10,
  },
  connectionError: {
    color: colors.negative,
    fontSize: 10,
    lineHeight: 15,
    paddingHorizontal: 16,
    paddingBottom: 14,
  },
  integrationRow: { minHeight: 78, padding: 16, borderTopWidth: 1, borderTopColor: colors.line, flexDirection: 'row', alignItems: 'center', gap: 12 },
  integrationIcon: { width: 36, height: 36, backgroundColor: colors.surfaceMuted, alignItems: 'center', justifyContent: 'center' },
  readinessBadge: { paddingHorizontal: 8, height: 24, backgroundColor: colors.surfaceMuted, alignItems: 'center', justifyContent: 'center' },
  readinessBadgeReady: { backgroundColor: colors.positiveSoft },
  readinessText: { color: colors.inkMuted, fontSize: 8, fontWeight: '800', letterSpacing: 0.7 },
  readinessTextReady: { color: colors.positive },
  settingRow: { minHeight: 82, padding: 16, borderBottomWidth: 1, borderBottomColor: colors.line, flexDirection: 'row', alignItems: 'center', gap: 12 },
  settingIcon: { width: 34, height: 34, backgroundColor: colors.surfaceMuted, alignItems: 'center', justifyContent: 'center' },
  settingCopy: { flex: 1 },
  settingTitle: { color: colors.ink, fontSize: 12, fontWeight: '700' },
  settingCaption: { color: colors.inkMuted, fontSize: 10, lineHeight: 15, marginTop: 4 },
  disclaimer: { color: colors.inkFaint, fontSize: 10, marginTop: 18, lineHeight: 15 },
});
