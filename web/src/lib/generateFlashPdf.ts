/**
 * Pure module for generating the "FLASH E-COMMERCE" PDF report.
 * No React dependency — operates on plain data.
 */
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import { getChannelMeta } from "./channels";
import type { Summary } from "./types";

export interface FlashPdfSections {
  synthese: boolean;
  ventilation: boolean;
  tva: boolean;
  geo: boolean;
}

export interface FlashPdfData {
  summary: Summary;
  dateRange: { from: Date; to: Date };
  mode: "ht" | "ttc";
  countryNames: Record<string, string>;
  channels: string[];
  sections: FlashPdfSections;
  generatedAt: Date;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Normalize narrow no-break spaces (U+202F) and no-break spaces (U+00A0)
 * to regular spaces — jsPDF Helvetica (WinAnsiEncoding) can't render U+202F.
 */
function normSpace(s: string): string {
  return s.replace(/[\u202F\u00A0]/g, " ");
}

/** French number format: "12 345,67 €" */
function fmt(n: number): string {
  return normSpace(
    new Intl.NumberFormat("fr-FR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n) + " \u20AC"
  );
}

/** French percent format: "12,5 %" */
function fmtPct(n: number): string {
  return normSpace(
    new Intl.NumberFormat("fr-FR", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(n) + " %"
  );
}

/** Format a Date to "DD/MM/YYYY". */
function fmtDate(d: Date): string {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

/** Build download filename. */
function buildFilename(dateRange: { from: Date; to: Date }): string {
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return `FLASH-ECOMMERCE_${iso(dateRange.from)}_${iso(dateRange.to)}.pdf`;
}

/** Get display label for a channel key. */
function channelLabel(key: string): string {
  return getChannelMeta(key).label;
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const PAGE_WIDTH = 210; // A4 mm
const MARGIN = 14;

const HEAD_STYLE = {
  fillColor: [41, 50, 65] as [number, number, number],
  textColor: 255,
  fontStyle: "bold" as const,
  font: "helvetica",
};

const BODY_STYLE = {
  font: "helvetica",
  fontStyle: "normal" as const,
};

const TOTAL_STYLE = {
  font: "helvetica",
  fontStyle: "bold" as const,
  fillColor: [235, 237, 240] as [number, number, number],
};

// ---------------------------------------------------------------------------
// Section renderers
// ---------------------------------------------------------------------------

function renderHeader(doc: jsPDF, data: FlashPdfData, y: number): number {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("FLASH E-COMMERCE", PAGE_WIDTH / 2, y, { align: "center" });
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

  const modeStr = `Mode : ${data.mode === "ttc" ? "TTC" : "HT"}`;
  doc.text(modeStr, PAGE_WIDTH / 2, y, { align: "center" });
  y += 5;

  doc.setTextColor(150);
  doc.setFontSize(8);
  doc.text(`G\u00e9n\u00e9r\u00e9 le ${fmtDate(data.generatedAt)}`, PAGE_WIDTH / 2, y, { align: "center" });
  y += 2;

  // Separator line
  doc.setDrawColor(200);
  doc.setLineWidth(0.3);
  doc.line(MARGIN, y, PAGE_WIDTH - MARGIN, y);
  y += 6;

  doc.setTextColor(0);
  return y;
}

function renderSectionTitle(doc: jsPDF, title: string, y: number): number {
  // Check if we need a page break (title + minimal table space)
  if (y > 260) {
    doc.addPage();
    y = MARGIN + 5;
  }
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text(title, MARGIN, y);
  y += 6;
  return y;
}

function renderSyntheseTable(doc: jsPDF, data: FlashPdfData, y: number): number {
  y = renderSectionTitle(doc, "Synth\u00e8se financi\u00e8re par canal", y);

  const { summary, channels, mode } = data;
  const isHt = mode === "ht";

  const head = isHt
    ? [["Canal", "CA HT", "Remb. HT", "Commissions HT", "Taux comm."]]
    : [["Canal", "CA TTC", "Remb. TTC", "Commissions TTC", "Net vendeur"]];

  const body = channels.map((c) => {
    const ca = isHt ? summary.ca_par_canal[c].ht : summary.ca_par_canal[c].ttc;
    const remb = isHt ? summary.remboursements_par_canal[c].ht : summary.remboursements_par_canal[c].ttc;
    const comm = isHt ? summary.commissions_par_canal[c].ht : summary.commissions_par_canal[c].ttc;
    const last = isHt
      ? fmtPct(summary.ca_par_canal[c].ht > 0 ? Math.round(summary.commissions_par_canal[c].ht / summary.ca_par_canal[c].ht * 1000) / 10 : 0)
      : fmt(summary.net_vendeur_par_canal[c]);
    return [channelLabel(c), fmt(ca), fmt(remb), fmt(comm), last];
  });

  // Totals
  const totCa = channels.reduce((s, c) => s + (isHt ? summary.ca_par_canal[c].ht : summary.ca_par_canal[c].ttc), 0);
  const totRemb = channels.reduce((s, c) => s + (isHt ? summary.remboursements_par_canal[c].ht : summary.remboursements_par_canal[c].ttc), 0);
  const totComm = channels.reduce((s, c) => s + (isHt ? summary.commissions_par_canal[c].ht : summary.commissions_par_canal[c].ttc), 0);
  const totLast = isHt
    ? fmtPct(totCa > 0 ? Math.round(totComm / totCa * 1000) / 10 : 0)
    : fmt(channels.reduce((s, c) => s + summary.net_vendeur_par_canal[c], 0));

  body.push(["TOTAL", fmt(totCa), fmt(totRemb), fmt(totComm), totLast]);

  autoTable(doc, {
    startY: y,
    margin: { left: MARGIN, right: MARGIN },
    head,
    body,
    headStyles: HEAD_STYLE,
    bodyStyles: BODY_STYLE,
    columnStyles: {
      0: { cellWidth: 40 },
      1: { halign: "right" },
      2: { halign: "right" },
      3: { halign: "right" },
      4: { halign: "right" },
    },
    didParseCell(hookData) {
      if (hookData.section === "body" && hookData.row.index === body.length - 1) {
        Object.assign(hookData.cell.styles, TOTAL_STYLE);
      }
    },
  });

  return (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;
}

function renderVentilationTable(doc: jsPDF, data: FlashPdfData, y: number): number {
  y = renderSectionTitle(doc, "Ventilation CA : Produits / Frais de port", y);

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
    margin: { left: MARGIN, right: MARGIN },
    head,
    body,
    headStyles: HEAD_STYLE,
    bodyStyles: BODY_STYLE,
    columnStyles: {
      0: { cellWidth: 40 },
      1: { halign: "right" },
      2: { halign: "right" },
      3: { halign: "right" },
    },
    didParseCell(hookData) {
      if (hookData.section === "body" && hookData.row.index === body.length - 1) {
        Object.assign(hookData.cell.styles, TOTAL_STYLE);
      }
    },
  });

  return (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 8;
}

function renderTvaTable(doc: jsPDF, data: FlashPdfData, y: number): number {
  y = renderSectionTitle(doc, "Fiscalit\u00e9 - TVA collect\u00e9e", y);

  const { summary, channels } = data;

  for (const canal of channels) {
    const tvaPays = summary.tva_par_pays_par_canal[canal];
    if (!tvaPays || Object.keys(tvaPays).length === 0) continue;

    // Sub-header for channel
    if (y > 265) {
      doc.addPage();
      y = MARGIN + 5;
    }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.text(channelLabel(canal), MARGIN, y);
    y += 4;

    const head = [["Pays", "Taux TVA", "Montant TVA"]];
    const body: string[][] = [];
    for (const [pays, rows] of Object.entries(tvaPays)) {
      for (let i = 0; i < rows.length; i++) {
        body.push([
          i === 0 ? pays : "",
          fmtPct(rows[i].taux),
          fmt(rows[i].montant),
        ]);
      }
    }

    // Total TVA for this channel
    const totalTva = summary.tva_collectee_par_canal[canal];
    body.push(["TOTAL", "", fmt(totalTva)]);

    autoTable(doc, {
      startY: y,
      margin: { left: MARGIN, right: MARGIN },
      head,
      body,
      headStyles: HEAD_STYLE,
      bodyStyles: BODY_STYLE,
      columnStyles: {
        0: { cellWidth: 60 },
        1: { halign: "right" },
        2: { halign: "right" },
      },
      didParseCell(hookData) {
        if (hookData.section === "body" && hookData.row.index === body.length - 1) {
          Object.assign(hookData.cell.styles, TOTAL_STYLE);
        }
      },
    });

    y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 6;
  }

  return y + 2;
}

function renderGeoTable(doc: jsPDF, data: FlashPdfData, y: number): number {
  y = renderSectionTitle(doc, "R\u00e9partition g\u00e9ographique", y);

  const { summary, channels } = data;

  // Global table
  const globalGeo = summary.repartition_geo_globale;
  const totalCaHt = Object.values(globalGeo).reduce((s, d) => s + d.ca_ht, 0);

  const head = [["Pays", "CA HT", "% du total"]];
  const body = Object.entries(globalGeo).map(([pays, d]) => [
    pays,
    fmt(d.ca_ht),
    fmtPct(totalCaHt > 0 ? Math.round(d.ca_ht / totalCaHt * 1000) / 10 : 0),
  ]);

  autoTable(doc, {
    startY: y,
    margin: { left: MARGIN, right: MARGIN },
    head,
    body,
    headStyles: HEAD_STYLE,
    bodyStyles: BODY_STYLE,
    columnStyles: {
      0: { cellWidth: 60 },
      1: { halign: "right" },
      2: { halign: "right" },
    },
  });

  y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 6;

  // Per-channel breakdown
  for (const canal of channels) {
    const countries = summary.repartition_geo_par_canal[canal];
    if (!countries || Object.keys(countries).length === 0) continue;

    if (y > 265) {
      doc.addPage();
      y = MARGIN + 5;
    }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.text(channelLabel(canal), MARGIN, y);
    y += 4;

    const cHead = [["Pays", "Transactions", "CA HT"]];
    const cBody = Object.entries(countries).map(([pays, d]) => [
      pays,
      String(d.count),
      fmt(d.ca_ht),
    ]);

    autoTable(doc, {
      startY: y,
      margin: { left: MARGIN, right: MARGIN },
      head: cHead,
      body: cBody,
      headStyles: HEAD_STYLE,
      bodyStyles: BODY_STYLE,
      columnStyles: {
        0: { cellWidth: 60 },
        1: { halign: "right" },
        2: { halign: "right" },
      },
    });

    y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 6;
  }

  return y;
}

function renderFooters(doc: jsPDF): void {
  const pageCount = doc.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(140);
    const footer = `MAPP E-Commerce - Flash E-Commerce    Page ${i}/${pageCount}`;
    doc.text(footer, PAGE_WIDTH / 2, 290, { align: "center" });
  }
  doc.setTextColor(0);
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function generateFlashPdf(data: FlashPdfData): void {
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

  let y = MARGIN + 5;
  y = renderHeader(doc, data, y);

  if (data.sections.synthese) {
    y = renderSyntheseTable(doc, data, y);
  }
  if (data.sections.ventilation) {
    y = renderVentilationTable(doc, data, y);
  }
  if (data.sections.tva) {
    y = renderTvaTable(doc, data, y);
  }
  if (data.sections.geo) {
    renderGeoTable(doc, data, y);
  }

  renderFooters(doc);

  doc.save(buildFilename(data.dateRange));
}
