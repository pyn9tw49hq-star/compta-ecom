/**
 * Pure module for generating the "Rapport d'Anomalies" PDF.
 * No React dependency — operates on plain data.
 */
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import {
  PAGE_WIDTH,
  MARGIN,
  HEAD_STYLE,
  BODY_STYLE,
  fmtDate,
  normSpace,
  channelLabel,
} from "./pdfStyles";
import {
  ANOMALY_TYPE_LABELS,
  SEVERITY_META,
} from "@/components/AnomaliesPanel";
import type { Anomaly } from "./types";
import type { DateRange } from "./datePresets";

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface AnomalyPdfSections {
  errors: boolean;
  warnings: boolean;
  infos: boolean;
  types: Record<string, boolean>;
  channels: Set<string>;
}

export interface AnomalyPdfData {
  anomalies: Anomaly[];
  sections: AnomalyPdfSections;
  groupBy: "severity" | "canal" | "type";
  dateRange: DateRange;
  generatedAt: string;
  channels: string[];
}

// ---------------------------------------------------------------------------
// Severity colors for PDF group headers
// ---------------------------------------------------------------------------

const SEVERITY_COLORS: Record<string, { bg: [number, number, number]; text: [number, number, number] }> = {
  error: { bg: [254, 226, 226], text: [153, 27, 27] },
  warning: { bg: [255, 237, 213], text: [154, 52, 18] },
  info: { bg: [219, 234, 254], text: [30, 64, 175] },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getTypeLabel(type: string): string {
  return ANOMALY_TYPE_LABELS[type] ?? type;
}

function getSeverityLabel(severity: string): string {
  return SEVERITY_META[severity]?.label ?? severity;
}

/** Filter anomalies based on sections config. */
function filterAnomalies(anomalies: Anomaly[], sections: AnomalyPdfSections): Anomaly[] {
  return anomalies.filter((a) => {
    // Severity filter
    if (a.severity === "error" && !sections.errors) return false;
    if (a.severity === "warning" && !sections.warnings) return false;
    if (a.severity === "info" && !sections.infos) return false;

    // Channel filter
    if (!sections.channels.has(a.canal)) return false;

    // Type filter
    if (a.type in sections.types && !sections.types[a.type]) return false;
    return true;
  });
}

/** Group anomalies by a key function. */
function groupBy<T>(items: T[], keyFn: (item: T) => string): Map<string, T[]> {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const key = keyFn(item);
    const group = map.get(key) ?? [];
    group.push(item);
    map.set(key, group);
  }
  return map;
}

/** Build download filename: anomalies-YYYY-MM-DD.pdf */
function buildFilename(): string {
  const now = new Date();
  return `anomalies-${now.toISOString().slice(0, 10)}.pdf`;
}

// ---------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------

function renderHeader(doc: jsPDF, data: AnomalyPdfData, filteredCount: number, y: number): number {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("RAPPORT D'ANOMALIES", PAGE_WIDTH / 2, y, { align: "center" });
  y += 7;

  doc.setFontSize(11);
  doc.setTextColor(100);
  doc.text("MAPP E-COMMERCE", PAGE_WIDTH / 2, y, { align: "center" });
  y += 8;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  const periodStr = `P\u00e9riode : ${fmtDate(data.dateRange.from)} - ${fmtDate(data.dateRange.to)}`;
  doc.text(periodStr, PAGE_WIDTH / 2, y, { align: "center" });
  y += 5;

  const countStr = `${filteredCount} anomalie${filteredCount > 1 ? "s" : ""} incluse${filteredCount > 1 ? "s" : ""}`;
  doc.text(countStr, PAGE_WIDTH / 2, y, { align: "center" });
  y += 5;

  doc.setTextColor(150);
  doc.setFontSize(8);
  doc.text(`G\u00e9n\u00e9r\u00e9 le ${data.generatedAt}`, PAGE_WIDTH / 2, y, { align: "center" });
  y += 2;

  // Separator line
  doc.setDrawColor(200);
  doc.setLineWidth(0.3);
  doc.line(MARGIN, y, PAGE_WIDTH - MARGIN, y);
  y += 6;

  doc.setTextColor(0);
  return y;
}

function renderGroupTitle(
  doc: jsPDF,
  title: string,
  count: number,
  y: number,
  colors?: { bg: [number, number, number]; text: [number, number, number] },
): number {
  // Page break check
  if (y > 260) {
    doc.addPage();
    y = MARGIN + 5;
  }

  if (colors) {
    // Colored banner for severity groups
    doc.setFillColor(colors.bg[0], colors.bg[1], colors.bg[2]);
    doc.roundedRect(MARGIN, y - 4, PAGE_WIDTH - 2 * MARGIN, 7, 1, 1, "F");
    doc.setTextColor(colors.text[0], colors.text[1], colors.text[2]);
  } else {
    doc.setTextColor(41, 50, 65);
  }

  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.text(`${normSpace(title)} (${count})`, MARGIN + 2, y);
  y += 6;

  doc.setTextColor(0);
  return y;
}

function renderAnomalyTable(doc: jsPDF, anomalies: Anomaly[], y: number): number {
  const head = [["S\u00e9v\u00e9rit\u00e9", "Type", "Canal", "R\u00e9f\u00e9rence", "D\u00e9tail"]];
  const body = anomalies.map((a) => [
    getSeverityLabel(a.severity),
    normSpace(getTypeLabel(a.type)),
    channelLabel(a.canal),
    a.reference || "-",
    normSpace(a.detail),
  ]);

  autoTable(doc, {
    startY: y,
    margin: { left: MARGIN, right: MARGIN },
    head,
    body,
    headStyles: HEAD_STYLE,
    bodyStyles: { ...BODY_STYLE, fontSize: 8 },
    columnStyles: {
      0: { cellWidth: 22 },
      1: { cellWidth: 35 },
      2: { cellWidth: 25 },
      3: { cellWidth: 28 },
      4: { cellWidth: "auto" },
    },
    showHead: "everyPage",
    styles: { overflow: "linebreak", cellPadding: 2 },
  });

  return (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 6;
}

function renderFooters(doc: jsPDF): void {
  const pageCount = doc.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(140);
    const footer = `MAPP E-Commerce - Rapport d'Anomalies    Page ${i}/${pageCount}`;
    doc.text(footer, PAGE_WIDTH / 2, 290, { align: "center" });
  }
  doc.setTextColor(0);
}

// ---------------------------------------------------------------------------
// Grouping strategies
// ---------------------------------------------------------------------------

function groupBySeverity(anomalies: Anomaly[]): { key: string; label: string; items: Anomaly[]; colors?: { bg: [number, number, number]; text: [number, number, number] } }[] {
  const severityOrder = ["error", "warning", "info"];
  const grouped = groupBy(anomalies, (a) => a.severity);
  return severityOrder
    .filter((s) => grouped.has(s))
    .map((s) => ({
      key: s,
      label: getSeverityLabel(s) + "s",
      items: grouped.get(s)!,
      colors: SEVERITY_COLORS[s],
    }));
}

function groupByCanal(anomalies: Anomaly[]): { key: string; label: string; items: Anomaly[] }[] {
  const grouped = groupBy(anomalies, (a) => a.canal);
  return Array.from(grouped.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, items]) => ({
      key,
      label: channelLabel(key),
      items,
    }));
}

function groupByType(anomalies: Anomaly[]): { key: string; label: string; items: Anomaly[] }[] {
  const grouped = groupBy(anomalies, (a) => a.type);
  return Array.from(grouped.entries())
    .sort(([a], [b]) => getTypeLabel(a).localeCompare(getTypeLabel(b)))
    .map(([key, items]) => ({
      key,
      label: getTypeLabel(key),
      items,
    }));
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function generateAnomalyPdf(data: AnomalyPdfData): void {
  const filtered = filterAnomalies(data.anomalies, data.sections);
  if (filtered.length === 0) return;

  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

  let y = MARGIN + 5;
  y = renderHeader(doc, data, filtered.length, y);

  // Build groups
  let groups: { key: string; label: string; items: Anomaly[]; colors?: { bg: [number, number, number]; text: [number, number, number] } }[];
  switch (data.groupBy) {
    case "severity":
      groups = groupBySeverity(filtered);
      break;
    case "canal":
      groups = groupByCanal(filtered);
      break;
    case "type":
      groups = groupByType(filtered);
      break;
  }

  for (const group of groups) {
    y = renderGroupTitle(doc, group.label, group.items.length, y, group.colors);
    y = renderAnomalyTable(doc, group.items, y);
  }

  renderFooters(doc);
  doc.save(buildFilename());
}
