/**
 * Shared PDF style constants and formatting helpers.
 * Used by generateFlashPdf.ts and generateAnomalyPdf.ts.
 */
import { getChannelMeta } from "./channels";

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

export const PAGE_WIDTH = 210; // A4 mm
export const MARGIN = 14;

// ---------------------------------------------------------------------------
// AutoTable shared styles
// ---------------------------------------------------------------------------

export const HEAD_STYLE = {
  fillColor: [41, 50, 65] as [number, number, number],
  textColor: 255,
  fontStyle: "bold" as const,
  font: "helvetica",
};

export const BODY_STYLE = {
  font: "helvetica",
  fontStyle: "normal" as const,
};

export const TOTAL_STYLE = {
  font: "helvetica",
  fontStyle: "bold" as const,
  fillColor: [235, 237, 240] as [number, number, number],
};

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/**
 * Normalize narrow no-break spaces (U+202F) and no-break spaces (U+00A0)
 * to regular spaces — jsPDF Helvetica (WinAnsiEncoding) can't render U+202F.
 */
export function normSpace(s: string): string {
  return s.replace(/[\u202F\u00A0]/g, " ");
}

/** French number format: "12 345,67 €" */
export function fmt(n: number): string {
  return normSpace(
    new Intl.NumberFormat("fr-FR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n) + " \u20AC"
  );
}

/** French percent format: "12,5 %" */
export function fmtPct(n: number): string {
  return normSpace(
    new Intl.NumberFormat("fr-FR", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(n) + " %"
  );
}

/** Format a Date to "DD/MM/YYYY". */
export function fmtDate(d: Date): string {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

/** Get display label for a channel key. */
export function channelLabel(key: string): string {
  return getChannelMeta(key).label;
}
