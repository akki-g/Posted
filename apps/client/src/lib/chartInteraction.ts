export type SourceInterval = '1Min' | '1Day';

export type ResolutionOption = {
  key: 'source' | '5m' | '15m' | '1w';
  label: string;
  groupSize: number;
};

/**
 * Index of the plotted point nearest to pointer x, for line charts whose
 * points sit at i/(count-1) across the drawn width.
 */
export function pointIndexForX(x: number, width: number, count: number): number {
  if (count <= 1) return 0;
  const safeWidth = Math.max(width, 1);
  const boundedX = Math.max(0, Math.min(x, safeWidth));
  return Math.round((boundedX / safeWidth) * (count - 1));
}

/**
 * Index of the bar column containing pointer x, for bar charts rendered as
 * `count` equal-width columns across the drawn width.
 */
export function barIndexForX(x: number, width: number, count: number): number {
  if (count <= 1) return 0;
  const safeWidth = Math.max(width, 1);
  const boundedX = Math.max(0, Math.min(x, safeWidth));
  return Math.min(count - 1, Math.floor((boundedX / safeWidth) * count));
}

export function availableResolutions(
  sourceInterval: SourceInterval,
  pointCount: number,
): ResolutionOption[] {
  const options: ResolutionOption[] =
    sourceInterval === '1Min'
      ? [
          { key: 'source', label: '1m', groupSize: 1 },
          { key: '5m', label: '5m', groupSize: 5 },
          { key: '15m', label: '15m', groupSize: 15 },
        ]
      : [
          { key: 'source', label: '1D', groupSize: 1 },
          { key: '1w', label: '1W', groupSize: 5 },
        ];
  return options.filter(
    (option) => option.groupSize === 1 || Math.ceil(pointCount / option.groupSize) >= 2,
  );
}
