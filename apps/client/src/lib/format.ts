export function money(value: string | number, compact = false): string {
  const amount = Number(value);
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : 2,
  }).format(amount);
}

export function number(value: string | number, digits = 2): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(Number(value));
}

export function percent(value: string | number): string {
  const amount = Number(value);
  return `${amount >= 0 ? '+' : ''}${amount.toFixed(2)}%`;
}

export function signedMoney(value: string | number): string {
  const amount = Number(value);
  return `${amount >= 0 ? '+' : '-'}${money(Math.abs(amount))}`;
}

export function relativeTime(timestamp: string): string {
  const elapsed = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.max(0, Math.floor(elapsed / 60_000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

