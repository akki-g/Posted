import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { useAuth } from '@/lib/AuthContext';
import { colors, spacing, type as typeTokens } from '@/theme/tokens';

export default function LoginCallbackScreen() {
  const router = useRouter();
  const { signIn } = useAuth();
  const params = useLocalSearchParams<{ session?: string; error?: string }>();

  useEffect(() => {
    if (params.session) {
      signIn(params.session);
      router.replace('/');
    }
  }, [params.session, signIn, router]);

  if (params.error) {
    return (
      <View style={styles.root}>
        <Text style={styles.text}>
          Google sign-in was cancelled or rejected. Return to the login page and try again.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <Text style={styles.text}>Signing you in…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
  text: { color: colors.inkMuted, fontSize: typeTokens.body, textAlign: 'center' },
});
