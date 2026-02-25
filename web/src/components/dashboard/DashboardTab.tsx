"use client";

import { useMemo } from "react";
import { useTheme } from "next-themes";
import {
  Coins,
  Wallet,
  ArrowLeftRight,
  Undo2,
  Scale,
  AlertTriangle,
  BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { getChannelMeta } from "@/lib/channels";
import { formatCurrency, formatCount, formatPercent } from "@/lib/format";
import {
  getChannelColor,
  getRefundRateColor,
  getSeverityColor,
  ENTRY_TYPE_COLORS,
  GEO_PALETTE,
} from "./chartColors";
import KpiCard from "./KpiCard";
import RevenuePieChart from "./RevenuePieChart";
import RevenueBarChart from "./RevenueBarChart";
import ProfitabilityChart from "./ProfitabilityChart";
import RefundRateChart from "./RefundRateChart";
import AnomalySeverityChart from "./AnomalySeverityChart";
import EntryTypeDonut from "./EntryTypeDonut";
import VatChart from "./VatChart";
import GeoChart from "./GeoChart";
import VentilationChart from "./VentilationChart";
import AnomalyCategoryDonut from "./AnomalyCategoryDonut";
import type { Summary, Anomaly } from "@/lib/types";

interface DashboardTabProps {
  summary: Summary;
  anomalies: Anomaly[];
  htTtcMode: "ht" | "ttc";
  onHtTtcModeChange?: (mode: "ht" | "ttc") => void;
  onNavigateTab?: (tab: string) => void;
}

const SEVERITY_LABELS: Record<string, string> = {
  error: "Erreur(s)",
  warning: "Avertissement(s)",
  info: "Info(s)",
};

const ENTRY_TYPE_LABELS: Record<string, string> = {
  sale: "Vente",
  refund: "Remboursement",
  settlement: "Règlement",
  commission: "Commission",
  payout: "Reversement",
  fee: "Frais",
};

const ANOMALY_TYPE_LABELS: Record<string, string> = {
  tva_mismatch: "Taux TVA incohérent",
  tva_amount_mismatch: "Montant TVA incorrect",
  orphan_sale: "Vente orpheline",
  orphan_settlement: "Règlement orphelin",
  amount_mismatch: "Écart montant",
  lettrage_511_unbalanced: "Lettrage 511 déséquilibré",
  mixed_psp_payout: "PSP hétérogène",
  balance_error: "Erreur d'équilibre",
  prior_period_refund: "Remb. période antérieure",
  payout_detail_refund: "Remb. dans payout detail",
  return_no_matching_sale: "Remb. sans vente correspondante",
  direct_payment: "Paiement direct",
  prior_period_settlement: "Règlement période antérieure",
  pending_manomano_payout: "Versement ManoMano en attente",
  prior_period_manomano_refund: "Remb. ManoMano période antérieure",
};

/**
 * Dashboard tab orchestrator — transforms summary Record→Array, renders all chart zones.
 */
export function DashboardTab({ summary, anomalies, htTtcMode, onHtTtcModeChange, onNavigateTab }: DashboardTabProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const modeLabel = htTtcMode === "ht" ? "HT" : "TTC";

  const channels = useMemo(() => Object.keys(summary.ca_par_canal ?? {}), [summary.ca_par_canal]);
  const hasKpis = channels.length > 0;

  // --- KPI computations ---
  const kpiData = useMemo(() => {
    const caTtc = channels.reduce((s, c) => s + (summary.ca_par_canal[c]?.ttc ?? 0), 0);
    const caHt = channels.reduce((s, c) => s + (summary.ca_par_canal[c]?.ht ?? 0), 0);
    const caDisplay = htTtcMode === "ht" ? caHt : caTtc;
    const net = channels.reduce((s, c) => s + (summary.net_vendeur_par_canal[c] ?? 0), 0);
    const totalTx = Object.values(summary.transactions_par_canal).reduce((s, n) => s + n, 0);
    const rembTtc = channels.reduce((s, c) => s + (summary.remboursements_par_canal[c]?.ttc ?? 0), 0);
    const tauxRemb = caTtc > 0 ? (rembTtc / caTtc) * 100 : 0;
    const balance = summary.totaux.debit - summary.totaux.credit;
    const isBalanced = Math.abs(balance) < 0.01;

    // Severity counts for subtitle
    const sevCounts: Record<string, number> = { error: 0, warning: 0, info: 0 };
    for (const a of anomalies) sevCounts[a.severity] = (sevCounts[a.severity] ?? 0) + 1;
    const sevParts: string[] = [];
    if (sevCounts.error > 0) sevParts.push(`${sevCounts.error}\u2298`);
    if (sevCounts.warning > 0) sevParts.push(`${sevCounts.warning}\u26A0`);
    if (sevCounts.info > 0) sevParts.push(`${sevCounts.info}\u2139`);

    const netPct = caTtc > 0 ? (net / caTtc) * 100 : 0;

    return {
      caDisplay, net, netPct, totalTx, tauxRemb, balance, isBalanced,
      anomalyCount: anomalies.length, sevSubtitle: sevParts.join(" "),
    };
  }, [channels, summary, anomalies, htTtcMode]);

  // --- Zone 2: Revenue by channel ---
  const revenueData = useMemo(() => {
    return channels
      .map((c, i) => ({
        channel: c,
        label: getChannelMeta(c).label,
        value: htTtcMode === "ht" ? (summary.ca_par_canal[c]?.ht ?? 0) : (summary.ca_par_canal[c]?.ttc ?? 0),
        fill: getChannelColor(c, isDark, i),
      }))
      .sort((a, b) => b.value - a.value);
  }, [channels, summary.ca_par_canal, htTtcMode, isDark]);

  const revenueTotal = useMemo(() => revenueData.reduce((s, d) => s + d.value, 0), [revenueData]);

  // --- Zone 3: Profitability ---
  const profitabilityData = useMemo(() => {
    return channels.map((c) => {
      const ca = summary.ca_par_canal[c]?.ht ?? 0;
      const commissions = summary.commissions_par_canal[c]?.ht ?? 0;
      const net = summary.net_vendeur_par_canal[c] ?? 0;
      return {
        channel: c,
        label: getChannelMeta(c).label,
        ca,
        commissions,
        net,
        commissionRate: ca > 0 ? (commissions / ca) * 100 : 0,
      };
    });
  }, [channels, summary]);

  // --- Zone 4 left: Refund rate ---
  const refundRateData = useMemo(() => {
    return channels.map((c) => ({
      channel: c,
      label: getChannelMeta(c).label,
      rate: summary.taux_remboursement_par_canal[c] ?? 0,
      fill: getRefundRateColor(summary.taux_remboursement_par_canal[c] ?? 0, isDark),
    }));
  }, [channels, summary.taux_remboursement_par_canal, isDark]);

  // --- Zone 4 right: Anomaly severity ---
  const severityData = useMemo(() => {
    const counts: Record<string, number> = { error: 0, warning: 0, info: 0 };
    for (const a of anomalies) counts[a.severity] = (counts[a.severity] ?? 0) + 1;
    return (["error", "warning", "info"] as const)
      .filter((s) => counts[s] > 0)
      .map((s) => ({
        severity: s,
        label: SEVERITY_LABELS[s],
        count: counts[s],
        fill: getSeverityColor(s, isDark),
      }));
  }, [anomalies, isDark]);

  // --- Lot 2: Entry type donut ---
  const entryTypeData = useMemo(() => {
    return Object.entries(summary.ecritures_par_type).map(([type, count]) => ({
      type,
      label: ENTRY_TYPE_LABELS[type] ?? type,
      count,
      fill: isDark ? (ENTRY_TYPE_COLORS[type]?.dark ?? "#94a3b8") : (ENTRY_TYPE_COLORS[type]?.light ?? "#64748b"),
    }));
  }, [summary.ecritures_par_type, isDark]);

  const entryTypeTotal = useMemo(() => entryTypeData.reduce((s, d) => s + d.count, 0), [entryTypeData]);

  // --- Lot 2: VAT by channel ---
  const vatData = useMemo(() => {
    return channels.map((c, i) => ({
      channel: c,
      label: getChannelMeta(c).label,
      amount: summary.tva_collectee_par_canal[c] ?? 0,
      fill: getChannelColor(c, isDark, i),
    }));
  }, [channels, summary.tva_collectee_par_canal, isDark]);

  // --- Lot 2: Geo treemap ---
  const geoData = useMemo(() => {
    const entries = Object.entries(summary.repartition_geo_globale ?? {})
      .map(([country, data]) => ({ country, ca_ttc: data.ca_ttc, count: data.count }))
      .sort((a, b) => b.ca_ttc - a.ca_ttc);

    const top10 = entries.slice(0, 10);
    const rest = entries.slice(10);
    if (rest.length > 0) {
      top10.push({
        country: "Autres",
        ca_ttc: rest.reduce((s, d) => s + d.ca_ttc, 0),
        count: rest.reduce((s, d) => s + d.count, 0),
      });
    }
    return top10.map((d, i) => {
      const geo = GEO_PALETTE[i % GEO_PALETTE.length];
      return { ...d, fill: isDark ? geo.dark : geo.light };
    });
  }, [summary.repartition_geo_globale, isDark]);

  const geoTotal = useMemo(() => geoData.reduce((s, d) => s + d.ca_ttc, 0), [geoData]);

  // --- Lot 2: Ventilation ---
  const ventilationData = useMemo(() => {
    if (!summary.ventilation_ca_par_canal) return [];
    return channels.map((c) => ({
      channel: c,
      label: getChannelMeta(c).label,
      produits_ht: summary.ventilation_ca_par_canal[c]?.produits_ht ?? 0,
      port_ht: summary.ventilation_ca_par_canal[c]?.port_ht ?? 0,
    }));
  }, [channels, summary.ventilation_ca_par_canal]);

  // --- Lot 2: Anomaly category donut ---
  const anomalyCategoryData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const a of anomalies) counts[a.type] = (counts[a.type] ?? 0) + 1;
    const CATEGORY_COLORS_LIGHT_DARK: Array<{ light: string; dark: string }> = [
      { light: "#2563eb", dark: "#60a5fa" },  // blue
      { light: "#dc2626", dark: "#f87171" },  // red
      { light: "#ea580c", dark: "#fb923c" },  // orange
      { light: "#16a34a", dark: "#4ade80" },  // green
      { light: "#9333ea", dark: "#c084fc" },  // purple
      { light: "#0891b2", dark: "#22d3ee" },  // cyan
      { light: "#be185d", dark: "#f472b6" },  // pink
      { light: "#854d0e", dark: "#facc15" },  // yellow
      { light: "#4f46e5", dark: "#818cf8" },  // indigo
      { light: "#059669", dark: "#34d399" },  // emerald
    ];
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([type, count], i) => {
        const color = CATEGORY_COLORS_LIGHT_DARK[i % CATEGORY_COLORS_LIGHT_DARK.length];
        return {
          type,
          label: ANOMALY_TYPE_LABELS[type] ?? type,
          count,
          fill: isDark ? color.dark : color.light,
        };
      });
  }, [anomalies, isDark]);

  // --- Refund rate border color helper ---
  const getKpiRefundBorder = (rate: number): "green" | "orange" | "red" => {
    if (rate < 5) return "green";
    if (rate <= 10) return "orange";
    return "red";
  };

  // --- Empty state ---
  if (!hasKpis) {
    return (
      <div className="rounded-md border border-dashed border-muted-foreground/30 p-12 text-center">
        <BarChart3 className="h-12 w-12 mx-auto text-muted-foreground/40 mb-4" aria-hidden="true" />
        <p className="text-lg font-medium text-muted-foreground">
          Données financières non disponibles
        </p>
        <p className="text-sm text-muted-foreground mt-2">
          Les indicateurs financiers (CA, commissions, net vendeur) n&apos;ont pas pu être calculés pour cette génération.
          Vérifiez que les fichiers source contiennent les données attendues.
        </p>
        {onNavigateTab && (
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => onNavigateTab("anomalies")}
          >
            Voir les anomalies →
          </Button>
        )}
      </div>
    );
  }

  const hasAnomalyOrRefund = anomalies.length > 0 || refundRateData.some((d) => d.rate > 0);
  const hasGeoData = geoData.length > 0;
  const hasVentilationData = ventilationData.length > 0;

  return (
    <div className="space-y-6">
      {/* HT/TTC Toggle */}
      {onHtTtcModeChange && (
        <div className="flex justify-end">
          <div className="inline-flex rounded-md border" role="group" aria-label="Affichage HT ou TTC">
            <button
              type="button"
              onClick={() => onHtTtcModeChange("ht")}
              className={`px-3 py-1 text-sm font-medium rounded-l-md transition-colors ${
                htTtcMode === "ht"
                  ? "bg-foreground text-background"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              HT
            </button>
            <button
              type="button"
              onClick={() => onHtTtcModeChange("ttc")}
              className={`px-3 py-1 text-sm font-medium rounded-r-md border-l transition-colors ${
                htTtcMode === "ttc"
                  ? "bg-foreground text-background"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              TTC
            </button>
          </div>
        </div>
      )}

      {/* Zone 1 — KPI Hero Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <KpiCard
          title={`CA Total ${modeLabel}`}
          value={`${formatCurrency(kpiData.caDisplay)} €`}
          subtitle={`${channels.length} ${channels.length > 1 ? "canaux" : "canal"}`}
          icon={Coins}
          variant="metric"
        />
        <KpiCard
          title="Net Vendeur"
          value={`${formatCurrency(kpiData.net)} €`}
          subtitle={`${formatPercent(kpiData.netPct)} du CA`}
          icon={Wallet}
          variant="metric"
        />
        <KpiCard
          title="Transactions"
          value={formatCount(kpiData.totalTx)}
          icon={ArrowLeftRight}
          variant="metric"
        />
        <KpiCard
          title="Taux Remboursement"
          value={formatPercent(kpiData.tauxRemb)}
          variant="status"
          borderColor={getKpiRefundBorder(kpiData.tauxRemb)}
          icon={Undo2}
        />
        <KpiCard
          title="Balance D/C"
          value={kpiData.isBalanced ? "✓ Équilibré" : `∆ ${formatCurrency(Math.abs(kpiData.balance))} €`}
          variant="status"
          borderColor={kpiData.isBalanced ? "green" : "red"}
          icon={Scale}
        />
        <KpiCard
          title="Anomalies"
          value={formatCount(kpiData.anomalyCount)}
          subtitle={kpiData.sevSubtitle || undefined}
          variant="status"
          borderColor={kpiData.anomalyCount === 0 ? "green" : kpiData.anomalyCount > 5 ? "red" : "orange"}
          icon={AlertTriangle}
          onNavigate={onNavigateTab ? () => onNavigateTab("anomalies") : undefined}
        />
      </div>

      {/* Zone 2 — Répartition CA */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
        <RevenueBarChart data={revenueData} modeLabel={modeLabel} />
        <RevenuePieChart data={revenueData} total={revenueTotal} modeLabel={modeLabel} />
      </div>

      {/* Zone 3 — Rentabilité (full width) */}
      <ProfitabilityChart data={profitabilityData} isDark={isDark} />

      {/* Zone 4 — Qualité & Santé */}
      {hasAnomalyOrRefund && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
          <RefundRateChart data={refundRateData} />
          <AnomalySeverityChart
            data={severityData}
            total={anomalies.length}
            onNavigateAnomalies={onNavigateTab ? () => onNavigateTab("anomalies") : undefined}
          />
        </div>
      )}

      {!hasAnomalyOrRefund && (
        <div className="rounded-md border-green-300 bg-green-50 border p-6 text-center text-sm text-green-700 dark:border-green-700 dark:bg-green-950 dark:text-green-200">
          ✓ Aucune anomalie détectée — aucun remboursement sur la période
        </div>
      )}

      {/* Lot 2 — Charts supplémentaires */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
        <EntryTypeDonut data={entryTypeData} total={entryTypeTotal} />
        <VatChart data={vatData} />
      </div>

      {/* Zone 5 — Géographie & Ventilation */}
      {(hasGeoData || hasVentilationData) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
          {hasGeoData && <GeoChart data={geoData} total={geoTotal} isDark={isDark} />}
          {hasVentilationData && <VentilationChart data={ventilationData} isDark={isDark} />}
        </div>
      )}

      {/* Lot 2 — Anomaly category donut */}
      {anomalyCategoryData.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
          <AnomalyCategoryDonut data={anomalyCategoryData} total={anomalies.length} />
        </div>
      )}
    </div>
  );
}
