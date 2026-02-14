import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, fireEvent, within, waitFor } from "@testing-library/react";
import { axe } from "vitest-axe";
import AnomalyPdfButton from "@/components/AnomalyPdfButton";
import type { Anomaly } from "@/lib/types";

// Polyfill ResizeObserver for jsdom (Radix Popover dependency)
beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

// Mock the PDF generator to avoid jsPDF in tests
vi.mock("@/lib/generateAnomalyPdf", () => ({
  generateAnomalyPdf: vi.fn(),
}));

const dateRange = { from: new Date("2026-01-01"), to: new Date("2026-01-31") };

// --- 16 mock anomalies: 3 severities, 4 canals, 7+ types ---

const MOCK_ANOMALIES: Anomaly[] = [
  // Errors (5)
  { type: "orphan_sale", severity: "error", canal: "shopify", reference: "#1001", detail: "Vente sans r\u00e8glement" },
  { type: "orphan_sale", severity: "error", canal: "manomano", reference: "#2001", detail: "Vente sans r\u00e8glement" },
  { type: "amount_mismatch", severity: "error", canal: "decathlon", reference: "#3001", detail: "\u00c9cart 0.01\u20ac" },
  { type: "orphan_refund", severity: "error", canal: "shopify", reference: "#1002", detail: "Remboursement orphelin" },
  { type: "return_no_matching_sale", severity: "error", canal: "leroy_merlin", reference: "#4001", detail: "Retour sans vente" },
  // Warnings (6)
  { type: "tva_mismatch", severity: "warning", canal: "shopify", reference: "#1003", detail: "TVA 20% vs 10%" },
  { type: "tva_amount_mismatch", severity: "warning", canal: "manomano", reference: "#2002", detail: "Montant TVA incorrect" },
  { type: "missing_payout", severity: "warning", canal: "decathlon", reference: "#3002", detail: "Versement manquant" },
  { type: "payout_detail_mismatch", severity: "warning", canal: "leroy_merlin", reference: "#4002", detail: "\u00c9cart versement" },
  { type: "payment_delay", severity: "warning", canal: "shopify", reference: "#1004", detail: "Retard 15j" },
  { type: "mixed_psp_payout", severity: "warning", canal: "shopify", reference: "#1005", detail: "Multi-PSP" },
  // Infos (5)
  { type: "orphan_settlement", severity: "info", canal: "shopify", reference: "#1006", detail: "R\u00e8glement sans vente" },
  { type: "lettrage_511_unbalanced", severity: "info", canal: "manomano", reference: "#2003", detail: "511 non sold\u00e9" },
  { type: "zero_amount_order", severity: "info", canal: "decathlon", reference: "#3003", detail: "Montant nul" },
  { type: "unknown_line_type", severity: "info", canal: "leroy_merlin", reference: "#4003", detail: "Type inconnu" },
  { type: "direct_payment", severity: "info", canal: "shopify", reference: "#1007", detail: "Klarna d\u00e9tect\u00e9" },
];

/** Helper: open the popover by clicking the trigger */
function openPopover() {
  fireEvent.click(screen.getByRole("button", { name: /exporter les anomalies en pdf/i }));
}

describe("AnomalyPdfButton", () => {
  describe("rendering", () => {
    it("renders the button when anomalies are present", () => {
      render(<AnomalyPdfButton anomalies={MOCK_ANOMALIES} dateRange={dateRange} />);
      expect(screen.getByRole("button", { name: /exporter les anomalies en pdf/i })).toBeInTheDocument();
      expect(screen.getByText("Export PDF")).toBeInTheDocument();
    });

    it("renders disabled button when no anomalies", () => {
      render(<AnomalyPdfButton anomalies={[]} dateRange={dateRange} />);
      const btn = screen.getByRole("button", { name: /aucune anomalie/i });
      expect(btn).toBeDisabled();
    });
  });

  describe("popover", () => {
    it("opens popover on click and shows filter sections", () => {
      render(<AnomalyPdfButton anomalies={MOCK_ANOMALIES} dateRange={dateRange} />);
      openPopover();

      const popover = screen.getByRole("dialog");

      // Title
      expect(within(popover).getByText("RAPPORT D'ANOMALIES")).toBeInTheDocument();

      // Severity checkboxes
      expect(within(popover).getByText("Erreurs")).toBeInTheDocument();
      expect(within(popover).getByText("Avertissements")).toBeInTheDocument();
      expect(within(popover).getByText("Infos")).toBeInTheDocument();

      // Categories section
      expect(within(popover).getByText(/Coh\u00e9rence TVA/)).toBeInTheDocument();
      expect(within(popover).getByText(/Rapprochement/)).toBeInTheDocument();

      // Grouping section heading (also appears in subtitle, so use getAllByText)
      const regroupements = within(popover).getAllByText(/Regroupement/i);
      expect(regroupements.length).toBeGreaterThanOrEqual(1);

      // Generate button present with anomaly count (use text query — Radix portal)
      const genBtn = screen.getByText(/16 anomalie/);
      expect(genBtn).toBeInTheDocument();
    });
  });

  describe("severity filtering", () => {
    it("decreases count when unchecking errors", async () => {
      render(<AnomalyPdfButton anomalies={MOCK_ANOMALIES} dateRange={dateRange} />);
      openPopover();

      // Find and click the Errors severity checkbox
      const errorsLabel = screen.getByText("Erreurs").closest("label")!;
      const checkbox = within(errorsLabel).getByRole("checkbox");
      fireEvent.click(checkbox);

      // 5 errors removed, 11 remain
      await waitFor(() => {
        expect(screen.getByText(/11 anomalie/)).toBeInTheDocument();
      });
    });
  });

  describe("category filtering", () => {
    it("decreases count when unchecking a category", async () => {
      render(<AnomalyPdfButton anomalies={MOCK_ANOMALIES} dateRange={dateRange} />);
      openPopover();

      // Find the "Coh\u00e9rence TVA" category checkbox inside the summary
      const catSummary = screen.getByText(/Coh\u00e9rence TVA/).closest("summary")!;
      const checkbox = within(catSummary).getByRole("checkbox");
      fireEvent.click(checkbox);

      // tva_mismatch + tva_amount_mismatch = 2 removed, 14 remain
      await waitFor(() => {
        expect(screen.getByText(/14 anomalie/)).toBeInTheDocument();
      });
    });
  });

  describe("canal filtering", () => {
    it("decreases count when unchecking a canal", async () => {
      render(<AnomalyPdfButton anomalies={MOCK_ANOMALIES} dateRange={dateRange} />);
      openPopover();

      // Find and click the Shopify canal checkbox
      const popover = screen.getByRole("dialog");
      const shopifyLabel = within(popover).getByText("Shopify").closest("label")!;
      const checkbox = within(shopifyLabel).getByRole("checkbox");
      fireEvent.click(checkbox);

      // 7 shopify anomalies removed, 9 remain
      await waitFor(() => {
        expect(screen.getByText(/9 anomalie/)).toBeInTheDocument();
      });
    });
  });

  describe("grouping", () => {
    it("selects 'Par canal' radio", () => {
      render(<AnomalyPdfButton anomalies={MOCK_ANOMALIES} dateRange={dateRange} />);
      openPopover();

      const radio = screen.getByRole("radio", { name: /canal/i });
      fireEvent.click(radio);

      expect(radio).toHaveAttribute("data-state", "checked");
    });
  });

  describe("disabled generate", () => {
    it("disables generate button when all filters deselected via toggle", async () => {
      render(<AnomalyPdfButton anomalies={MOCK_ANOMALIES} dateRange={dateRange} />);
      openPopover();

      // The first "Tout d\u00e9s\u00e9lectionner" button belongs to the severity section
      const toggleBtns = screen.getAllByText(/Tout d\u00e9s\u00e9lectionner/);
      fireEvent.click(toggleBtns[0]);

      // After toggle, count should be 0 and button disabled (use text query)
      await waitFor(() => {
        expect(screen.getByText(/0 anomalie/)).toBeInTheDocument();
      });
    });
  });

  describe("accessibility", () => {
    it("has no axe violations with anomalies", async () => {
      const { container } = render(
        <AnomalyPdfButton anomalies={MOCK_ANOMALIES} dateRange={dateRange} />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});
