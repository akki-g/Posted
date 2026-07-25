import { colors } from '@/theme/tokens';

export function momentumColor(values: number[], index: number, lookback = 3): string {
  const from = Math.max(0, index - lookback);
  if (from === index || values[index] == null || values[from] == null) return colors.inkMuted;
  return values[index] >= values[from] ? colors.positive : colors.negative;
}
