/**
 * Chart color palette for dashboard visualizations.
 * Hex values for light/dark themes — Recharts needs concrete colors, not CSS vars.
 */

export const CHANNEL_CHART_COLORS: Record<string, { light: string; dark: string }> = {
  shopify:      { light: "#16a34a", dark: "#4ade80" },   // green-600 / green-400
  manomano:     { light: "#2563eb", dark: "#60a5fa" },   // blue-600 / blue-400
  decathlon:    { light: "#ea580c", dark: "#fb923c" },   // orange-600 / orange-400
  leroy_merlin: { light: "#9333ea", dark: "#c084fc" },   // purple-600 / purple-400
};

const FALLBACK_COLORS = [
  { light: "#0891b2", dark: "#22d3ee" },  // cyan
  { light: "#be185d", dark: "#f472b6" },  // pink
  { light: "#854d0e", dark: "#facc15" },  // yellow
  { light: "#4f46e5", dark: "#818cf8" },  // indigo
];

export const METRIC_COLORS = {
  commissions: { light: "#dc2626", dark: "#f87171" },    // red-600 / red-400
  net_vendeur: { light: "#059669", dark: "#34d399" },    // emerald-600 / emerald-400
};

export const SEVERITY_COLORS: Record<string, { light: string; dark: string }> = {
  error:   { light: "#dc2626", dark: "#f87171" },
  warning: { light: "#ea580c", dark: "#fb923c" },
  info:    { light: "#2563eb", dark: "#60a5fa" },
};

/**
 * Get chart color for a channel, with fallback for unknown channels.
 */
export function getChannelColor(channel: string, isDark: boolean, index = 0): string {
  const entry = CHANNEL_CHART_COLORS[channel];
  if (entry) return isDark ? entry.dark : entry.light;
  const fb = FALLBACK_COLORS[index % FALLBACK_COLORS.length];
  return isDark ? fb.dark : fb.light;
}

/**
 * Conditional color for refund rate thresholds.
 */
export function getRefundRateColor(rate: number, isDark = false): string {
  if (rate < 5) return isDark ? "#4ade80" : "#16a34a";   // green
  if (rate <= 10) return isDark ? "#fb923c" : "#ea580c";  // orange
  return isDark ? "#f87171" : "#dc2626";                  // red
}

/**
 * Get severity color hex.
 */
export function getSeverityColor(severity: string, isDark = false): string {
  const entry = SEVERITY_COLORS[severity];
  if (!entry) return isDark ? "#94a3b8" : "#64748b"; // slate fallback
  return isDark ? entry.dark : entry.light;
}

/** Geo chart neutral palette — blue-tinted slate for dark mode to contrast with hover overlay */
export const GEO_PALETTE: Array<{ light: string; dark: string }> = [
  { light: "#374151", dark: "#93c5fd" },  // gray-700 / blue-300
  { light: "#4b5563", dark: "#7dd3fc" },  // gray-600 / sky-300
  { light: "#6b7280", dark: "#a5b4fc" },  // gray-500 / indigo-300
  { light: "#9ca3af", dark: "#c4b5fd" },  // gray-400 / violet-300
  { light: "#475569", dark: "#86efac" },  // slate-600 / green-300
  { light: "#64748b", dark: "#67e8f9" },  // slate-500 / cyan-300
  { light: "#334155", dark: "#fca5a5" },  // slate-700 / red-300
  { light: "#525c6b", dark: "#fcd34d" },  // custom / amber-300
  { light: "#78849a", dark: "#fdba74" },  // custom / orange-300
  { light: "#3f4e63", dark: "#d8b4fe" },  // custom / purple-300
];

/** Entry type label colors */
export const ENTRY_TYPE_COLORS: Record<string, { light: string; dark: string }> = {
  sale:       { light: "#16a34a", dark: "#4ade80" },
  refund:     { light: "#dc2626", dark: "#f87171" },
  settlement: { light: "#2563eb", dark: "#60a5fa" },
  commission: { light: "#ea580c", dark: "#fb923c" },
  payout:     { light: "#9333ea", dark: "#c084fc" },
  fee:        { light: "#0891b2", dark: "#22d3ee" },
};
