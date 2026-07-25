import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="dark" />
        <Stack screenOptions={{ headerShown: false, animation: 'fade' }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="feed" />
          <Stack.Screen name="holdings" />
          <Stack.Screen name="settings" />
          <Stack.Screen name="money" />
          <Stack.Screen name="transactions" />
          <Stack.Screen name="subscriptions" />
          <Stack.Screen name="invest" />
          <Stack.Screen name="news" />
          <Stack.Screen name="assistant" />
          <Stack.Screen name="event/[id]" />
        </Stack>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
