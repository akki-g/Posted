import { colors } from '@/theme/tokens';

const PALETTE = [
  colors.teal,
  colors.blue,
  colors.purple,
  colors.orange,
  colors.indigo,
  colors.pink,
  colors.brown,
] as const;

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
