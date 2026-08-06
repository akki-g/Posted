import { Manrope_500Medium, Manrope_700Bold } from '@expo-google-fonts/manrope';
import { SpaceMono_400Regular } from '@expo-google-fonts/space-mono';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider } from '@/lib/AuthContext';
import { colors } from '@/theme/tokens';

export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );
  // Space Mono (every measured figure) + Manrope (labels/prose) — the one
  // deliberate typographic exception to the system-font floor, reserved for
  // the redesign's "measured fact" vs. "narrated context" distinction. See
  // theme/tokens.ts's `fontFamily` doc comment.
  const [fontsLoaded] = useFonts({ SpaceMono_400Regular, Manrope_500Medium, Manrope_700Bold });
  if (!fontsLoaded) {
    return <View style={{ flex: 1, backgroundColor: colors.canvas }} />;
  }
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StatusBar style="dark" />
          <Stack screenOptions={{ headerShown: false, animation: 'fade' }}>
            <Stack.Screen name="index" />
            <Stack.Screen name="portfolio" />
            <Stack.Screen name="login" />
            <Stack.Screen name="login/callback" />
            <Stack.Screen name="feed" />
            <Stack.Screen name="holdings" />
            <Stack.Screen name="settings" />
            <Stack.Screen name="money" />
            <Stack.Screen name="transactions" />
            <Stack.Screen name="subscriptions" />
            <Stack.Screen name="invest" />
            <Stack.Screen name="news" />
            <Stack.Screen name="insiders" />
            <Stack.Screen name="assistant" />
            <Stack.Screen name="event/[id]" />
            <Stack.Screen name="stock/[symbol]" />
            <Stack.Screen name="privacy" />
            <Stack.Screen name="terms" />
          </Stack>
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
