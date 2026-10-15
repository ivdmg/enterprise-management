/**
 * Formatting utilities for Russian locale
 */

const ruNumberFormat = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 0,
});

const ruCurrencyFormat = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  maximumFractionDigits: 0,
});

const ruDateFormat = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});

const ruShortDateFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
});

export function formatNumber(value: number): string {
  return ruNumberFormat.format(value);
}

export function formatCurrency(value: number): string {
  return ruCurrencyFormat.format(value);
}

export function formatCurrencyShort(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)} млн`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(0)} тыс.`;
  }
  return formatNumber(value);
}

export function formatDate(dateStr: string): string {
  return ruDateFormat.format(new Date(dateStr));
}

export function formatShortDate(dateStr: string): string {
  return ruShortDateFormat.format(new Date(dateStr));
}

export function formatFileSize(bytes: number): string {
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} МБ`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(0)} КБ`;
  return `${bytes} Б`;
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}
