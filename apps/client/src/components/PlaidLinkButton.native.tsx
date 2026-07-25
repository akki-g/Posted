import { useQueryClient } from '@tanstack/react-query';
import { createPlaidLinkSession } from 'react-native-plaid-link-sdk';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useState } from 'react';

import { api } from '@/lib/api';
import { colors } from '@/theme/tokens';

type Props = {
  disabled?: boolean;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The bank connection could not be completed.';
}

export function PlaidLinkButton({ disabled = false }: Props) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const refreshMoneyQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['money-connections'] }),
      queryClient.invalidateQueries({ queryKey: ['money-overview'] }),
      queryClient.invalidateQueries({ queryKey: ['money-transactions'] }),
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] }),
    ]);
  };

  const connect = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);

    try {
      const token = await api.plaidLinkToken();
      const session = await createPlaidLinkSession({
        token: token.link_token,
        onEvent: () => undefined,
        onExit: (exit) => {
          if (exit.error) {
            setError(exit.error.displayMessage || exit.error.errorMessage);
          }
          setBusy(false);
        },
        onSuccess: (result) => {
          void (async () => {
            try {
              const connection = await api.exchangePlaidToken(result.publicToken);
              const sync = await api.syncMoneyConnection(connection.id);
              await refreshMoneyQueries();
              const skipped = sync.rejected > 0 ? ` ${sync.rejected} could not be read and were skipped.` : '';
              setSuccess(
                sync.normalized > 0
                  ? `Connected and imported ${sync.normalized} transactions.${skipped}`
                  : `Connected. No transactions were available yet.${skipped}`,
              );
            } catch (connectionError) {
              setError(errorMessage(connectionError));
            } finally {
              setBusy(false);
            }
          })();
        },
      });
      await session.open(true);
    } catch (sessionError) {
      setError(errorMessage(sessionError));
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Pressable
        accessibilityRole="button"
        disabled={disabled || busy}
        onPress={() => void connect()}
        style={({ pressed }) => [
          styles.button,
          (disabled || busy) && styles.disabled,
          pressed && !disabled && !busy && styles.pressed,
        ]}>
        <Text style={styles.buttonText}>
          {busy ? 'Connecting securely…' : disabled ? 'Plaid setup required' : 'Connect a bank or card'}
        </Text>
      </Pressable>
      <Text style={styles.help}>
        Posted receives transaction data and balances; your banking credentials stay with Plaid.
      </Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {success ? <Text style={styles.success}>{success}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { borderTopWidth: 1, borderTopColor: colors.line, padding: 16, gap: 8 },
  button: {
    minHeight: 48,
    backgroundColor: colors.tealDark,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
  },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.82 },
  buttonText: { color: colors.surface, fontSize: 12, fontWeight: '800' },
  help: { color: colors.inkMuted, fontSize: 10, lineHeight: 15 },
  error: { color: colors.negative, fontSize: 10, lineHeight: 15 },
  success: { color: colors.positive, fontSize: 10, lineHeight: 15, fontWeight: '700' },
});
