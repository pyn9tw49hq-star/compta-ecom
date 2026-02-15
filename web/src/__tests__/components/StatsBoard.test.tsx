import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { axe } from "vitest-axe";
import StatsBoard from "@/components/StatsBoard";
import type { Summary, Entry, Anomaly } from "@/lib/types";

const htTtcProps = { htTtcMode: "ttc" as const, onHtTtcModeChange: vi.fn() };

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
  ca_par_canal: {
    shopify: { ht: 37500.0, ttc: 45000.0 },
    manomano: { ht: 10000.0, ttc: 12000.0 },
    decathlon: { ht: 3750.0, ttc: 4500.0 },
  },
  remboursements_par_canal: {
    shopify: { count: 15, ht: 1000.0, ttc: 1200.0 },
    manomano: { count: 5, ht: 666.67, ttc: 800.0 },
    decathlon: { count: 8, ht: 583.33, ttc: 700.0 },
  },
  taux_remboursement_par_canal: {
    shopify: 2.7,
    manomano: 6.7,
    decathlon: 15.0,
  },
  commissions_par_canal: {
    shopify: { ht: 2625.0, ttc: 3150.0 },
    manomano: { ht: 1500.0, ttc: 1800.0 },
    decathlon: { ht: 375.0, ttc: 450.0 },
  },
  net_vendeur_par_canal: {
    shopify: 40650.0,
    manomano: 9400.0,
    decathlon: 3350.0,
  },
  tva_collectee_par_canal: {
    shopify: 7500.0,
    manomano: 2000.0,
    decathlon: 750.0,
  },
  ventilation_ca_par_canal: {
    shopify: { produits_ht: 35000.0, port_ht: 2500.0, total_ht: 37500.0 },
    manomano: { produits_ht: 9000.0, port_ht: 1000.0, total_ht: 10000.0 },
    decathlon: { produits_ht: 3500.0, port_ht: 250.0, total_ht: 3750.0 },
  },
  repartition_geo_globale: {
    France: { count: 900, ca_ttc: 40000.0, ca_ht: 33333.33 },
    Belgique: { count: 200, ca_ttc: 12000.0, ca_ht: 10000.0 },
  },
  repartition_geo_par_canal: {
    manomano: {
      France: { count: 100, ca_ttc: 5000.0, ca_ht: 4166.67 },
      Belgique: { count: 50, ca_ttc: 4000.0, ca_ht: 3333.33 },
    },
    shopify: {
      France: { count: 800, ca_ttc: 35000.0, ca_ht: 29166.67 },
      Belgique: { count: 150, ca_ttc: 8000.0, ca_ht: 6666.67 },
    },
  },
  tva_par_pays_par_canal: {
    shopify: {
      France: [{ taux: 20, montant: 5833.33 }],
      Belgique: [{ taux: 21, montant: 1400.0 }],
    },
    manomano: {
      France: [{ taux: 20, montant: 833.33 }],
      Belgique: [{ taux: 21, montant: 700.0 }],
    },
    decathlon: {
      France: [{ taux: 20, montant: 750.0 }],
    },
  },
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
          {...htTtcProps}
        />,
      );

      expect(screen.getAllByText("Shopify").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("ManoMano").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Décathlon").length).toBeGreaterThanOrEqual(1);
    });

    it("displays the Total row with font-semibold", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
          {...htTtcProps}
        />,
      );

      const totalCells = screen.getAllByText("Total");
      expect(totalCells[0]).toHaveClass("font-semibold");
    });

    it("formats counts with French thousands separator (UX-5)", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
          {...htTtcProps}
        />,
      );

      // 1250 → "1 250" (with non-breaking space); also matches "51 250,00" in financial table
      expect(screen.getAllByText(/1\s*250/).length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Écritures par type (AC1)", () => {
    it("displays total entry count", () => {
      render(
        <StatsBoard
          summary={MOCK_SUMMARY}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
          {...htTtcProps}
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
          {...htTtcProps}
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
          {...htTtcProps}
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
          {...htTtcProps}
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
          {...htTtcProps}
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
          {...htTtcProps}
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
          {...htTtcProps}
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
          {...htTtcProps}
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
          {...htTtcProps}
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
          {...htTtcProps}
        />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  // ======================================================
  // KPI sections (Story 8.1)
  // ======================================================

  describe("Synthèse financière par canal (AC15-19)", () => {
    it("displays h2 heading 'Synthèse financière par canal'", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      expect(
        screen.getByRole("heading", { name: "Synthèse financière par canal", level: 2 }),
      ).toBeInTheDocument();
    });

    it("displays consolidated table column headings (AC16)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      expect(screen.getAllByText("CA TTC").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Remb. TTC")).toBeInTheDocument();
      expect(screen.getByText("Taux remb.")).toBeInTheDocument();
      expect(screen.getByText("Commissions TTC")).toBeInTheDocument();
      expect(screen.getByText("Net vendeur")).toBeInTheDocument();
    });

    it("displays formatted amounts per channel in the table (AC16, AC23)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      // Shopify CA TTC = 45000 → "45 000,00 €"
      expect(screen.getAllByText(/45\s*000,00\s*€/).length).toBeGreaterThanOrEqual(1);
      // ManoMano CA TTC = 12000 → "12 000,00 €"
      expect(screen.getAllByText(/12\s*000,00\s*€/).length).toBeGreaterThanOrEqual(1);
    });

    it("displays a Total row in the consolidated table (AC16)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      // Total CA TTC = 61500 → "61 500,00"
      expect(screen.getByText(/61\s*500,00/)).toBeInTheDocument();
      // Total Net = 53400 → "53 400,00"
      expect(screen.getByText(/53\s*400,00/)).toBeInTheDocument();
    });

    it("renders expansion detail with HT/TVA content (AC18)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      // Detail content is in the DOM (inside <details>)
      expect(screen.getAllByText(/CA HT/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/TVA collectée/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Commission HT/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Remboursement HT/).length).toBeGreaterThanOrEqual(1);
    });

    it("displays green badge for refund rate < 5% (AC19)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      // Shopify taux = 2.7% → green badge
      const badge = screen.getByText(/2,7\s*%/);
      expect(badge.closest("[class*='bg-green-']")).not.toBeNull();
    });

    it("displays orange badge for refund rate 5–10% (AC19)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      // ManoMano taux = 6.7% → orange badge
      const badge = screen.getByText(/6,7\s*%/);
      expect(badge.closest("[class*='bg-orange-']")).not.toBeNull();
    });

    it("displays red badge for refund rate > 10% (AC19)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      // Decathlon taux = 15.0% → red badge
      const badge = screen.getByText(/15,0\s*%/);
      expect(badge.closest("[class*='bg-red-']")).not.toBeNull();
    });

    it("highlights Net vendeur column with distinctive CSS (AC17)", () => {
      const { container } = render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      // Net vendeur cells have text-emerald-700 class
      const emeraldCells = container.querySelectorAll(".text-emerald-700");
      expect(emeraldCells.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Fiscalité & géographie (AC20-21)", () => {
    it("displays h2 headings for Fiscalité and Répartition géographique", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      expect(
        screen.getByRole("heading", { name: /Fiscalité/, level: 2 }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: /Répartition géographique/, level: 2 }),
      ).toBeInTheDocument();
    });

    it("displays TVA collectée par canal section (AC20)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      expect(
        screen.getByRole("heading", { name: "TVA collectée par canal", level: 3 }),
      ).toBeInTheDocument();
      // Shopify TVA = 7500 → "7 500,00"
      expect(screen.getAllByText(/7\s*500,00/).length).toBeGreaterThanOrEqual(1);
    });

    it("displays global geographic table (AC21)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      expect(
        screen.getByRole("heading", { name: "Répartition géographique", level: 2 }),
      ).toBeInTheDocument();
      // France and Belgique in the global table
      expect(screen.getAllByText("France").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Belgique").length).toBeGreaterThanOrEqual(1);
    });

    it("displays per-channel geographic detail (AC21)", () => {
      render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      // Per-canal geo sections exist as collapsible <details>
      // France CA TTC in shopify geo = 35000 → "35 000,00"
      expect(screen.getAllByText(/35\s*000,00/).length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("Existing sections unchanged (AC25)", () => {
    it("keeps the 4 original sections in first position", () => {
      const { container } = render(
        <StatsBoard summary={MOCK_SUMMARY} entries={MOCK_ENTRIES} anomalies={MOCK_ANOMALIES} {...htTtcProps} />,
      );
      const sections = container.querySelectorAll("section");
      // First 4 sections: Équilibre, Transactions, Écritures, Anomalies
      expect(within(sections[0]).getByRole("heading")).toHaveTextContent("Équilibre comptable");
      expect(within(sections[1]).getByRole("heading")).toHaveTextContent("Transactions par canal");
      expect(within(sections[2]).getByRole("heading")).toHaveTextContent("Écritures générées");
      expect(within(sections[3]).getByRole("heading")).toHaveTextContent("Anomalies");
    });
  });
});
