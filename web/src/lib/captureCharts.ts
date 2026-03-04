/**
 * Render charts as PNG images via Canvas 2D for PDF embedding.
 * No DOM dependency — draws programmatically from data.
 */
import type { ChartImages } from "./generateFlashPdf";

// ---------------------------------------------------------------------------
// Public interfaces
// ---------------------------------------------------------------------------

export interface PieChartData {
  label: string;
  value: number;
  color: string;
}

export interface BarChartData {
  label: string;
  segments: { value: number; color: string; label: string }[];
}

export interface RenderChartParams {
  revenuePie?: { data: PieChartData[]; total: number; centerLabel: string };
  commissionPie?: { data: PieChartData[]; total: number; centerLabel: string };
  ventilation?: { data: BarChartData[]; maxValue: number };
}

// ---------------------------------------------------------------------------
// Channel colors
// ---------------------------------------------------------------------------

const CHANNEL_COLORS: Record<string, string> = {
  shopify: "#16a34a",
  manomano: "#2563eb",
  decathlon: "#ea580c",
  leroy_merlin: "#9333ea",
};

export function getChannelColor(key: string): string {
  return CHANNEL_COLORS[key] ?? "#6B46C1";
}

// ---------------------------------------------------------------------------
// Formatting helpers (canvas-only — no Intl for simplicity)
// ---------------------------------------------------------------------------

function fmtNum(n: number): string {
  const parts = n.toFixed(2).split(".");
  const intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${intPart},${parts[1]} \u20AC`;
}

function fmtK(n: number): string {
  if (n >= 1000) return `${Math.round(n / 1000)}k`;
  return String(Math.round(n));
}

// ---------------------------------------------------------------------------
// Donut chart renderer
// ---------------------------------------------------------------------------

function renderDonut(
  data: PieChartData[],
  total: number,
  centerLabel: string,
  width: number,
  height: number,
): string {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;

  // White background
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  const cx = width / 2;
  const cy = height * 0.38;
  const outerR = Math.min(width, height) * 0.28;
  const innerR = outerR * 0.6;
  const padAngle = 0.02;

  // Filter out zero-value segments
  const nonZero = data.filter((d) => d.value > 0);
  if (nonZero.length === 0) return canvas.toDataURL("image/png");

  // Draw arcs
  let startAngle = -Math.PI / 2;
  for (const segment of nonZero) {
    const sliceAngle = (segment.value / total) * (2 * Math.PI);
    const endAngle = startAngle + sliceAngle;

    ctx.beginPath();
    ctx.arc(cx, cy, outerR, startAngle + padAngle / 2, endAngle - padAngle / 2);
    ctx.arc(cx, cy, innerR, endAngle - padAngle / 2, startAngle + padAngle / 2, true);
    ctx.closePath();
    ctx.fillStyle = segment.color;
    ctx.fill();

    startAngle = endAngle;
  }

  // Center text — total amount
  ctx.fillStyle = "#1B2A4A";
  ctx.font = "bold 28px Helvetica, Arial, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(fmtNum(total), cx, cy - 8);

  // Center text — label
  ctx.fillStyle = "#4A5568";
  ctx.font = "14px Helvetica, Arial, sans-serif";
  ctx.fillText(centerLabel, cx, cy + 16);

  // Legend below donut
  const legendY = height * 0.78;
  const legendItemW = width / Math.max(nonZero.length, 1);

  for (let i = 0; i < nonZero.length; i++) {
    const seg = nonZero[i];
    const x = legendItemW * i + legendItemW / 2;
    const pct = total > 0 ? ((seg.value / total) * 100).toFixed(1) : "0.0";

    // Color dot
    ctx.beginPath();
    ctx.arc(x - 30, legendY, 6, 0, 2 * Math.PI);
    ctx.fillStyle = seg.color;
    ctx.fill();

    // Label + percentage
    ctx.fillStyle = "#2D3748";
    ctx.font = "13px Helvetica, Arial, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(`${seg.label}  ${pct} %`, x - 20, legendY + 4);
  }

  return canvas.toDataURL("image/png");
}

// ---------------------------------------------------------------------------
// Horizontal stacked bar chart renderer
// ---------------------------------------------------------------------------

function renderBars(
  data: BarChartData[],
  maxValue: number,
  width: number,
  height: number,
): string {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d")!;

  // White background
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  if (data.length === 0 || maxValue <= 0) return canvas.toDataURL("image/png");

  // Scale factor: all sizes are designed for a 2400x1000 canvas
  const labelAreaW = 280;
  const rightPad = 80;
  const barAreaW = width - labelAreaW - rightPad;
  const barH = 100;
  const barGap = 60;
  const topPad = 60;
  const totalBarsH = data.length * barH + (data.length - 1) * barGap;
  const startY = topPad + Math.max(0, (height - topPad - 120 - totalBarsH) / 2);

  // Grid lines + axis labels
  ctx.strokeStyle = "#E2E8F0";
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 6]);
  const ticks = 5;
  for (let i = 0; i <= ticks; i++) {
    const x = labelAreaW + (barAreaW * i) / ticks;
    ctx.beginPath();
    ctx.moveTo(x, startY - 20);
    ctx.lineTo(x, startY + totalBarsH + 10);
    ctx.stroke();

    // Tick label
    ctx.fillStyle = "#A0AEC0";
    ctx.font = "22px Helvetica, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(fmtK((maxValue * i) / ticks), x, startY + totalBarsH + 40);
  }
  ctx.setLineDash([]);

  // Bars
  for (let i = 0; i < data.length; i++) {
    const item = data[i];
    const y = startY + i * (barH + barGap);

    // Channel label
    ctx.fillStyle = "#1B2A4A";
    ctx.font = "bold 28px Helvetica, Arial, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillText(item.label, labelAreaW - 20, y + barH / 2);

    // Draw stacked segments
    let xOffset = labelAreaW;
    for (const seg of item.segments) {
      const segW = (seg.value / maxValue) * barAreaW;
      if (segW > 0) {
        ctx.fillStyle = seg.color;
        // Rounded corners for first and last visible segments
        const radius = 8;
        ctx.beginPath();
        ctx.roundRect(xOffset, y, Math.max(segW, 1), barH, radius);
        ctx.fill();
        xOffset += segW;
      }
    }

    // Total amount label right of bar
    const totalValue = item.segments.reduce((s, seg) => s + seg.value, 0);
    ctx.font = "bold 24px Helvetica, Arial, sans-serif";
    ctx.textBaseline = "middle";
    const amountText = fmtNum(totalValue);
    const amountTextW = ctx.measureText(amountText).width;
    if (xOffset + 16 + amountTextW < width - rightPad) {
      // Fits right of bar
      ctx.fillStyle = "#1B2A4A";
      ctx.textAlign = "left";
      ctx.fillText(amountText, xOffset + 16, y + barH / 2);
    } else {
      // Overflow — place above bar end, dark text
      ctx.fillStyle = "#1B2A4A";
      ctx.textAlign = "right";
      ctx.textBaseline = "bottom";
      ctx.fillText(amountText, xOffset, y - 8);
    }
  }

  // Legend at bottom — generic pattern explanation (not channel-specific)
  const legendY = height - 40;
  const legendStartX = labelAreaW;

  // Dark square = Produits
  ctx.fillStyle = "#374151"; // neutral dark gray
  ctx.fillRect(legendStartX, legendY - 10, 20, 20);
  ctx.fillStyle = "#2D3748";
  ctx.font = "22px Helvetica, Arial, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText("Produits HT", legendStartX + 28, legendY + 6);

  // Light square = Frais de port
  const lx2 = legendStartX + 220;
  ctx.fillStyle = "#D1D5DB"; // neutral light gray
  ctx.fillRect(lx2, legendY - 10, 20, 20);
  ctx.fillStyle = "#2D3748";
  ctx.fillText("Frais de port HT", lx2 + 28, legendY + 6);

  return canvas.toDataURL("image/png");
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/**
 * Render chart images programmatically via Canvas 2D.
 * Returns base64 PNG strings ready for PDF embedding.
 */
export function renderChartImages(params: RenderChartParams): ChartImages {
  const result: ChartImages = {};

  if (params.revenuePie) {
    result.revenuePie = renderDonut(
      params.revenuePie.data,
      params.revenuePie.total,
      params.revenuePie.centerLabel,
      800,
      800,
    );
  }

  if (params.commissionPie) {
    result.commissionPie = renderDonut(
      params.commissionPie.data,
      params.commissionPie.total,
      params.commissionPie.centerLabel,
      800,
      800,
    );
  }

  if (params.ventilation) {
    result.ventilation = renderBars(
      params.ventilation.data,
      params.ventilation.maxValue,
      2400,
      1000,
    );
  }

  return result;
}
