/**
 * Pure module for generating the "FLASH E-COMMERCE" PDF report.
 * Landscape A4 slideshow format — one section per page.
 * No React dependency — operates on plain data.
 */
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import { normSpace, fmt, fmtPct, fmtDate, channelLabel } from "./pdfStyles";
import {
  ANOMALY_TYPE_LABELS,
} from "@/components/AnomaliesPanel";
import { countVisualCardsBySeverity } from "./anomalyCardKey";
import type { Summary, Anomaly } from "./types";

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface FlashPdfSections {
  profitability: boolean;
  ventilation: boolean;
  tva: boolean;
  geo: boolean;
  kpis: boolean;
  anomalies: boolean;
}

/** Base64 PNG images captured from DOM charts. */
export interface ChartImages {
  revenuePie?: string;
  commissionPie?: string;
  ventilation?: string;
}

export interface FlashPdfData {
  summary: Summary;
  dateRange: { from: Date; to: Date };
  mode: "ht" | "ttc";
  countryNames: Record<string, string>;
  channels: string[];
  sections: FlashPdfSections;
  generatedAt: Date;
  anomalies: Anomaly[];
  chartImages?: ChartImages;
}

// ---------------------------------------------------------------------------
// UX Design Constants
// ---------------------------------------------------------------------------

const C = {
  primary: [27, 42, 74] as const,       // #1B2A4A
  secondary: [74, 85, 104] as const,     // #4A5568
  accent: [43, 108, 176] as const,       // #2B6CB0
  white: [255, 255, 255] as const,
  rowAlt: [240, 244, 248] as const,      // #F0F4F8
  borderLight: [226, 232, 240] as const, // #E2E8F0
  borderMedium: [203, 213, 224] as const,// #CBD5E0
  textMuted: [160, 174, 192] as const,   // #A0AEC0
  textBody: [45, 55, 72] as const,       // #2D3748

  errorBg: [255, 245, 245] as const,
  errorText: [197, 48, 48] as const,
  warningBg: [255, 250, 240] as const,
  warningText: [192, 86, 33] as const,
  warningAccent: [221, 107, 32] as const,
  infoBg: [235, 248, 255] as const,
  infoText: [43, 108, 176] as const,
};

const CHANNEL_COLORS: Record<string, readonly [number, number, number]> = {
  shopify: [149, 191, 71],      // #95BF47
  manomano: [0, 178, 169],      // #00B2A9
  decathlon: [0, 85, 160],      // #0055A0
  leroy_merlin: [45, 140, 60],  // #2D8C3C
};
const TOTAL_COLOR = C.primary;
function getChannelColor(key: string): readonly [number, number, number] {
  return CHANNEL_COLORS[key] ?? [107, 70, 193]; // fallback purple
}

const L = {
  pageWidth: 297,
  pageHeight: 210,
  margin: 15,
  contentWidth: 267,
  contentStartY: 35,
  contentEndY: 189,
  headerLineY: 27,
  footerLineY: 189,
  tableStartY: 42,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildFilename(dateRange: { from: Date; to: Date }): string {
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return `FLASH-ECOMMERCE_${iso(dateRange.from)}_${iso(dateRange.to)}.pdf`;
}

/** Get period label like "F\u00e9v 2026" from a date range. */
function periodLabel(dateRange: { from: Date; to: Date }): string {
  return `${fmtDate(dateRange.from)} - ${fmtDate(dateRange.to)}`;
}

function getTypeLabel(type: string): string {
  return ANOMALY_TYPE_LABELS[type] ?? type;
}

function getFinalY(doc: jsPDF): number {
  return (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY;
}

const FOOTER_SAFETY_MARGIN = 12; // mm

/** Ensure enough vertical space remains on the current page; adds a new page if needed. */
function ensureSpace(doc: jsPDF, neededHeight: number, currentY: number, data: FlashPdfData): number {
  const maxY = L.footerLineY - FOOTER_SAFETY_MARGIN; // 177mm
  if (currentY + neededHeight > maxY) {
    doc.addPage();
    renderPageHeader(doc, data);
    return L.contentStartY + 2; // 31mm
  }
  return currentY;
}

// ---------------------------------------------------------------------------
// AutoTable style presets (UX design)
// ---------------------------------------------------------------------------

const HEAD_STYLE = {
  fillColor: [...C.primary] as [number, number, number],
  textColor: 255,
  fontStyle: "bold" as const,
  font: "helvetica",
  fontSize: 9,
  cellPadding: { top: 3, bottom: 3, left: 4, right: 4 },
  lineWidth: 0,
};

const BODY_STYLE = {
  font: "helvetica",
  fontStyle: "normal" as const,
  fontSize: 8.5,
  textColor: [...C.textBody] as [number, number, number],
  cellPadding: { top: 2.5, bottom: 2.5, left: 4, right: 4 },
  lineWidth: 0.1,
  lineColor: [...C.borderLight] as [number, number, number],
};

const ALT_ROW_STYLE = {
  fillColor: [...C.rowAlt] as [number, number, number],
};

const TOTAL_ROW_STYLE = {
  font: "helvetica",
  fontStyle: "bold" as const,
  fontSize: 9,
  textColor: [...C.primary] as [number, number, number],
  fillColor: [...C.rowAlt] as [number, number, number],
};

// ---------------------------------------------------------------------------
// Recurring Header / Footer (all pages except title)
// ---------------------------------------------------------------------------

function renderPageHeader(doc: jsPDF, data: FlashPdfData): void {
  // Title
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(...C.secondary);
  doc.text(`Flash E-Commerce \u00B7 ${periodLabel(data.dateRange)}`, L.margin, L.margin + 5);

  // Mode HT/TTC right-aligned
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.text(data.mode.toUpperCase(), L.pageWidth - L.margin, L.margin + 5, { align: "right" });

  // Accent line
  doc.setDrawColor(...C.accent);
  doc.setLineWidth(0.5);
  doc.line(L.margin, L.headerLineY, L.pageWidth - L.margin, L.headerLineY);
}

function renderPageFooter(doc: jsPDF, pageNum: number, pageCount: number, generatedAt: Date): void {
  // Grey line
  doc.setDrawColor(...C.borderMedium);
  doc.setLineWidth(0.3);
  doc.line(L.margin, L.footerLineY, L.pageWidth - L.margin, L.footerLineY);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.setTextColor(...C.textMuted);

  // Date left
  doc.text(`G\u00e9n\u00e9r\u00e9 le ${fmtDate(generatedAt)}`, L.margin, 194);

  // Page center
  doc.text(`Page ${pageNum} / ${pageCount}`, L.pageWidth / 2, 194, { align: "center" });

  // Brand right
  doc.setFont("helvetica", "bold");
  doc.setTextColor(...C.borderMedium);
  doc.text("MAPP", L.pageWidth - L.margin, 194, { align: "right" });
}

// ---------------------------------------------------------------------------
// Section title (used at top of each slide)
// ---------------------------------------------------------------------------

function renderSlideTitle(doc: jsPDF, title: string, subtitle?: string): number {
  let y = L.contentStartY + 2;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.setTextColor(...C.primary);
  doc.text(title, L.margin, y);
  y += 6;

  if (subtitle) {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(11);
    doc.setTextColor(...C.secondary);
    doc.text(subtitle, L.margin, y);
    y += 6;
  }

  return y;
}

// ---------------------------------------------------------------------------
// Page Titre (slide 1)
// ---------------------------------------------------------------------------

function renderTitlePage(doc: jsPDF, data: FlashPdfData): void {
  const cx = L.pageWidth / 2;

  // Accent bar
  doc.setFillColor(...C.accent);
  doc.rect(cx - 40, 72, 80, 3, "F");

  // Title
  doc.setFont("helvetica", "bold");
  doc.setFontSize(28);
  doc.setTextColor(...C.primary);
  doc.text("Flash E-Commerce", cx, 84, { align: "center" });

  // Period
  doc.setFont("helvetica", "normal");
  doc.setFontSize(14);
  doc.setTextColor(...C.secondary);
  doc.text(`P\u00e9riode : ${periodLabel(data.dateRange)}`, cx, 96, { align: "center" });

  // Mode
  doc.setFontSize(11);
  doc.text(`Mode : ${data.mode === "ttc" ? "Toutes Taxes Comprises (TTC)" : "Hors Taxes (HT)"}`, cx, 104, { align: "center" });

  // Fine separator
  doc.setFillColor(...C.borderMedium);
  doc.rect(cx - 40, 114, 80, 1, "F");

  // Generated date
  doc.setFontSize(10);
  doc.setTextColor(...C.textMuted);
  doc.text(`G\u00e9n\u00e9r\u00e9 le ${fmtDate(data.generatedAt)}`, cx, 122, { align: "center" });

}

// ---------------------------------------------------------------------------
// Page KPIs (slide 2)
// ---------------------------------------------------------------------------

function renderKpisPage(doc: jsPDF, data: FlashPdfData): void {
  doc.addPage();
  renderPageHeader(doc, data);

  const y = renderSlideTitle(doc, "KPIs par Canal de Vente", "Synth\u00e8se des indicateurs cl\u00e9s");

  const { summary, channels, mode } = data;
  const isHt = mode === "ht";
  const allChannels = channels.length > 1 ? ["total", ...channels] : channels;
  const nCards = allChannels.length;
  const GAP_BETWEEN_CARDS = 5;
  // Allow up to 6 cards in a single row to avoid overflow beyond printable area
  const MAX_CARDS_PER_ROW = nCards <= 6 ? Math.max(nCards, 4) : 4;
  const CARD_PADDING = 4;
  const contentWidth = 267; // 297 - 2 * 15mm margins
  const multiRow = nCards > MAX_CARDS_PER_ROW;
  const valueFontSize = multiRow ? 14 : nCards >= 5 ? 13 : nCards === 4 ? 16 : 24;
  const labelFontSize = multiRow ? 7 : nCards >= 5 ? 6.5 : 8;

  // KPI definitions
  const totalTx = channels.reduce((s, c) => s + (summary.transactions_par_canal[c] ?? 0), 0);
  const totalCa = channels.reduce((s, c) => s + (isHt ? summary.ca_par_canal[c]?.ht ?? 0 : summary.ca_par_canal[c]?.ttc ?? 0), 0);
  const totalNet = isHt
    ? channels.reduce((s, c) => s + (summary.net_vendeur_ht_par_canal?.[c] ?? 0), 0)
    : channels.reduce((s, c) => s + (summary.net_vendeur_par_canal[c] ?? 0), 0);
  const totalRemb = totalTx > 0
    ? channels.reduce((s, c) => s + (summary.remboursements_par_canal[c]?.count ?? 0), 0) / totalTx * 100
    : 0;
  const totalUniqueAnomalyTx = new Set(
    data.anomalies.map(a => `${a.canal}:${a.reference}`)
  ).size;
  const totalAnomalyRate = totalTx > 0 ? Math.min(100, totalUniqueAnomalyTx / totalTx * 100) : 0;

  function getKpis(channel: string): { value: string; label: string }[] {
    const netLabel = isHt ? "Net Vendeur HT" : "Net Vendeur TTC";
    if (channel === "total") {
      return [
        { value: fmt(totalCa), label: `CA Total ${isHt ? "HT" : "TTC"}` },
        { value: fmt(totalNet), label: netLabel },
        { value: String(totalTx), label: "Nb Transactions" },
        { value: fmtPct(Math.round(totalRemb * 10) / 10), label: "Tx Remboursement" },
        { value: fmtPct(Math.round(totalAnomalyRate * 10) / 10), label: "Tx Anomalies" },
      ];
    }
    const ca = isHt ? summary.ca_par_canal[channel]?.ht ?? 0 : summary.ca_par_canal[channel]?.ttc ?? 0;
    const net = isHt
      ? (summary.net_vendeur_ht_par_canal?.[channel] ?? 0)
      : (summary.net_vendeur_par_canal[channel] ?? 0);
    const tx = summary.transactions_par_canal[channel] ?? 0;
    const remb = summary.taux_remboursement_par_canal[channel] ?? 0;
    const chUniqueAnomalyTx = new Set(
      data.anomalies.filter((a) => a.canal === channel).map(a => `${a.canal}:${a.reference}`)
    ).size;
    const anomRate = tx > 0 ? Math.min(100, chUniqueAnomalyTx / tx * 100) : 0;
    return [
      { value: fmt(ca), label: `CA Total ${isHt ? "HT" : "TTC"}` },
      { value: fmt(net), label: netLabel },
      { value: String(tx), label: "Nb Transactions" },
      { value: fmtPct(Math.round(remb * 10) / 10), label: "Tx Remboursement" },
      { value: fmtPct(Math.round(anomRate * 10) / 10), label: "Tx Anomalies" },
    ];
  }

  const kpiBlockH = nCards >= 5 ? 22 : 26;
  const cardH = 8 + 5 * kpiBlockH; // channel name header + 5 KPIs
  const sepPad = CARD_PADDING;
  const ROW_GAP = 6; // mm between rows

  // Split cards into rows
  const rows: string[][] = [];
  for (let i = 0; i < allChannels.length; i += MAX_CARDS_PER_ROW) {
    rows.push(allChannels.slice(i, i + MAX_CARDS_PER_ROW));
  }

  let rowY = y + 2;
  for (const row of rows) {
    const rowCardsPerRow = row.length;
    const rowTotalGaps = (rowCardsPerRow + 1) * GAP_BETWEEN_CARDS;
    const rowCardW = (contentWidth - rowTotalGaps) / rowCardsPerRow;

    for (let i = 0; i < row.length; i++) {
      const ch = row[i];
      const x = L.margin + GAP_BETWEEN_CARDS + i * (rowCardW + GAP_BETWEEN_CARDS);
      const color = ch === "total" ? TOTAL_COLOR : getChannelColor(ch);

      // Card outline
      doc.setDrawColor(...C.borderLight);
      doc.setLineWidth(0.3);
      doc.setFillColor(...C.white);
      if (ch === "total") {
        doc.setFillColor(247, 250, 252); // very light #F7FAFC
      }
      doc.rect(x, rowY, rowCardW, cardH, "FD");

      // Left colored border
      doc.setFillColor(color[0], color[1], color[2]);
      doc.rect(x, rowY, 2, cardH, "F");

      // Channel name header
      doc.setFillColor(...C.rowAlt);
      doc.rect(x + 2, rowY, rowCardW - 2, 8, "F");
      doc.setFont("helvetica", "bold");
      doc.setFontSize(nCards >= 5 ? 8.5 : 10);
      doc.setTextColor(...C.primary);
      const label = ch === "total" ? "TOTAL" : channelLabel(ch);
      doc.text(label, x + rowCardW / 2, rowY + 5.5, { align: "center" });

      // KPIs
      const kpis = getKpis(ch);
      for (let k = 0; k < kpis.length; k++) {
        const ky = rowY + 8 + k * kpiBlockH;

        // Value
        doc.setFont("helvetica", "bold");
        doc.setFontSize(valueFontSize);
        doc.setTextColor(...C.accent);
        doc.text(kpis[k].value, x + rowCardW / 2, ky + kpiBlockH / 2, { align: "center" });

        // Label
        doc.setFont("helvetica", "normal");
        doc.setFontSize(labelFontSize);
        doc.setTextColor(...C.secondary);
        doc.text(kpis[k].label, x + rowCardW / 2, ky + kpiBlockH / 2 + valueFontSize * 0.35 + 3, { align: "center" });

        // Separator (except after last KPI)
        if (k < kpis.length - 1) {
          doc.setDrawColor(...C.borderLight);
          doc.setLineWidth(0.3);
          doc.line(x + sepPad, ky + kpiBlockH, x + rowCardW - sepPad, ky + kpiBlockH);
        }
      }
    }
    rowY += cardH + ROW_GAP;
  }
}

// ---------------------------------------------------------------------------
// Rentabilité par canal
// ---------------------------------------------------------------------------

function renderProfitabilitySlide(doc: jsPDF, data: FlashPdfData): void {
  doc.addPage();
  renderPageHeader(doc, data);
  const y = renderSlideTitle(doc, "Rentabilité par Canal", "Détail commissions, abonnements et net vendeur HT");

  const { summary, channels } = data;

  const head = [["Canal", "CA HT", "Comm. HT", "Abon. HT", "Remb. HT", "Net Vendeur HT", "Taux comm."]];

  const body = channels.map((c) => {
    const caHt = summary.ca_par_canal[c]?.ht ?? 0;
    const commHt = summary.commissions_par_canal[c]?.ht ?? 0;
    const aboHt = summary.abonnements_par_canal?.[c]?.ht ?? 0;
    const rembHt = summary.remboursements_par_canal[c]?.ht ?? 0;
    const netHt = summary.net_vendeur_ht_par_canal?.[c] ?? 0;
    const rate = caHt > 0 ? fmtPct(Math.round(commHt / caHt * 1000) / 10) : fmtPct(0);
    return [channelLabel(c), fmt(caHt), fmt(commHt), fmt(aboHt), fmt(rembHt), fmt(netHt), rate];
  });

  const totCaHt = channels.reduce((s, c) => s + (summary.ca_par_canal[c]?.ht ?? 0), 0);
  const totCommHt = channels.reduce((s, c) => s + (summary.commissions_par_canal[c]?.ht ?? 0), 0);
  const totAboHt = channels.reduce((s, c) => s + (summary.abonnements_par_canal?.[c]?.ht ?? 0), 0);
  const totRembHt = channels.reduce((s, c) => s + (summary.remboursements_par_canal[c]?.ht ?? 0), 0);
  const totNetHt = channels.reduce((s, c) => s + (summary.net_vendeur_ht_par_canal?.[c] ?? 0), 0);
  const totRate = totCaHt > 0 ? fmtPct(Math.round(totCommHt / totCaHt * 1000) / 10) : fmtPct(0);
  body.push(["TOTAL", fmt(totCaHt), fmt(totCommHt), fmt(totAboHt), fmt(totRembHt), fmt(totNetHt), totRate]);

  // Column widths: Canal(45) + 5 numeric(38 each) + Taux(32) = 267mm total
  autoTable(doc, {
    startY: y,
    margin: { top: L.contentStartY, left: L.margin, right: L.margin, bottom: 25 },
    tableWidth: L.contentWidth,
    head,
    body,
    headStyles: HEAD_STYLE,
    bodyStyles: BODY_STYLE,
    alternateRowStyles: ALT_ROW_STYLE,
    columnStyles: {
      0: { cellWidth: 45 },
      1: { halign: "right", cellWidth: 38 },
      2: { halign: "right", cellWidth: 38 },
      3: { halign: "right", cellWidth: 38 },
      4: { halign: "right", cellWidth: 38 },
      5: { halign: "right", cellWidth: 38 },
      6: { halign: "right", cellWidth: 32 },
    },
    didParseCell(hookData) {
      if (hookData.section === "body" && hookData.row.index === body.length - 1) {
        Object.assign(hookData.cell.styles, TOTAL_ROW_STYLE);
      }
    },
    didDrawPage() {
      renderPageHeader(doc, data);
    },
  });
}

// ---------------------------------------------------------------------------
// Chart image helpers
// ---------------------------------------------------------------------------

/** Insert a chart image as a new page with a title. */
function renderChartImagePage(doc: jsPDF, data: FlashPdfData, title: string, images: { src: string; x: number; y: number; w: number; h: number }[]): void {
  doc.addPage();
  renderPageHeader(doc, data);
  renderSlideTitle(doc, title);

  for (const img of images) {
    doc.addImage(img.src, "PNG", img.x, img.y, img.w, img.h);
  }
}

/** Render the two pie charts (revenue + commission) side by side on a new page. */
function renderPieChartsPage(doc: jsPDF, data: FlashPdfData): void {
  const images: { src: string; x: number; y: number; w: number; h: number }[] = [];
  // Two donut charts side by side with 1:1 ratio (square) to avoid deformation
  // Each 120x120mm, gap between them, centered in 267mm content width
  const chartW = 120;
  const chartH = 120; // 1:1 ratio matches 800x800 canvas
  const gapBetween = 7;
  const totalChartsW = 2 * chartW + gapBetween; // 247mm < 267mm available
  const chartOffsetX = L.margin + (L.contentWidth - totalChartsW) / 2; // center
  const chartY = L.tableStartY + 8;
  if (data.chartImages?.revenuePie) {
    images.push({ src: data.chartImages.revenuePie, x: chartOffsetX, y: chartY, w: chartW, h: chartH });
  }
  if (data.chartImages?.commissionPie) {
    images.push({ src: data.chartImages.commissionPie, x: chartOffsetX + chartW + gapBetween, y: chartY, w: chartW, h: chartH });
  }
  if (images.length > 0) {
    renderChartImagePage(doc, data, "Répartition CA HT & Commissions", images);
  }
}

/** Render the ventilation bar chart image on a new page. */
function renderVentilationChartPage(doc: jsPDF, data: FlashPdfData): void {
  if (data.chartImages?.ventilation) {
    // Single chart full-width: 267mm wide × 145mm tall, flush under title
    const chartW = L.contentWidth;
    const chartH = 145;
    const chartY = L.tableStartY;
    renderChartImagePage(doc, data, "Ventilation CA — Graphique", [
      { src: data.chartImages.ventilation, x: L.margin, y: chartY, w: chartW, h: chartH },
    ]);
  }
}

function renderVentilationSlide(doc: jsPDF, data: FlashPdfData): void {
  doc.addPage();
  renderPageHeader(doc, data);
  const y = renderSlideTitle(doc, "Ventilation CA", "R\u00e9partition Produits / Frais de port");

  const { summary, channels } = data;

  const head = [["Canal", "CA Produits HT", "CA Frais de port HT", "CA Total HT"]];
  const body = channels.map((c) => {
    const v = summary.ventilation_ca_par_canal[c];
    return [channelLabel(c), fmt(v.produits_ht), fmt(v.port_ht), fmt(v.total_ht)];
  });

  const totProd = channels.reduce((s, c) => s + summary.ventilation_ca_par_canal[c].produits_ht, 0);
  const totPort = channels.reduce((s, c) => s + summary.ventilation_ca_par_canal[c].port_ht, 0);
  const totHt = channels.reduce((s, c) => s + summary.ca_par_canal[c].ht, 0);
  body.push(["TOTAL", fmt(totProd), fmt(totPort), fmt(totHt)]);

  autoTable(doc, {
    startY: y,
    margin: { top: L.contentStartY, left: L.margin, right: L.margin, bottom: 25 },
    tableWidth: L.contentWidth,
    head,
    body,
    headStyles: HEAD_STYLE,
    bodyStyles: BODY_STYLE,
    alternateRowStyles: ALT_ROW_STYLE,
    columnStyles: {
      0: { cellWidth: 60 },
      1: { halign: "right" },
      2: { halign: "right" },
      3: { halign: "right" },
    },
    didParseCell(hookData) {
      if (hookData.section === "body" && hookData.row.index === body.length - 1) {
        Object.assign(hookData.cell.styles, TOTAL_ROW_STYLE);
      }
    },
    didDrawPage() {
      renderPageHeader(doc, data);
    },
  });
}

function renderTvaSlide(doc: jsPDF, data: FlashPdfData): void {
  doc.addPage();
  renderPageHeader(doc, data);
  let y = renderSlideTitle(doc, "Fiscalit\u00e9 \u2014 TVA Collect\u00e9e", "D\u00e9tail par canal et par pays/taux");

  const { summary, channels } = data;

  for (const canal of channels) {
    const tvaPays = summary.tva_par_pays_par_canal[canal];
    if (!tvaPays || Object.keys(tvaPays).length === 0) continue;

    y = ensureSpace(doc, 20, y, data);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...C.primary);
    doc.text(channelLabel(canal), L.margin, y);
    y += 5;

    const head = [["Pays", "Taux TVA", "Montant TVA"]];
    const body: string[][] = [];
    const continuationRows = new Set<number>();
    for (const [pays, rows] of Object.entries(tvaPays)) {
      const filteredRows = rows.filter(r => Math.abs(r.montant) >= 0.01);
      if (filteredRows.length === 0) continue;
      const displayPays = pays || "Non renseigné";
      for (let i = 0; i < filteredRows.length; i++) {
        if (i > 0) continuationRows.add(body.length);
        body.push([displayPays, fmtPct(filteredRows[i].taux), fmt(filteredRows[i].montant)]);
      }
    }
    const totalTva = summary.tva_collectee_par_canal[canal];
    body.push(["TOTAL", "", fmt(totalTva)]);

    autoTable(doc, {
      startY: y,
      margin: { top: L.contentStartY, left: L.margin, right: L.margin, bottom: 25 },
      tableWidth: L.contentWidth,
      head,
      body,
      headStyles: HEAD_STYLE,
      bodyStyles: BODY_STYLE,
      alternateRowStyles: ALT_ROW_STYLE,
      columnStyles: {
        0: { cellWidth: 80 },
        1: { halign: "right" },
        2: { halign: "right" },
      },
      didParseCell(hookData) {
        if (hookData.section === "body" && hookData.row.index === body.length - 1) {
          Object.assign(hookData.cell.styles, TOTAL_ROW_STYLE);
        }
        if (hookData.section === "body" && hookData.column.index === 0 && continuationRows.has(hookData.row.index)) {
          hookData.cell.styles.textColor = [160, 174, 192];
          hookData.cell.styles.fontStyle = "italic";
        }
      },
      didDrawPage() {
        renderPageHeader(doc, data);
      },
    });

    y = getFinalY(doc) + 8;
  }
}

function renderGeoSlide(doc: jsPDF, data: FlashPdfData): void {
  doc.addPage();
  renderPageHeader(doc, data);
  let y = renderSlideTitle(doc, "R\u00e9partition G\u00e9ographique", "CA HT par pays, d\u00e9tail par canal");

  const { summary, channels } = data;

  // Global table
  const globalGeo = summary.repartition_geo_globale;
  const totalCaHt = Object.values(globalGeo).reduce((s, d) => s + d.ca_ht, 0);

  const head = [["Pays", "Transactions", "CA HT", "% du total"]];
  const body = Object.entries(globalGeo).map(([pays, d]) => [
    pays,
    String(d.count),
    fmt(d.ca_ht),
    fmtPct(totalCaHt > 0 ? Math.round(d.ca_ht / totalCaHt * 1000) / 10 : 0),
  ]);

  autoTable(doc, {
    startY: y,
    margin: { top: L.contentStartY, left: L.margin, right: L.margin, bottom: 25 },
    tableWidth: L.contentWidth,
    head,
    body,
    headStyles: HEAD_STYLE,
    bodyStyles: BODY_STYLE,
    alternateRowStyles: ALT_ROW_STYLE,
    columnStyles: {
      0: { cellWidth: 80 },
      1: { halign: "right" },
      2: { halign: "right" },
      3: { halign: "right" },
    },
    didDrawPage() {
      renderPageHeader(doc, data);
    },
  });

  y = getFinalY(doc) + 8;

  // Per-channel breakdown
  for (const canal of channels) {
    const countries = summary.repartition_geo_par_canal[canal];
    if (!countries || Object.keys(countries).length === 0) continue;

    y = ensureSpace(doc, 20, y, data);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...C.primary);
    doc.text(channelLabel(canal), L.margin, y);
    y += 5;

    const cHead = [["Pays", "Transactions", "CA HT"]];
    const cBody = Object.entries(countries).map(([pays, d]) => [
      pays,
      String(d.count),
      fmt(d.ca_ht),
    ]);

    autoTable(doc, {
      startY: y,
      margin: { top: L.contentStartY, left: L.margin, right: L.margin, bottom: 25 },
      tableWidth: L.contentWidth,
      head: cHead,
      body: cBody,
      headStyles: HEAD_STYLE,
      bodyStyles: BODY_STYLE,
      alternateRowStyles: ALT_ROW_STYLE,
      columnStyles: {
        0: { cellWidth: 80 },
        1: { halign: "right" },
        2: { halign: "right" },
      },
      didDrawPage() {
        renderPageHeader(doc, data);
      },
    });

    y = getFinalY(doc) + 8;
  }
}

// ---------------------------------------------------------------------------
// Anomalies slide
// ---------------------------------------------------------------------------

function renderAnomaliesSlide(doc: jsPDF, data: FlashPdfData): void {
  const { anomalies } = data;
  if (anomalies.length === 0) return;

  // === PAGE N: Résumé Anomalies ===
  doc.addPage();
  renderPageHeader(doc, data);
  let y = renderSlideTitle(doc, "Anomalies D\u00e9tect\u00e9es");

  // Count by severity — unique visual cards
  const sevCounts = countVisualCardsBySeverity(anomalies);
  const errCount = sevCounts.error;
  const warnCount = sevCounts.warning;
  const infoCount = sevCounts.info;

  // Subtitle with counts
  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor(...C.secondary);
  const parts: string[] = [];
  if (errCount > 0) parts.push(`${errCount} erreur${errCount > 1 ? "s" : ""}`);
  if (warnCount > 0) parts.push(`${warnCount} avertissement${warnCount > 1 ? "s" : ""}`);
  if (infoCount > 0) parts.push(`${infoCount} info${infoCount > 1 ? "s" : ""}`);
  doc.text(parts.join(" \u00B7 "), L.margin, y);
  y += 8;

  // Severity summary cards — 3 fixed cards centered
  const cardDefs = [
    { count: errCount, label: "Erreurs", bg: C.errorBg, accent: C.errorText, text: C.errorText },
    { count: warnCount, label: "Avertissements", bg: C.warningBg, accent: C.warningAccent, text: C.warningText },
    { count: infoCount, label: "Infos", bg: C.infoBg, accent: C.infoText, text: C.infoText },
  ];
  const cardW = 80;
  const cardGapBetween = 6.5;
  const cardH = 30;
  const totalCardsWidth = 3 * cardW + 2 * cardGapBetween;
  const cardOffsetX = L.margin + (L.contentWidth - totalCardsWidth) / 2;

  for (let i = 0; i < 3; i++) {
    const def = cardDefs[i];
    const x = cardOffsetX + i * (cardW + cardGapBetween);

    // Card background
    doc.setFillColor(def.bg[0], def.bg[1], def.bg[2]);
    doc.rect(x, y, cardW, cardH, "F");

    // Top border accent (2mm)
    doc.setFillColor(def.accent[0], def.accent[1], def.accent[2]);
    doc.rect(x, y, cardW, 2, "F");

    // Count value
    doc.setFont("helvetica", "bold");
    doc.setFontSize(24);
    doc.setTextColor(def.text[0], def.text[1], def.text[2]);
    doc.text(String(def.count), x + cardW / 2, y + 16, { align: "center" });

    // Label
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(...C.secondary);
    doc.text(def.label, x + cardW / 2, y + 24, { align: "center" });
  }

  // === PAGE N+1: Détail Anomalies (forced page break) ===
  doc.addPage();
  renderPageHeader(doc, data);
  y = renderSlideTitle(doc, "D\u00e9tail des anomalies");

  const sevOrder = ["error", "warning", "info"];
  const sorted = [...anomalies].sort((a, b) => sevOrder.indexOf(a.severity) - sevOrder.indexOf(b.severity));

  const sevColors: Record<string, readonly [number, number, number]> = {
    error: C.errorBg,
    warning: C.warningBg,
    info: C.infoBg,
  };
  const sevCodes: Record<string, string> = { error: "ER", warning: "AV", info: "IN" };

  const head = [["S\u00e9v.", "Canal", "Type", "R\u00e9f\u00e9rence", "D\u00e9tail"]];
  const tableBody = sorted.map((a) => [
    sevCodes[a.severity] ?? a.severity,
    channelLabel(a.canal),
    normSpace(getTypeLabel(a.type)),
    a.reference || "-",
    normSpace(a.detail),
  ]);

  autoTable(doc, {
    startY: y,
    margin: { top: L.contentStartY, left: L.margin, right: L.margin, bottom: 25 },
    tableWidth: L.contentWidth,
    head,
    body: tableBody,
    headStyles: HEAD_STYLE,
    bodyStyles: { ...BODY_STYLE, fontSize: 8 },
    columnStyles: {
      0: { cellWidth: 15 },
      1: { cellWidth: 30 },
      2: { cellWidth: 50 },
      3: { cellWidth: 35 },
      4: { cellWidth: "auto" },
    },
    showHead: "everyPage",
    styles: { overflow: "linebreak", cellPadding: 2 },
    didParseCell(hookData) {
      if (hookData.section === "body") {
        const sev = sorted[hookData.row.index]?.severity;
        if (sev && sevColors[sev]) {
          const bg = sevColors[sev];
          hookData.cell.styles.fillColor = [bg[0], bg[1], bg[2]];
        }
      }
    },
    didDrawPage() {
      renderPageHeader(doc, data);
    },
  });
}

// ---------------------------------------------------------------------------
// Footer pass — render footers on all pages except page 1 (title)
// ---------------------------------------------------------------------------

function renderAllFooters(doc: jsPDF, data: FlashPdfData): void {
  const pageCount = doc.getNumberOfPages();
  for (let i = 2; i <= pageCount; i++) {
    doc.setPage(i);
    renderPageFooter(doc, i, pageCount, data.generatedAt);
  }
  doc.setTextColor(0);
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function generateFlashPdf(data: FlashPdfData): void {
  const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });

  // Slide 1 — Title page
  renderTitlePage(doc, data);

  // Slide 2 — KPIs
  if (data.sections.kpis) {
    renderKpisPage(doc, data);
  }

  // Slide 3 — Rentabilité par canal
  if (data.sections.profitability) {
    renderProfitabilitySlide(doc, data);
    // Charts: pie charts after rentabilité
    if (data.chartImages?.revenuePie || data.chartImages?.commissionPie) {
      renderPieChartsPage(doc, data);
    }
  }

  // Slide 5 — Ventilation
  if (data.sections.ventilation) {
    renderVentilationSlide(doc, data);
    // Charts: ventilation bar chart after table
    if (data.chartImages?.ventilation) {
      renderVentilationChartPage(doc, data);
    }
  }

  // Slide 5 — TVA
  if (data.sections.tva) {
    renderTvaSlide(doc, data);
  }

  // Slide 6 — Geo
  if (data.sections.geo) {
    renderGeoSlide(doc, data);
  }

  // Slide 7 — Anomalies
  if (data.sections.anomalies) {
    renderAnomaliesSlide(doc, data);
  }

  // Apply footers on all pages except title
  renderAllFooters(doc, data);

  doc.save(buildFilename(data.dateRange));
}
