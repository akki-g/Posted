import { Redirect } from 'expo-router';

// Holdings is now the "Holdings" tab of the unified Portfolio detail
// destination at "/portfolio". Kept as a route only for deep links and
// bookmarks made before the four screens were merged into one tabbed page.
export default function HoldingsRedirect() {
  return <Redirect href="/portfolio?tab=holdings" />;
}
