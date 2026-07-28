import { Redirect } from 'expo-router';

// Money is no longer a separate destination — it's the Cash lens of the
// unified Position Spine at "/". Kept as a route only for deep links and
// bookmarks made before the redesign.
export default function MoneyRedirect() {
  return <Redirect href="/?lens=cash" />;
}
