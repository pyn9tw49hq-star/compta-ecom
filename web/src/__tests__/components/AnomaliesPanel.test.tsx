import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import AnomaliesPanel from "@/components/AnomaliesPanel";
import type { Anomaly } from "@/lib/types";

// --- Mock data: 10 anomalies, mix of severities, channels, types ---

const MOCK_ANOMALIES: Anomaly[] = [
  {
    type: "tva_mismatch",
    severity: "warning",
    canal: "shopify",
    reference: "#1001",
    detail: "TVA 20% attendue, 0% trouvée",
    expected_value: "20",
    actual_value: "0",
  },
  {
    type: "orphan_sale",
    severity: "error",
    canal: "manomano",
    reference: "#2001",
    detail: "Vente sans règlement correspondant",
  },
  {
    type: "amount_mismatch",
    severity: "warning",
    canal: "decathlon",
    reference: "#3001",
    detail: "Écart de 0.01€ sur le montant",
  },
  {
    type: "balance_error",
    severity: "error",
    canal: "shopify",
    reference: "#1002",
    detail: "Débit 100.00 ≠ Crédit 99.99",
  },
  {
    type: "missing_payout",
    severity: "warning",
    canal: "leroy_merlin",
    reference: "#4001",
    detail: "Aucun reversement trouvé pour ce mois",
  },
  {
    type: "orphan_settlement",
    severity: "info",
    canal: "shopify",
    reference: "#1003",
    detail: "Règlement sans vente associée",
  },
  {
    type: "orphan_refund",
    severity: "error",
    canal: "manomano",
    reference: "#2002",
    detail: "Remboursement sans commande d'origine",
  },
  {
    type: "lettrage_511_unbalanced",
    severity: "info",
    canal: "shopify",
    reference: "#1004",
    detail: "Compte 511 non soldé après lettrage",
  },
  {
    type: "payout_detail_mismatch",
    severity: "warning",
    canal: "decathlon",
    reference: "#3002",
    detail: "Détail versement incohérent",
  },
  {
    type: "mixed_psp_payout",
    severity: "info",
    canal: "leroy_merlin",
    reference: "#4002",
    detail: "Versement avec plusieurs PSP",
  },
];

describe("AnomaliesPanel", () => {
  describe("rendering", () => {
    it("displays severity badges with correct colors", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      // 3 errors → red badge
      const errorBadges = screen
        .getAllByText("Erreur")
        .filter((el) => el.classList.contains("bg-red-100"));
      expect(errorBadges.length).toBe(3);

      // 4 warnings → orange badge
      const warningBadges = screen
        .getAllByText("Avertissement")
        .filter((el) => el.classList.contains("bg-orange-100"));
      expect(warningBadges.length).toBe(4);

      // 3 infos → blue badge
      const infoBadges = screen
        .getAllByText("Info")
        .filter((el) => el.classList.contains("bg-blue-100"));
      expect(infoBadges.length).toBe(3);
    });

    it("displays all 5 fields for each anomaly (severity, type, canal, reference, detail)", () => {
      const flatAnomaly: Anomaly = {
        type: "amount_mismatch",
        severity: "warning",
        canal: "shopify",
        reference: "#5001",
        detail: "Écart de 0.02€",
        expected_value: null,
        actual_value: null,
      };
      render(<AnomaliesPanel anomalies={[flatAnomaly]} />);

      // Severity badge
      expect(screen.getByText("Avertissement")).toBeInTheDocument();
      // Type label (French)
      expect(screen.getByText("Écart de montant")).toBeInTheDocument();
      // Canal badge
      expect(screen.getByText("Shopify")).toBeInTheDocument();
      // Reference
      expect(screen.getByText("#5001")).toBeInTheDocument();
      // Detail
      expect(screen.getByText("Écart de 0.02€")).toBeInTheDocument();
    });

    it("displays severity counters in header", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      expect(screen.getByText("3 erreurs")).toBeInTheDocument();
      expect(screen.getByText("4 avertissements")).toBeInTheDocument();
      expect(screen.getByText("3 infos")).toBeInTheDocument();
    });

    it("uses French labels for anomaly types via ANOMALY_TYPE_LABELS", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      // Labels appear in both filter checkboxes and cards, so use getAllByText
      expect(screen.getAllByText("Vente sans encaissement").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Écart de montant").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Déséquilibre débit/crédit").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Versement en attente").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Encaissement sans commande").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Remboursement sans commande").length).toBeGreaterThanOrEqual(1);
    });

    it("displays French label for direct_payment type in grouped summary", () => {
      const anomaly: Anomaly = {
        type: "direct_payment",
        severity: "info",
        canal: "shopify",
        reference: "#DP01",
        detail: "Paiement Klarna détecté",
        expected_value: null,
        actual_value: null,
      };
      render(<AnomaliesPanel anomalies={[anomaly]} />);

      // direct_payment is grouped — summary text contains "paiement direct"
      expect(screen.getByText(/paiement direct/)).toBeInTheDocument();
    });

    it("falls back to raw type value for unknown types", () => {
      const anomaly: Anomaly = {
        type: "some_unknown_type",
        severity: "info",
        canal: "shopify",
        reference: "#9999",
        detail: "Unknown type detail",
      };
      render(<AnomaliesPanel anomalies={[anomaly]} />);

      expect(screen.getByText("some_unknown_type")).toBeInTheDocument();
    });

    it("uses singular form for single count", () => {
      const singleError: Anomaly[] = [
        {
          type: "balance_error",
          severity: "error",
          canal: "shopify",
          reference: "#1",
          detail: "Test",
        },
      ];
      render(<AnomaliesPanel anomalies={singleError} />);

      expect(screen.getByText("1 erreur")).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("shows positive message when no anomalies", () => {
      render(<AnomaliesPanel anomalies={[]} />);

      expect(
        screen.getByText("Aucune anomalie détectée"),
      ).toBeInTheDocument();
    });

    it("has role=status on empty message", () => {
      render(<AnomaliesPanel anomalies={[]} />);

      expect(screen.getByRole("status")).toHaveTextContent(
        "Aucune anomalie détectée",
      );
    });

    it("does not show filters or counters when empty", () => {
      render(<AnomaliesPanel anomalies={[]} />);

      expect(screen.queryByText("Canal :")).not.toBeInTheDocument();
      expect(screen.queryByText("Type :")).not.toBeInTheDocument();
      expect(screen.queryByText("Sévérité :")).not.toBeInTheDocument();
      expect(screen.queryByText(/erreur/)).not.toBeInTheDocument();
    });
  });

  describe("default sort", () => {
    it("displays errors first", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      // Get all severity badges in order
      const allBadges = screen.getAllByText(/^(Erreur|Avertissement|Info)$/);
      // Filter to only the flat card badges (not counter badges, not grouped <details>)
      // First flat card badge should be "Erreur"
      const cardBadges = allBadges.filter(
        (el) => el.closest("[class*='border-l-4']") !== null && el.closest("details") === null,
      );
      expect(cardBadges[0]).toHaveTextContent("Erreur");
    });

    it("displays info after warning", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      const cardBadges = screen
        .getAllByText(/^(Erreur|Avertissement|Info)$/)
        .filter((el) => el.closest("[class*='border-l-4']") !== null);

      // Find last warning and first info
      const lastWarningIdx = cardBadges.reduce(
        (acc, el, idx) =>
          el.textContent === "Avertissement" ? idx : acc,
        -1,
      );
      const firstInfoIdx = cardBadges.findIndex(
        (el) => el.textContent === "Info",
      );

      expect(lastWarningIdx).toBeLessThan(firstInfoIdx);
    });
  });

  describe("filtering", () => {
    it("filters by canal checkbox", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      const shopifyCheckbox = screen.getByRole("checkbox", {
        name: /Shopify/,
      });
      fireEvent.click(shopifyCheckbox);

      // 4 shopify anomalies in mock data
      const cards = document.querySelectorAll("[class*='border-l-4']");
      expect(cards).toHaveLength(4);
    });

    it("filters by severity checkbox", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      const errorCheckbox = screen.getByRole("checkbox", { name: /Erreur/ });
      fireEvent.click(errorCheckbox);

      // 3 errors in mock data
      const cards = document.querySelectorAll("[class*='border-l-4']");
      expect(cards).toHaveLength(3);
    });

    it("filters by type checkbox", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      const tvaCheckbox = screen.getByRole("checkbox", {
        name: /Taux de TVA incohérent/,
      });
      fireEvent.click(tvaCheckbox);

      // 1 tva_mismatch in mock data
      const cards = document.querySelectorAll("[class*='border-l-4']");
      expect(cards).toHaveLength(1);
    });

    it("combines canal + severity filters", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      // Filter canal=shopify + severity=error
      const shopifyCheckbox = screen.getByRole("checkbox", {
        name: /Shopify/,
      });
      fireEvent.click(shopifyCheckbox);

      const errorCheckbox = screen.getByRole("checkbox", { name: /Erreur/ });
      fireEvent.click(errorCheckbox);

      // shopify errors: #1002 (balance_error) = 1
      const cards = document.querySelectorAll("[class*='border-l-4']");
      expect(cards).toHaveLength(1);
    });

    it("updates counter after filter", () => {
      render(<AnomaliesPanel anomalies={MOCK_ANOMALIES} />);

      const errorCheckbox = screen.getByRole("checkbox", { name: /Erreur/ });
      fireEvent.click(errorCheckbox);

      // Should show "3 erreurs" and "(sur 10 total)"
      expect(screen.getByText("3 erreurs")).toBeInTheDocument();
      expect(screen.getByText("(sur 10 total)")).toBeInTheDocument();

      // Warning and info counters should not appear (they are 0 after filter)
      expect(screen.queryByText(/avertissement/)).not.toBeInTheDocument();
    });
  });

  describe("tva_mismatch grouping", () => {
    it("groups tva_mismatch anomalies by rate discrepancy in a <details>", () => {
      const tvaMismatchAnomalies: Anomaly[] = [
        {
          type: "tva_mismatch",
          severity: "warning",
          canal: "shopify",
          reference: "#A01",
          detail: "TVA 20% attendue, 0% trouvée",
          expected_value: "20",
          actual_value: "0",
        },
        {
          type: "tva_mismatch",
          severity: "warning",
          canal: "shopify",
          reference: "#A02",
          detail: "TVA 20% attendue, 0% trouvée",
          expected_value: "20",
          actual_value: "0",
        },
        {
          type: "tva_mismatch",
          severity: "warning",
          canal: "shopify",
          reference: "#A03",
          detail: "TVA 20% attendue, 10% trouvée",
          expected_value: "20",
          actual_value: "10",
        },
      ];
      render(<AnomaliesPanel anomalies={tvaMismatchAnomalies} />);

      // Two groups: "0% au lieu de 20%" (2 items) and "10% au lieu de 20%" (1 item)
      const details = document.querySelectorAll("details");
      expect(details).toHaveLength(2);

      // First group summary: 2 factures
      expect(screen.getByText(/2 factures avec taux de TVA incohérent — 0% au lieu de 20%/)).toBeInTheDocument();
      // Second group summary: 1 facture (singular)
      expect(screen.getByText(/1 facture avec taux de TVA incohérent — 10% au lieu de 20%/)).toBeInTheDocument();

      // Individual references visible inside details
      expect(screen.getByText("#A01")).toBeInTheDocument();
      expect(screen.getByText("#A02")).toBeInTheDocument();
      expect(screen.getByText("#A03")).toBeInTheDocument();
    });

    it("uses severity badge and channel badge in tva_mismatch group summary", () => {
      const anomalies: Anomaly[] = [
        {
          type: "tva_mismatch",
          severity: "warning",
          canal: "decathlon",
          reference: "#D01",
          detail: "TVA incohérente",
          expected_value: "20",
          actual_value: "0",
        },
      ];
      render(<AnomaliesPanel anomalies={anomalies} />);

      // Severity badge inside the details summary
      const details = document.querySelector("details");
      expect(details).not.toBeNull();
      expect(details!.querySelector("[class*='bg-orange-100']")).not.toBeNull();

      // Channel badge
      expect(screen.getByText("Décathlon")).toBeInTheDocument();
    });

    it("handles missing expected_value/actual_value with fallback '?'", () => {
      const anomalies: Anomaly[] = [
        {
          type: "tva_mismatch",
          severity: "warning",
          canal: "shopify",
          reference: "#X01",
          detail: "TVA incohérente",
          expected_value: null,
          actual_value: null,
        },
      ];
      render(<AnomaliesPanel anomalies={anomalies} />);

      expect(screen.getByText(/\?% au lieu de \?%/)).toBeInTheDocument();
    });
  });

  describe("accessibility", () => {
    it("has no axe violations with anomalies", async () => {
      const { container } = render(
        <AnomaliesPanel anomalies={MOCK_ANOMALIES} />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it("has no axe violations when empty", async () => {
      const { container } = render(<AnomaliesPanel anomalies={[]} />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});
