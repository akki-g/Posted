import { Redirect } from 'expo-router';

// The impact feed is now the "Feed" tab of the unified Portfolio detail
// destination at "/portfolio". Kept as a route only for deep links and
// bookmarks made before the four screens were merged into one tabbed page.
export default function FeedRedirect() {
  return <Redirect href="/portfolio?tab=feed" />;
}
