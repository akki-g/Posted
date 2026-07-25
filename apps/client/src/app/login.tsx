import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useEffect } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { BrandMark } from '@/components/BrandMark';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { colors, radius, spacing, type as typeTokens } from '@/theme/tokens';

export default function LoginScreen() {
  const router = useRouter();
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
    <View style={styles.root}>
      <View style={styles.card}>
        <BrandMark />
        <Text style={styles.title}>Sign in to Posted</Text>
        <Text style={styles.caption}>
          Use your Google account to personalize your dashboard.
        </Text>
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
          <Text style={styles.caption}>
            Sign-in is available on the web app for now.
          </Text>
        )}
        {authorize.isError ? (
          <Text style={styles.error}>{authorize.error.message}</Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.canvas,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  card: {
    width: '100%',
    maxWidth: 380,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.lg,
    padding: spacing.xl,
    gap: spacing.sm,
    alignItems: 'flex-start',
  },
  title: {
    color: colors.ink,
    fontSize: typeTokens.title,
    fontWeight: '600',
    marginTop: spacing.md,
  },
  caption: {
    color: colors.inkMuted,
    fontSize: typeTokens.body,
    lineHeight: 20,
  },
  button: {
    marginTop: spacing.sm,
    height: 46,
    width: '100%',
    borderRadius: radius.md,
    backgroundColor: colors.teal,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonPressed: { opacity: 0.85 },
  buttonText: { color: colors.white, fontSize: typeTokens.body, fontWeight: '700' },
  error: { color: colors.negative, fontSize: typeTokens.caption, marginTop: spacing.xs },
});
