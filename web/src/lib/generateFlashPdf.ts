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
import type { Summary, Anomaly } from "./types";

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface FlashPdfSections {
  synthese: boolean;
  ventilation: boolean;
  tva: boolean;
  geo: boolean;
  kpis: boolean;
  anomalies: boolean;
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
  shopify: [90, 142, 59],
  manomano: [194, 115, 36],
  decathlon: [43, 108, 176],
  leroy_merlin: [107, 70, 193],
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
  // Logo placeholder
  doc.setFillColor(...C.borderLight);
  doc.rect(L.margin, L.margin, 12, 12, "F");
  doc.setFont("helvetica", "normal");
  doc.setFontSize(6);
  doc.setTextColor(...C.secondary);
  doc.text("LOGO", L.margin + 6, L.margin + 7, { align: "center" });

  // Title
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(...C.secondary);
  doc.text(`Flash E-Commerce \u00B7 ${periodLabel(data.dateRange)}`, L.margin + 15, L.margin + 5);

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

  // Logo placeholder
  doc.setFillColor(...C.borderLight);
  doc.rect(cx - 10, 130, 20, 20, "F");
  doc.setFont("helvetica", "normal");
  doc.setFontSize(6);
  doc.setTextColor(...C.secondary);
  doc.text("LOGO", cx, 141, { align: "center" });
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
  const allChannels = ["total", ...channels];
  const nCards = allChannels.length;
  const GAP_BETWEEN_CARDS = 5;
  const MAX_CARDS_PER_ROW = 4;
  const CARD_PADDING = 4;
  const contentWidth = 267; // 297 - 2 * 15mm margins
  const multiRow = nCards > MAX_CARDS_PER_ROW;
  const valueFontSize = multiRow ? 14 : nCards === 4 ? 16 : 24;
  const labelFontSize = multiRow ? 7 : 8;

  // KPI definitions
  const totalTx = channels.reduce((s, c) => s + (summary.transactions_par_canal[c] ?? 0), 0);
  const totalCa = channels.reduce((s, c) => s + (isHt ? summary.ca_par_canal[c]?.ht ?? 0 : summary.ca_par_canal[c]?.ttc ?? 0), 0);
  const totalNet = channels.reduce((s, c) => s + (summary.net_vendeur_par_canal[c] ?? 0), 0);
  const totalRemb = totalTx > 0
    ? channels.reduce((s, c) => s + (summary.remboursements_par_canal[c]?.count ?? 0), 0) / totalTx * 100
    : 0;
  const totalAnomalyRate = totalTx > 0 ? data.anomalies.length / totalTx * 100 : 0;

  function getKpis(channel: string): { value: string; label: string }[] {
    if (channel === "total") {
      return [
        { value: fmt(totalCa), label: `CA Total ${isHt ? "HT" : "TTC"}` },
        { value: fmt(totalNet), label: "Net Vendeur" },
        { value: String(totalTx), label: "Nb Transactions" },
        { value: fmtPct(Math.round(totalRemb * 10) / 10), label: "Tx Remboursement" },
        { value: fmtPct(Math.round(totalAnomalyRate * 10) / 10), label: "Tx Anomalies" },
      ];
    }
    const ca = isHt ? summary.ca_par_canal[channel]?.ht ?? 0 : summary.ca_par_canal[channel]?.ttc ?? 0;
    const net = summary.net_vendeur_par_canal[channel] ?? 0;
    const tx = summary.transactions_par_canal[channel] ?? 0;
    const remb = summary.taux_remboursement_par_canal[channel] ?? 0;
    const chAnomalies = data.anomalies.filter((a) => a.canal === channel).length;
    const anomRate = tx > 0 ? chAnomalies / tx * 100 : 0;
    return [
      { value: fmt(ca), label: `CA Total ${isHt ? "HT" : "TTC"}` },
      { value: fmt(net), label: "Net Vendeur" },
      { value: String(tx), label: "Nb Transactions" },
      { value: fmtPct(Math.round(remb * 10) / 10), label: "Tx Remboursement" },
      { value: fmtPct(Math.round(anomRate * 10) / 10), label: "Tx Anomalies" },
    ];
  }

  const kpiBlockH = 26;
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
      doc.setFontSize(10);
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
// Table slide helpers
// ---------------------------------------------------------------------------

function renderSyntheseSlide(doc: jsPDF, data: FlashPdfData): void {
  doc.addPage();
  renderPageHeader(doc, data);
  const y = renderSlideTitle(doc, "Synth\u00e8se Financi\u00e8re", "R\u00e9capitulatif par canal de vente");

  const { summary, channels, mode } = data;
  const isHt = mode === "ht";

  const head = isHt
    ? [["Canal", "CA HT", "Remb. HT", "Commissions HT", "Taux comm.", "Net vendeur"]]
    : [["Canal", "CA TTC", "Remb. TTC", "Commissions TTC", "Taux comm.", "Net vendeur"]];

  const body = channels.map((c) => {
    const ca = isHt ? summary.ca_par_canal[c].ht : summary.ca_par_canal[c].ttc;
    const remb = isHt ? summary.remboursements_par_canal[c].ht : summary.remboursements_par_canal[c].ttc;
    const comm = isHt ? summary.commissions_par_canal[c].ht : summary.commissions_par_canal[c].ttc;
    const rate = ca > 0 ? fmtPct(Math.round(comm / ca * 1000) / 10) : fmtPct(0);
    const net = fmt(summary.net_vendeur_par_canal[c]);
    return [channelLabel(c), fmt(ca), fmt(remb), fmt(comm), rate, net];
  });

  const totCa = channels.reduce((s, c) => s + (isHt ? summary.ca_par_canal[c].ht : summary.ca_par_canal[c].ttc), 0);
  const totRemb = channels.reduce((s, c) => s + (isHt ? summary.remboursements_par_canal[c].ht : summary.remboursements_par_canal[c].ttc), 0);
  const totComm = channels.reduce((s, c) => s + (isHt ? summary.commissions_par_canal[c].ht : summary.commissions_par_canal[c].ttc), 0);
  const totRate = totCa > 0 ? fmtPct(Math.round(totComm / totCa * 1000) / 10) : fmtPct(0);
  const totNet = fmt(channels.reduce((s, c) => s + summary.net_vendeur_par_canal[c], 0));
  body.push(["TOTAL", fmt(totCa), fmt(totRemb), fmt(totComm), totRate, totNet]);

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
      0: { cellWidth: 50 },
      1: { halign: "right" },
      2: { halign: "right" },
      3: { halign: "right" },
      4: { halign: "right" },
      5: { halign: "right" },
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
    for (const [pays, rows] of Object.entries(tvaPays)) {
      for (let i = 0; i < rows.length; i++) {
        body.push([i === 0 ? pays : "", fmtPct(rows[i].taux), fmt(rows[i].montant)]);
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

  // Count by severity
  const errCount = anomalies.filter((a) => a.severity === "error").length;
  const warnCount = anomalies.filter((a) => a.severity === "warning").length;
  const infoCount = anomalies.filter((a) => a.severity === "info").length;

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

  // Slide 3 — Synthese
  if (data.sections.synthese) {
    renderSyntheseSlide(doc, data);
  }

  // Slide 4 — Ventilation
  if (data.sections.ventilation) {
    renderVentilationSlide(doc, data);
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
