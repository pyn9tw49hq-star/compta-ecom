/**
 * Utility to compute visual card keys for anomaly deduplication.
 *
 * The key returned corresponds exactly to ONE visual card in AnomaliesPanel.tsx.
 * This ensures anomaly counters match the number of visible cards.
 */
import type { Anomaly } from "./types";

/** Types that are hidden from counts (never rendered as cards). */
export const HIDDEN_TYPES = new Set(["missing_payout_summary", "negative_solde"]);

/**
 * Extract payment method name from a direct_payment anomaly detail string.
 * Mirrors the logic in AnomaliesPanel.tsx.
 */
function extractPaymentMethod(detail: string): string {
  const separators = [" — ", " - ", ": "];
  for (const sep of separators) {
    const idx = detail.indexOf(sep);
    if (idx > 0) {
      return detail.substring(0, idx).trim();
    }
  }
  return detail.trim();
}

/**
 * Compute the visual card key for an anomaly.
 *
 * The key uniquely identifies which visual card this anomaly belongs to
 * in AnomaliesPanel.tsx. Two anomalies with the same key will be rendered
 * in the same card; different keys mean different cards.
 *
 * Grouped types (1 card per group):
 * - missing_payout        → type|canal|severity
 * - payment_delay          → type|canal|severity
 * - orphan_sale/summary    → type_group|canal|severity  (merged into one group)
 * - direct_payment         → type|canal|severity|paymentMethod
 * - tva_mismatch           → type|canal|severity|rateKey
 *
 * All other types: 1 card per anomaly → type|canal|severity|reference|detail_hash
 */
export function getVisualCardKey(a: Anomaly): string {
  const base = `${a.type}|${a.canal}|${a.severity}`;

  switch (a.type) {
    // Grouped by canal only — 1 card per (type, canal, severity)
    case "missing_payout":
    case "payment_delay":
      return base;

    // orphan_sale and orphan_sale_summary are merged into the same card per canal
    case "orphan_sale":
    case "orphan_sale_summary":
      return `orphan_sale_group|${a.canal}|${a.severity}`;

    // Sub-grouped by payment method
    case "direct_payment": {
      const method = extractPaymentMethod(a.detail);
      return `${base}|${method}`;
    }

    // Sub-grouped by rate discrepancy
    case "tva_mismatch": {
      const rateKey = `${a.actual_value ?? "?"}% au lieu de ${a.expected_value ?? "?"}%`;
      return `${base}|${rateKey}`;
    }

    // Hidden types — should never be counted but return a key anyway
    case "missing_payout_summary":
    case "negative_solde":
      return base;

    // All other types: each anomaly is its own card
    default:
      return `${base}|${a.reference}|${a.detail}`;
  }
}

/**
 * Count unique visual cards per severity level.
 * Excludes HIDDEN_TYPES from the count.
 */
export function countVisualCardsBySeverity(anomalies: Anomaly[]): Record<string, number> {
  const counts: Record<string, number> = { error: 0, warning: 0, info: 0 };
  const seen = new Set<string>();
  for (const a of anomalies) {
    if (HIDDEN_TYPES.has(a.type)) continue;
    const key = getVisualCardKey(a);
    if (!seen.has(key)) {
      seen.add(key);
      counts[a.severity] = (counts[a.severity] ?? 0) + 1;
    }
  }
  return counts;
}

/**
 * Count total unique visual cards (excluding HIDDEN_TYPES).
 */
export function countVisualCards(anomalies: Anomaly[]): number {
  const seen = new Set<string>();
  for (const a of anomalies) {
    if (HIDDEN_TYPES.has(a.type)) continue;
    seen.add(getVisualCardKey(a));
  }
  return seen.size;
}
