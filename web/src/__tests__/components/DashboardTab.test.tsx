import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "vitest-axe";
import KpiCard from "@/components/dashboard/KpiCard";
import ChartCard from "@/components/dashboard/ChartCard";
import { DashboardTab } from "@/components/dashboard";
import { Coins } from "lucide-react";
import type { Summary, Anomaly } from "@/lib/types";

// --- Polyfill matchMedia for jsdom ---
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

// --- Mock next-themes ---
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light" }),
}));

// --- Mock Recharts ResponsiveContainer (renders children at fixed size) ---
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 800, height: 400 }}>{children}</div>
    ),
  };
});

// --- Mock data ---

const MOCK_SUMMARY: Summary = {
  transactions_par_canal: {
    shopify: 200,
    manomano: 100,
    decathlon: 42,
  },
  ecritures_par_type: {
    sale: 300,
    settlement: 200,
    commission: 150,
    payout: 50,
  },
  totaux: { debit: 40000.0, credit: 40000.0 },
  ca_par_canal: {
    shopify: { ht: 25000.0, ttc: 30000.0 },
    manomano: { ht: 8000.0, ttc: 9600.0 },
    decathlon: { ht: 3000.0, ttc: 3600.0 },
  },
  remboursements_par_canal: {
    shopify: { count: 10, ht: 800.0, ttc: 960.0 },
    manomano: { count: 5, ht: 500.0, ttc: 600.0 },
    decathlon: { count: 2, ht: 100.0, ttc: 120.0 },
  },
  taux_remboursement_par_canal: {
    shopify: 3.2,
    manomano: 6.3,
    decathlon: 3.3,
  },
  commissions_par_canal: {
    shopify: { ht: 1750.0, ttc: 2100.0 },
    manomano: { ht: 1200.0, ttc: 1440.0 },
    decathlon: { ht: 300.0, ttc: 360.0 },
  },
  net_vendeur_par_canal: {
    shopify: 27000.0,
    manomano: 7560.0,
    decathlon: 3120.0,
  },
  tva_collectee_par_canal: {
    shopify: 5000.0,
    manomano: 1600.0,
    decathlon: 600.0,
  },
  ventilation_ca_par_canal: {
    shopify: { produits_ht: 23000.0, port_ht: 2000.0, total_ht: 25000.0 },
    manomano: { produits_ht: 7200.0, port_ht: 800.0, total_ht: 8000.0 },
    decathlon: { produits_ht: 2800.0, port_ht: 200.0, total_ht: 3000.0 },
  },
  repartition_geo_globale: {
    France: { count: 250, ca_ttc: 35000.0, ca_ht: 29166.67 },
    Belgique: { count: 92, ca_ttc: 8200.0, ca_ht: 6833.33 },
  },
  repartition_geo_par_canal: {
    shopify: { France: { count: 180, ca_ttc: 25000.0, ca_ht: 20833.33 } },
    manomano: { Belgique: { count: 70, ca_ttc: 6000.0, ca_ht: 5000.0 } },
  },
  tva_par_pays_par_canal: {
    shopify: { France: [{ taux: 20, montant: 4166.67 }] },
    manomano: { Belgique: [{ taux: 21, montant: 1050.0 }] },
  },
};

const MOCK_ANOMALIES: Anomaly[] = [
  { type: "tva_mismatch", severity: "error", canal: "shopify", reference: "REF1", detail: "TVA issue", expected_value: null, actual_value: null },
  { type: "orphan_sale", severity: "warning", canal: "manomano", reference: "REF2", detail: "Orphan", expected_value: null, actual_value: null },
  { type: "orphan_sale", severity: "warning", canal: "shopify", reference: "REF3", detail: "Orphan 2", expected_value: null, actual_value: null },
  { type: "amount_mismatch", severity: "info", canal: "decathlon", reference: "REF4", detail: "Amount issue", expected_value: null, actual_value: null },
  { type: "amount_mismatch", severity: "info", canal: "shopify", reference: "REF5", detail: "Amount issue 2", expected_value: null, actual_value: null },
  { type: "tva_mismatch", severity: "info", canal: "manomano", reference: "REF6", detail: "TVA info", expected_value: null, actual_value: null },
];

const EMPTY_SUMMARY: Summary = {
  transactions_par_canal: {},
  ecritures_par_type: {},
  totaux: { debit: 0, credit: 0 },
  ca_par_canal: {},
  remboursements_par_canal: {},
  taux_remboursement_par_canal: {},
  commissions_par_canal: {},
  net_vendeur_par_canal: {},
  tva_collectee_par_canal: {},
  ventilation_ca_par_canal: {},
  repartition_geo_globale: {},
  repartition_geo_par_canal: {},
  tva_par_pays_par_canal: {},
};

// ============ KpiCard Tests ============

describe("KpiCard", () => {
  it("renders metric variant with title, value, and icon", () => {
    render(
      <KpiCard title="CA Total" value="30 000,00 €" icon={Coins} variant="metric" />
    );
    expect(screen.getByText("CA Total")).toBeTruthy();
    expect(screen.getByText("30 000,00 €")).toBeTruthy();
  });

  it("renders status variant with colored border", () => {
    const { container } = render(
      <KpiCard title="Balance" value="✓ Équilibré" variant="status" borderColor="green" />
    );
    const card = container.querySelector("[class*='border-l-green']");
    expect(card).toBeTruthy();
  });

  it("renders subtitle when provided", () => {
    render(
      <KpiCard title="Net Vendeur" value="37 680,00 €" subtitle="87,2 % du CA" />
    );
    expect(screen.getByText("87,2 % du CA")).toBeTruthy();
  });

  it("calls onNavigate when clicked", () => {
    const onNavigate = vi.fn();
    render(
      <KpiCard title="Anomalies" value="6" onNavigate={onNavigate} variant="status" borderColor="orange" />
    );
    const card = screen.getByRole("button");
    fireEvent.click(card);
    expect(onNavigate).toHaveBeenCalledTimes(1);
  });

  it("has correct aria-label combining title and value", () => {
    render(
      <KpiCard title="CA Total TTC" value="43 200,00 €" />
    );
    expect(screen.getByLabelText("CA Total TTC : 43 200,00 €")).toBeTruthy();
  });

  it("shows loading skeleton when loading", () => {
    const { container } = render(
      <KpiCard title="CA" value="0" loading />
    );
    expect(container.querySelector(".animate-pulse")).toBeTruthy();
  });
});

// ============ ChartCard Tests ============

describe("ChartCard", () => {
  it("renders title and subtitle", () => {
    render(
      <ChartCard title="Test Chart" subtitle="Some subtitle" minHeight={200}>
        <div>chart</div>
      </ChartCard>
    );
    expect(screen.getByText("Test Chart")).toBeTruthy();
    expect(screen.getByText("Some subtitle")).toBeTruthy();
  });

  it("renders empty state when empty=true", () => {
    render(
      <ChartCard title="Empty Chart" minHeight={200} empty emptyMessage="Aucune donnée">
        <div>should not show</div>
      </ChartCard>
    );
    expect(screen.getByText("Aucune donnée")).toBeTruthy();
  });

  it("renders sr-only accessible table when provided", () => {
    const { container } = render(
      <ChartCard
        title="Accessible Chart"
        minHeight={200}
        accessibleTable={{
          caption: "Test table",
          headers: ["Col1", "Col2"],
          rows: [["A", "B"]],
        }}
      >
        <div>chart</div>
      </ChartCard>
    );
    const srTable = container.querySelector("table.sr-only");
    expect(srTable).toBeTruthy();
    expect(srTable?.querySelector("caption")?.textContent).toBe("Test table");
  });
});

// ============ DashboardTab Tests ============

describe("DashboardTab", () => {
  it("renders without crashing with full data", () => {
    render(
      <DashboardTab
        summary={MOCK_SUMMARY}
        anomalies={MOCK_ANOMALIES}
        htTtcMode="ttc"
      />
    );
    // KPI zone titles should be visible
    expect(screen.getByText("CA Total TTC")).toBeTruthy();
    expect(screen.getByText("Net Vendeur")).toBeTruthy();
    // "Transactions" may appear in KPI cards + accessible table headers
    expect(screen.getAllByText("Transactions").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Taux Remboursement")).toBeTruthy();
    expect(screen.getByText("Balance D/C")).toBeTruthy();
    // "Anomalies" appears in KPI card + chart zone
    expect(screen.getAllByText("Anomalies").length).toBeGreaterThanOrEqual(1);
  });

  it("displays correct KPI values", () => {
    render(
      <DashboardTab
        summary={MOCK_SUMMARY}
        anomalies={MOCK_ANOMALIES}
        htTtcMode="ttc"
      />
    );
    // CA TTC = 30000 + 9600 + 3600 = 43200
    expect(screen.getByText("43 200,00 €")).toBeTruthy();
    // Transactions = 200 + 100 + 42 = 342
    expect(screen.getByText("342")).toBeTruthy();
    // Anomaly count
    expect(screen.getByText("6")).toBeTruthy();
  });

  it("renders chart zone titles", () => {
    render(
      <DashboardTab
        summary={MOCK_SUMMARY}
        anomalies={MOCK_ANOMALIES}
        htTtcMode="ttc"
      />
    );
    expect(screen.getByText("Répartition CA TTC")).toBeTruthy();
    // Title + sr-only caption both exist
    expect(screen.getAllByText("Rentabilité par canal").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Taux de remboursement").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Santé des données").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Lot 2 chart titles", () => {
    render(
      <DashboardTab
        summary={MOCK_SUMMARY}
        anomalies={MOCK_ANOMALIES}
        htTtcMode="ttc"
      />
    );
    expect(screen.getByText("Écritures par type")).toBeTruthy();
    // Title + sr-only table caption both contain this text
    expect(screen.getAllByText("TVA collectée par canal").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Répartition géographique").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Ventilation CA")).toBeTruthy();
  });

  it("shows empty state when ca_par_canal is empty", () => {
    render(
      <DashboardTab
        summary={EMPTY_SUMMARY}
        anomalies={[]}
        htTtcMode="ttc"
      />
    );
    expect(screen.getByText("Données financières non disponibles")).toBeTruthy();
  });

  it("empty state has 'Voir les anomalies' button when onNavigateTab provided", () => {
    const onNav = vi.fn();
    render(
      <DashboardTab
        summary={EMPTY_SUMMARY}
        anomalies={[]}
        htTtcMode="ttc"
        onNavigateTab={onNav}
      />
    );
    const btn = screen.getByText("Voir les anomalies →");
    fireEvent.click(btn);
    expect(onNav).toHaveBeenCalledWith("anomalies");
  });

  it("navigates to anomalies when clicking anomaly KPI card", () => {
    const onNav = vi.fn();
    render(
      <DashboardTab
        summary={MOCK_SUMMARY}
        anomalies={MOCK_ANOMALIES}
        htTtcMode="ttc"
        onNavigateTab={onNav}
      />
    );
    // Find the KPI card with role="button" that has "Anomalies" in its aria-label
    const anomalyCard = screen.getByLabelText(/Anomalies/);
    fireEvent.click(anomalyCard);
    expect(onNav).toHaveBeenCalledWith("anomalies");
  });

  it("switches to HT mode labels", () => {
    render(
      <DashboardTab
        summary={MOCK_SUMMARY}
        anomalies={MOCK_ANOMALIES}
        htTtcMode="ht"
      />
    );
    expect(screen.getByText("CA Total HT")).toBeTruthy();
    expect(screen.getByText("Répartition CA HT")).toBeTruthy();
  });

  it("shows balanced status when debit equals credit", () => {
    render(
      <DashboardTab
        summary={MOCK_SUMMARY}
        anomalies={[]}
        htTtcMode="ttc"
      />
    );
    expect(screen.getByText("✓ Équilibré")).toBeTruthy();
  });

  it("shows no-anomaly banner when no anomalies and no refunds", () => {
    const noRefundSummary: Summary = {
      ...MOCK_SUMMARY,
      taux_remboursement_par_canal: { shopify: 0, manomano: 0, decathlon: 0 },
    };
    render(
      <DashboardTab
        summary={noRefundSummary}
        anomalies={[]}
        htTtcMode="ttc"
      />
    );
    expect(screen.getByText(/Aucune anomalie détectée/)).toBeTruthy();
  });
});

// ============ Accessibility Tests ============

describe("DashboardTab accessibility", () => {
  it("passes axe-core with full data", async () => {
    const { container } = render(
      <DashboardTab
        summary={MOCK_SUMMARY}
        anomalies={MOCK_ANOMALIES}
        htTtcMode="ttc"
      />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("passes axe-core with empty data", async () => {
    const { container } = render(
      <DashboardTab
        summary={EMPTY_SUMMARY}
        anomalies={[]}
        htTtcMode="ttc"
      />
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
