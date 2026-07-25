import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { usePlaidLink } from 'react-plaid-link';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { api } from '@/lib/api';
import { colors } from '@/theme/tokens';

type Props = { disabled?: boolean };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The brokerage connection could not be completed.';
}

export function PlaidInvestmentLinkButton({ disabled = false }: Props) {
  const queryClient = useQueryClient();
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const refreshInvestingQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['connections'] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      queryClient.invalidateQueries({ queryKey: ['holdings'] }),
    ]);
  };

  const { open, ready } = usePlaidLink({
    token: linkToken ?? '',
    onEvent: () => undefined,
    onExit: (plaidError) => {
      if (plaidError) setError(plaidError.display_message || plaidError.error_message);
      setBusy(false);
      setLinkToken(null);
    },
    onSuccess: (publicToken) => {
      void (async () => {
        try {
          const connection = await api.exchangePlaidInvestmentsToken(publicToken);
          const sync = await api.sync(connection.id);
          await refreshInvestingQueries();
          setSuccess(sync.message);
        } catch (connectionError) {
          setError(errorMessage(connectionError));
        } finally {
          setBusy(false);
          setLinkToken(null);
        }
      })();
    },
  });

  useEffect(() => {
    if (linkToken && ready) open();
  }, [linkToken, ready, open]);

  const connect = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const token = await api.plaidInvestmentsLinkToken();
      setLinkToken(token.link_token);
    } catch (tokenError) {
      setError(errorMessage(tokenError));
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
          {busy ? 'Connecting securely…' : disabled ? 'Plaid setup required' : 'Connect a brokerage'}
        </Text>
      </Pressable>
      <Text style={styles.help}>
        Posted receives read-only holdings and balances; your brokerage credentials stay with Plaid.
      </Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {success ? <Text style={styles.success}>{success}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { borderTopWidth: 1, borderTopColor: colors.line, padding: 16, gap: 8 },
  button: {
    minHeight: 48, backgroundColor: colors.tealDark, alignItems: 'center',
    justifyContent: 'center', paddingHorizontal: 16,
  },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.82 },
  buttonText: { color: colors.surface, fontSize: 12, fontWeight: '800' },
  help: { color: colors.inkMuted, fontSize: 10, lineHeight: 15 },
  error: { color: colors.negative, fontSize: 10, lineHeight: 15 },
  success: { color: colors.positive, fontSize: 10, lineHeight: 15, fontWeight: '700' },
});
