import { useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

// Avoid hammering Plaid/Schwab on quick back-and-forth navigation between
// screens in the same session; a fresh session (or a long-idle tab) still
// gets an automatic sync on open.
const AUTO_SYNC_STALE_MS = 5 * 60 * 1000;

type SyncableConnection = { id: string; last_synced_at: string | null; demo: boolean };

// Exported for direct unit testing (apps/client/src/lib/useConnectionSync.test.ts)
// — pure functions, no need to render a component to cover their logic.
export function isStale(connections: SyncableConnection[]): boolean {
  return connections.some((connection) => {
    if (!connection.last_synced_at) return true;
    return Date.now() - new Date(connection.last_synced_at).getTime() > AUTO_SYNC_STALE_MS;
  });
}

// Sync every live connection; fall back to a single demo connection (the
// backend runs its own demo-data sync path for it) when there's no live one.
export function targetConnections(connections: SyncableConnection[]): SyncableConnection[] {
  const live = connections.filter((connection) => !connection.demo);
  return live.length > 0 ? live : connections.slice(0, 1);
}

/**
 * Drives provider syncing for a page's live (non-demo) connections: syncs
 * automatically once when the page opens with stale data, and exposes a
 * mutation the page's manual refresh (button or pull-to-refresh) can call to
 * force a sync unconditionally.
 */
export function useConnectionSync({
  connections,
  syncFn,
  invalidateKeys,
}: {
  connections: SyncableConnection[] | undefined;
  syncFn: (connectionId: string) => Promise<unknown>;
  invalidateKeys: string[][];
}) {
  const queryClient = useQueryClient();
  const autoSyncAttempted = useRef(false);

  const sync = useMutation({
    mutationFn: async () => {
      if (!connections || connections.length === 0) return;
      const targets = targetConnections(connections);
      await Promise.all(targets.map((connection) => syncFn(connection.id)));
    },
    onSuccess: async () => {
      await Promise.all(
        invalidateKeys.map((key) => queryClient.invalidateQueries({ queryKey: key })),
      );
    },
  });

  useEffect(() => {
    if (autoSyncAttempted.current || !connections) return;
    autoSyncAttempted.current = true;
    if (isStale(targetConnections(connections))) {
      sync.mutate();
    }
    // Only re-run once connections load for the first time; re-syncing on
    // every subsequent data change would defeat the staleness check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connections]);

  return sync;
}
