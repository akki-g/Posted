import {
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  Building2,
  CreditCard,
  Repeat2,
} from 'lucide-react-native';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { money } from '@/lib/format';
import type {
  MoneyAccountSummary,
  MoneyTransactionSummary,
  RecurringStreamSummary,
} from '@/lib/types';
import { colors } from '@/theme/tokens';

export function MoneyAccountList({ accounts }: { accounts: MoneyAccountSummary[] }) {
  return (
    <View>
      {accounts.map((account) => {
        const creditUsed =
          account.credit_limit && Number(account.credit_limit) > 0
            ? Math.min(100, (Number(account.current_balance) / Number(account.credit_limit)) * 100)
            : null;
        const Icon = account.is_liability ? CreditCard : Building2;
        return (
          <View key={account.id} style={styles.accountRow}>
            <View style={styles.accountIcon}>
              <Icon size={17} color={colors.tealDark} strokeWidth={1.8} />
            </View>
            <View style={styles.accountCopy}>
              <Text style={styles.accountName}>{account.name}</Text>
              <Text style={styles.accountMeta}>
                {account.account_type.replace('_', ' ')} · ••{account.mask ?? '—'}
              </Text>
              {creditUsed !== null ? (
                <View style={styles.creditTrack}>
                  <View style={[styles.creditFill, { width: `${creditUsed}%` }]} />
                </View>
              ) : null}
            </View>
            <View style={styles.accountAmountBlock}>
              <Text style={styles.accountAmount}>{money(account.current_balance)}</Text>
              <Text style={styles.accountAvailable}>
                {account.is_liability
                  ? `${creditUsed?.toFixed(0) ?? 0}% utilized`
                  : `${money(account.available_balance ?? account.current_balance)} available`}
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

export function TransactionList({
  transactions,
  emptyLabel = 'No transactions match these filters.',
}: {
  transactions: MoneyTransactionSummary[];
  emptyLabel?: string;
}) {
  const { width } = useWindowDimensions();
  const showDetails = width >= 720;
  if (!transactions.length) {
    return (
      <View style={styles.emptyState}>
        <Text style={styles.emptyText}>{emptyLabel}</Text>
      </View>
    );
  }
  return (
    <View>
      {transactions.map((transaction) => {
        const Icon = transaction.is_transfer
          ? ArrowLeftRight
          : transaction.direction === 'inflow'
            ? ArrowDownLeft
            : ArrowUpRight;
        const positive = transaction.direction === 'inflow' && !transaction.is_transfer;
        const sign = transaction.is_transfer ? '' : positive ? '+' : '−';
        return (
          <View key={transaction.id} style={styles.transactionRow}>
            <View
              style={[
                styles.transactionIcon,
                positive && styles.transactionIconPositive,
                transaction.is_transfer && styles.transactionIconTransfer,
              ]}>
              <Icon
                size={16}
                color={
                  positive
                    ? colors.positive
                    : transaction.is_transfer
                      ? colors.blue
                      : colors.inkMuted
                }
                strokeWidth={1.9}
              />
            </View>
            <View style={styles.transactionCopy}>
              <View style={styles.transactionTitleLine}>
                <Text numberOfLines={1} style={styles.transactionName}>
                  {transaction.merchant_name}
                </Text>
                {transaction.status === 'pending' ? (
                  <View style={styles.pendingBadge}>
                    <Text style={styles.pendingText}>PENDING</Text>
                  </View>
                ) : null}
              </View>
              <Text numberOfLines={1} style={styles.transactionMeta}>
                {new Date(transaction.occurred_at).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })}
                {' · '}
                {transaction.account_name}
              </Text>
            </View>
            {showDetails ? (
              <View style={styles.categoryBadge}>
                <Text numberOfLines={1} style={styles.categoryText}>
                  {transaction.category.replaceAll('_', ' ')}
                </Text>
              </View>
            ) : null}
            <Text
              style={[
                styles.transactionAmount,
                positive && styles.transactionAmountPositive,
                transaction.is_transfer && styles.transactionAmountTransfer,
              ]}>
              {sign}
              {money(transaction.amount)}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

export function SubscriptionList({ streams }: { streams: RecurringStreamSummary[] }) {
  return (
    <View>
      {streams.map((stream) => (
        <View key={stream.id} style={styles.subscriptionRow}>
          <View style={styles.subscriptionIcon}>
            <Repeat2 size={16} color={colors.tealDark} strokeWidth={1.9} />
          </View>
          <View style={styles.subscriptionCopy}>
            <Text style={styles.subscriptionName}>{stream.merchant_name}</Text>
            <Text style={styles.subscriptionMeta}>
              Next expected{' '}
              {new Date(`${stream.next_expected_date}T12:00:00`).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
              })}
              {' · '}
              {Math.round(Number(stream.confidence) * 100)}% confidence
            </Text>
          </View>
          <View style={styles.subscriptionAmountBlock}>
            <Text style={styles.subscriptionAmount}>{money(stream.average_amount)}</Text>
            <Text style={styles.subscriptionFrequency}>/{stream.frequency}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  accountRow: {
    minHeight: 84,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  accountIcon: {
    width: 36,
    height: 36,
    backgroundColor: colors.tealSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  accountCopy: { flex: 1, minWidth: 0 },
  accountName: { color: colors.ink, fontSize: 12, fontWeight: '700' },
  accountMeta: { color: colors.inkMuted, fontSize: 10, marginTop: 4, textTransform: 'capitalize' },
  accountAmountBlock: { alignItems: 'flex-end' },
  accountAmount: { color: colors.ink, fontSize: 13, fontWeight: '700', fontVariant: ['tabular-nums'] },
  accountAvailable: { color: colors.inkMuted, fontSize: 9, marginTop: 5 },
  creditTrack: { height: 3, marginTop: 8, backgroundColor: colors.surfaceStrong, maxWidth: 150 },
  creditFill: { height: 3, backgroundColor: colors.warning },
  transactionRow: {
    minHeight: 72,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  transactionIcon: { width: 34, height: 34, backgroundColor: colors.surfaceMuted, alignItems: 'center', justifyContent: 'center' },
  transactionIconPositive: { backgroundColor: colors.positiveSoft },
  transactionIconTransfer: { backgroundColor: colors.blueSoft },
  transactionCopy: { flex: 1, minWidth: 80 },
  transactionTitleLine: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  transactionName: { color: colors.ink, fontSize: 12, fontWeight: '700', flexShrink: 1 },
  transactionMeta: { color: colors.inkMuted, fontSize: 9, marginTop: 5 },
  pendingBadge: { backgroundColor: colors.warningSoft, paddingHorizontal: 5, paddingVertical: 2 },
  pendingText: { color: colors.warning, fontSize: 7, fontWeight: '800', letterSpacing: 0.5 },
  categoryBadge: { width: 150, paddingHorizontal: 8 },
  categoryText: { color: colors.inkFaint, fontSize: 9, textTransform: 'capitalize' },
  transactionAmount: { width: 92, textAlign: 'right', color: colors.ink, fontSize: 12, fontWeight: '700', fontVariant: ['tabular-nums'] },
  transactionAmountPositive: { color: colors.positive },
  transactionAmountTransfer: { color: colors.blue },
  subscriptionRow: {
    minHeight: 76,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 11,
  },
  subscriptionIcon: { width: 34, height: 34, backgroundColor: colors.tealSoft, alignItems: 'center', justifyContent: 'center' },
  subscriptionCopy: { flex: 1 },
  subscriptionName: { color: colors.ink, fontSize: 12, fontWeight: '700' },
  subscriptionMeta: { color: colors.inkMuted, fontSize: 9, marginTop: 5 },
  subscriptionAmountBlock: { alignItems: 'flex-end' },
  subscriptionAmount: { color: colors.ink, fontSize: 12, fontWeight: '700', fontVariant: ['tabular-nums'] },
  subscriptionFrequency: { color: colors.inkMuted, fontSize: 9, marginTop: 3 },
  emptyState: { minHeight: 130, alignItems: 'center', justifyContent: 'center', padding: 20 },
  emptyText: { color: colors.inkMuted, fontSize: 11, textAlign: 'center' },
});
