import { Redirect, useLocalSearchParams } from 'expo-router';

// Insider activity is now the "Insiders" tab of the unified Portfolio detail
// destination at "/portfolio". Kept as a route only for deep links and
// bookmarks made before the merge; forwards any ?symbol= through so old
// per-ticker links keep landing on the right analysis.
export default function InsidersRedirect() {
  const { symbol } = useLocalSearchParams<{ symbol?: string }>();
  return (
    <Redirect
      href={{
        pathname: '/portfolio',
        params: symbol ? { tab: 'insiders', symbol: String(symbol) } : { tab: 'insiders' },
      }}
    />
  );
}
