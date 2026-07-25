import { useCallback, useEffect, useMemo, useState } from 'react';

const MIN_VISIBLE_POINTS = 12;
const WHEEL_ZOOM_FACTOR = 0.88;

export type ChartZoom = {
  start: number;
  end: number;
  lastIndex: number;
  isZoomed: boolean;
  setRange: (start: number, end: number) => void;
  zoomAtRatio: (ratio: number, zoomIn: boolean) => void;
  reset: () => void;
};

export function useChartZoom(count: number, resetKey?: string | number): ChartZoom {
  const [range, setRangeState] = useState<{ start: number; end: number } | null>(null);
  const lastIndex = Math.max(count - 1, 0);

  useEffect(() => {
    setRangeState(null);
  }, [resetKey]);

  const start = range ? Math.max(0, Math.min(Math.round(range.start), lastIndex)) : 0;
  const end = range ? Math.max(start, Math.min(Math.round(range.end), lastIndex)) : lastIndex;
  const isZoomed = start > 0 || end < lastIndex;

  const setRange = useCallback(
    (nextStart: number, nextEnd: number) => {
      const minSpan = Math.min(MIN_VISIBLE_POINTS - 1, lastIndex);
      let boundedStart = Math.max(0, Math.min(nextStart, lastIndex - minSpan));
      let boundedEnd = Math.max(boundedStart + minSpan, Math.min(nextEnd, lastIndex));
      if (boundedEnd > lastIndex) {
        boundedStart -= boundedEnd - lastIndex;
        boundedEnd = lastIndex;
      }
      setRangeState({ start: Math.max(0, boundedStart), end: boundedEnd });
    },
    [lastIndex],
  );

  const zoomAtRatio = useCallback(
    (ratio: number, zoomIn: boolean) => {
      const span = end - start;
      const anchor = start + Math.max(0, Math.min(ratio, 1)) * span;
      const factor = zoomIn ? WHEEL_ZOOM_FACTOR : 1 / WHEEL_ZOOM_FACTOR;
      const minSpan = Math.min(MIN_VISIBLE_POINTS - 1, lastIndex);
      const nextSpan = Math.max(minSpan, Math.min(lastIndex, span * factor));
      const nextStart = anchor - ratio * nextSpan;
      setRange(nextStart, nextStart + nextSpan);
    },
    [start, end, lastIndex, setRange],
  );

  const reset = useCallback(() => setRangeState(null), []);

  return useMemo(
    () => ({ start, end, lastIndex, isZoomed, setRange, zoomAtRatio, reset }),
    [start, end, lastIndex, isZoomed, setRange, zoomAtRatio, reset],
  );
}
