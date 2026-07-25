function localeDateString(value: string, options: Intl.DateTimeFormatOptions): string {
  return new Date(value).toLocaleString('en-US', options);
}

export function formatAxisDate(value: string, includeTime: boolean): string {
  return localeDateString(value, {
    month: 'short',
    day: 'numeric',
    ...(includeTime ? { hour: 'numeric' as const, minute: '2-digit' as const } : {}),
  });
}

export function formatTrackingDate(value: string, includeTime: boolean): string {
  return localeDateString(value, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    ...(includeTime ? { hour: 'numeric' as const, minute: '2-digit' as const } : {}),
  });
}

function trimTrailingZero(value: number): string {
  return value.toFixed(1).replace(/\.0$/, '');
}

function roundToOneDecimal(value: number): number {
  return Math.round(value * 10) / 10;
}

export function formatVolume(value: number): string {
  const billions = roundToOneDecimal(value / 1_000_000_000);
  if (billions >= 1) return `${trimTrailingZero(billions)}B`;
  const millions = roundToOneDecimal(value / 1_000_000);
  if (millions >= 1) return `${trimTrailingZero(millions)}M`;
  const thousands = roundToOneDecimal(value / 1_000);
  if (thousands >= 1) return `${trimTrailingZero(thousands)}K`;
  return String(Math.round(value));
}
