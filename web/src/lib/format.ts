const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Format a number as French-locale currency (e.g. 1 234,50).
 */
export function formatCurrency(amount: number): string {
  return currencyFormatter.format(amount);
}

const countFormatter = new Intl.NumberFormat("fr-FR");

/**
 * Format a count with French thousands separator (e.g. 1 234).
 */
export function formatCount(n: number): string {
  return countFormatter.format(n);
}

/**
 * Format an ISO date string "YYYY-MM-DD" to French "DD/MM/YYYY".
 */
export function formatDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-");
  return `${day}/${month}/${year}`;
}
