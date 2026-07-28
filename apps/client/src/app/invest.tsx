import { Redirect } from 'expo-router';

// Investing is no longer a separate destination — it's the Investments lens
// of the unified Position Spine at "/". Kept as a route only for deep links
// and bookmarks made before the redesign.
export default function InvestRedirect() {
  return <Redirect href="/?lens=investments" />;
}
