import { chartCategorical } from '@/theme/tokens';

// Categorical identity color only — never a semantic/state color (teal and
// blue are claimed roles elsewhere and teal reads as gray in a categorical
// role; see theme/tokens.ts's `chartCategorical` doc comment).
const PALETTE = chartCategorical;

function hashString(value: string): number {
  let hash = 7;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function withAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function symbolColor(symbol: string): { background: string; foreground: string } {
  const foreground = PALETTE[hashString(symbol) % PALETTE.length];
  return { background: withAlpha(foreground, 0.14), foreground };
}
