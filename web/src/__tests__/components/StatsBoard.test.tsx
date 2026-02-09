import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { axe } from "vitest-axe";
import StatsBoard from "@/components/StatsBoard";
import type { Summary, Entry, Anomaly } from "@/lib/types";

// --- Mock data ---

const MOCK_SUMMARY: Summary = {
  transactions_par_canal: {
    shopify: 1250,
    manomano: 80,
    decathlon: 45,
  },
  ecritures_par_type: {
    sale: 200,
    settlement: 150,
    commission: 100,
    payout: 50,
  },
  totaux: { debit: 45000.0, credit: 45000.0 },
};

const MOCK_ENTRIES: Entry[] = [
  {
    date: "2024-01-15",
    journal: "VE",
    compte: "411000",
    libelle: "Vente Shopify #1001",
    debit: 100.0,
    credit: 0,
    piece: "#1001",
    lettrage: "L001",
    canal: "shopify",
    type_ecriture: "sale",
  },
  {
    date: "2024-01-15",
    journal: "VE",
    compte: "707000",
    libelle: "Vente Shopify #1001",
    debit: 0,
    credit: 83.33,
    piece: "#1001",
    lettrage: "L001",
    canal: "shopify",
    type_ecriture: "sale",
  },
  {
    date: "2024-01-15",
    journal: "RE",
    compte: "511000",
    libelle: "Règlement #1001",
    debit: 97.0,
    credit: 0,
    piece: "#1001",
    lettrage: "L001",
    canal: "shopify",
    type_ecriture: "settlement",
  },
];

const MOCK_ANOMALIES: Anomaly[] = [
  {
    type: "tva_mismatch",
    severity: "warning",
    canal: "shopify",
    reference: "#1001",
    detail: "TVA 20% attendue, 10% trouvée",
  },
  {
    type: "orphan_sale",
    severity: "error",
    canal: "manomano",
    reference: "#2001",
    detail: "Vente sans règlement",
  },
  {
    type: "orphan_settlement",
    severity: "info",
    canal: "shopify",
    reference: "#1003",
    detail: "Règlement orphelin",
  },
  {
    type: "balance_error",
    severity: "error",
    canal: "decathlon",
    reference: "#3001",
    detail: "Débit ≠ Crédit",
  },
];

describe("StatsBoard", () => {
  describe("Transactions par canal (AC1, AC2)", () => {
    it("displays a comparative table with channel labels", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      expect(screen.getByText("Shopify")).toBeInTheDocument();
      expect(screen.getByText("ManoMano")).toBeInTheDocument();
      expect(screen.getByText("Décathlon")).toBeInTheDocument();
    });

    it("displays the Total row with font-semibold", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      const totalCell = screen.getByText("Total");
      expect(totalCell).toHaveClass("font-semibold");
    });

    it("formats counts with French thousands separator (UX-5)", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      // 1250 → "1 250" (with non-breaking space)
      expect(screen.getByText(/1\s*250/)).toBeInTheDocument();
    });
  });

  describe("Écritures par type (AC1)", () => {
    it("displays total entry count", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      // entries.length = 3
      expect(screen.getByText("3")).toBeInTheDocument();
    });

    it("displays French labels for entry types", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      expect(screen.getByText("Vente")).toBeInTheDocument();
      expect(screen.getByText("Règlement")).toBeInTheDocument();
      expect(screen.getByText("Commission")).toBeInTheDocument();
      expect(screen.getByText("Reversement")).toBeInTheDocument();
    });
  });

  describe("Totaux débit/crédit (AC1)", () => {
    it("formats amounts in EUR with € suffix (UX-3)", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      // 45000.00 → "45 000,00 €"
      const debitText = screen.getByText(/Débit/);
      expect(debitText).toHaveTextContent(/45\s*000,00\s*€/);

      const creditText = screen.getByText(/Crédit/);
      expect(creditText).toHaveTextContent(/45\s*000,00\s*€/);
    });

    it("displays h3 heading 'Équilibre comptable' (UX-2)", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      const heading = screen.getByRole("heading", {
        name: "Équilibre comptable",
        level: 3,
      });
      expect(heading).toBeInTheDocument();
    });
  });

  describe("Indicateur d'équilibre (AC3)", () => {
    it("shows green 'Équilibré' when debit === credit", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      const indicator = screen.getByText("Équilibré");
      expect(indicator).toBeInTheDocument();
      expect(indicator.closest("div[class*='bg-green-50']")).not.toBeNull();
    });

    it("shows red 'Déséquilibré' with écart when debit !== credit", () => {
      const unbalanced: Summary = {
        ...MOCK_SUMMARY,
        totaux: { debit: 45000.0, credit: 44990.5 },
      };

      render(
        <StatsBoard
          summary={unbalanced}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      const indicator = screen.getByText("Déséquilibré");
      expect(indicator).toBeInTheDocument();
      expect(indicator.closest("div[class*='bg-red-50']")).not.toBeNull();

      // Écart displayed
      expect(screen.getByText(/Écart/)).toBeInTheDocument();
    });

    it("renders balance section before transactions in DOM (UX-1)", () => {
      const { container } = render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      const sections = container.querySelectorAll("section");
      const firstSection = sections[0];
      const firstHeading = within(firstSection).getByRole("heading");
      expect(firstHeading).toHaveTextContent("Équilibre comptable");
    });
  });

  describe("Anomalies par sévérité (AC1)", () => {
    it("displays severity counters with colored badges", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      // 2 errors, 1 warning, 1 info
      expect(screen.getByText(/2\s+Erreur/)).toBeInTheDocument();
      expect(screen.getByText(/1\s+Avertissement/)).toBeInTheDocument();
      expect(screen.getByText(/1\s+Info/)).toBeInTheDocument();
    });

    it("shows 'Aucune anomalie' when anomalies is empty", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={[]}
        />,
      );

      expect(screen.getByText("Aucune anomalie")).toBeInTheDocument();
    });
  });

  describe("accessibility", () => {
    it("has no axe violations", async () => {
      const { container } = render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});
