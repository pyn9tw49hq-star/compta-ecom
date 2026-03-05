"use client";

import { useState, useMemo, Fragment } from "react";
import { ChevronRight, ListFilter, ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { getChannelMeta } from "@/lib/channels";
import { countVisualCardsBySeverity } from "@/lib/anomalyCardKey";
import { useNewDesign } from "@/hooks/useNewDesign";
import type { Anomaly } from "@/lib/types";

// --- Task 1: Constants ---

export interface SeverityMeta {
  label: string;
  badgeClass: string;
  borderClass: string;
  order: number;
}

export const SEVERITY_META: Record<string, SeverityMeta> = {
  error: {
    label: "Erreur",
    badgeClass: "bg-red-100 text-red-800 border-red-300 dark:bg-red-900 dark:text-red-200 dark:border-red-700",
    borderClass: "border-red-500",
    order: 2,
  },
  warning: {
    label: "Avertissement",
    badgeClass: "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700",
    borderClass: "border-orange-500",
    order: 1,
  },
  info: {
    label: "Info",
    badgeClass: "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-700",
    borderClass: "border-blue-500",
    order: 0,
  },
};

export const ANOMALY_CATEGORIES: Record<string, { label: string; types: string[] }> = {
  coherence_tva: {
    label: "Cohérence TVA",
    types: ["tva_mismatch", "tva_amount_mismatch", "ttc_coherence_mismatch", "unknown_country"],
  },
  rapprochement: {
    label: "Rapprochement ventes/encaissements",
    types: ["orphan_sale", "orphan_sale_summary", "orphan_settlement", "amount_mismatch", "orphan_refund", "prior_period_settlement", "prior_period_refund", "prior_period_lm_refund", "pending_manomano_payout", "overdue_manomano_payout"],
  },
  versements: {
    label: "Versements & détails",
    types: [
      "missing_payout", "missing_payout_summary", "negative_solde",
      "payout_detail_mismatch", "payout_missing_details",
      "orphan_payout_detail", "mixed_psp_payout", "unknown_psp_detail",
      "payout_cycle_missing", "payout_detail_refund_discovered", "direct_payment",
      "prior_period_manomano_refund",
    ],
  },
  retours: {
    label: "Retours & remboursements",
    types: ["return_no_matching_sale", "return_fee_nonzero", "return_tva_rate_aberrant"],
  },
  parsing: {
    label: "Parsing & données",
    types: [
      "parse_warning", "zero_amount_order", "missing_date", "invalid_date",
      "unknown_line_type", "unknown_transaction_type", "unknown_payout_type", "unknown_psp",
    ],
  },
  lettrage: {
    label: "Lettrage comptable",
    types: ["lettrage_511_unbalanced", "balance_error"],
  },
  delais: {
    label: "Délais de paiement",
    types: ["payment_delay"],
  },
};

export const ANOMALY_TYPE_LABELS: Record<string, string> = {
  orphan_sale: "Vente sans encaissement",
  orphan_sale_summary: "Commandes sans encaissement",
  orphan_settlement: "Encaissement sans commande",
  tva_mismatch: "Taux de TVA incohérent",
  tva_amount_mismatch: "Montant TVA incorrect",
  ttc_coherence_mismatch: "Total TTC incohérent",
  unknown_country: "Pays non reconnu",
  amount_mismatch: "Écart de montant",
  balance_error: "Déséquilibre débit/crédit",
  missing_payout: "Versement en attente",
  payout_cycle_missing: "Cycle de versement manquant",
  payment_delay: "Retard de paiement",
  orphan_refund: "Remboursement sans commande",
  lettrage_511_unbalanced: "Lettrage banque déséquilibré",
  payout_detail_mismatch: "Écart sur détail versement",
  payout_missing_details: "Versement sans détail",
  orphan_payout_detail: "Détail versement sans correspondance",
  unknown_psp_detail: "Moyen de paiement inconnu",
  mixed_psp_payout: "Versement multi-paiements",
  payout_detail_refund_discovered: "Remboursement détecté dans versement",
  return_no_matching_sale: "Remboursement sans commande d'origine",
  return_fee_nonzero: "Frais de retour non nuls",
  unknown_psp: "Moyen de paiement non reconnu",
  direct_payment: "Paiement direct",
  parse_warning: "Avertissement de lecture fichier",
  zero_amount_order: "Commande à montant nul",
  missing_date: "Date manquante",
  invalid_date: "Date invalide",
  unknown_line_type: "Type de ligne inconnu",
  unknown_transaction_type: "Type de transaction inconnu",
  unknown_payout_type: "Type de versement inconnu",
  prior_period_settlement: "Encaissements période antérieure",
  prior_period_refund: "Remboursements période antérieure",
  pending_manomano_payout: "Reversements ManoMano en attente",
  overdue_manomano_payout: "Reversements ManoMano en retard",
  prior_period_manomano_refund: "Remboursements ManoMano période antérieure",
  return_tva_rate_aberrant: "Taux TVA aberrant sur remboursement",
  country_conflict: "Conflit de pays sur une commande",
  missing_country_iso: "Code pays manquant",
  unknown_country_alpha2: "Code pays non reconnu",
  order_reference_not_in_lookup: "Référence commande introuvable",
  missing_payout_summary: "Résumé reversements en attente",
  negative_solde: "Solde négatif marketplace",
  prior_period_lm_refund: "Remboursements Leroy Merlin année précédente",
};

function getTypeLabel(type: string): string {
  return ANOMALY_TYPE_LABELS[type] ?? type;
}

function getSeverityMeta(severity: string): SeverityMeta {
  return SEVERITY_META[severity] ?? SEVERITY_META.info;
}

/** Extract payment method name from a direct_payment anomaly detail string. */
function extractPaymentMethod(detail: string): string {
  const separators = [" — ", " - ", ": "];
  for (const sep of separators) {
    const idx = detail.indexOf(sep);
    if (idx > 0) {
      return detail.substring(0, idx).trim();
    }
  }
  return detail.trim();
}

/** Compute actual order count for an orphan_sale group (summary embeds count in detail). */
function getOrphanSaleCount(group: Anomaly[]): number {
  let count = 0;
  for (const a of group) {
    if (a.type === "orphan_sale_summary") {
      const match = a.detail.match(/^(\d+)\s+commande/);
      count += match ? parseInt(match[1], 10) : 1;
    } else {
      count += 1;
    }
  }
  return count;
}

// --- Task 2 + 3: Component ---

interface AnomaliesPanelProps {
  anomalies: Anomaly[];
}

/**
 * Displays anomalies with color-coded severity, filters, and counters.
 */
// --- V2 styling maps (faithful to .pen design) ---

const V2_SEV = {
  info: { bg: "#E8F0FA", stroke: "#BFDBFE", text: "#007B96", dot: "#3B82F6", label: "Info" },
  warning: { bg: "#FEF3EE", stroke: "#FED7AA", text: "#004080", dot: "#F97316", label: "Avertissement" },
  error: { bg: "#FEF2F2", stroke: "#FECACA", text: "#DC2626", dot: "#EF4444", label: "Erreur" },
} as const;

const V2_SEV_PLURAL: Record<string, [string, string]> = {
  info: ["info", "infos"],
  warning: ["avertissement", "avertissements"],
  error: ["erreur", "erreurs"],
};

const CANAL_COLORS: Record<string, string> = {
  shopify: "#95BF47",
  manomano: "#00B2A9",
  decathlon: "#0055A0",
  leroy_merlin: "#2D8C3C",
  leroymerlin: "#2D8C3C",
};

function getCanalColor(canal: string): string {
  return CANAL_COLORS[canal] ?? "#6B7280";
}

// --- V1 styling maps (kept for backward compat) ---

const V2_BADGE_STYLES: Record<string, string> = {
  info: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  warning: "bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  error: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  total: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

const V2_CARD_BG: Record<string, string> = {
  info: "bg-blue-50 border-l-4 border-blue-400 dark:bg-blue-900/20 dark:border-blue-500",
  warning: "bg-orange-50 border-l-4 border-orange-400 dark:bg-orange-900/20 dark:border-orange-500",
  error: "bg-red-50 border-l-4 border-red-400 dark:bg-red-900/20 dark:border-red-500",
};

const V2_BADGE_LABELS: Record<string, [string, string]> = {
  info: ["info", "infos"],
  warning: ["avertissement", "avertissements"],
  error: ["erreur", "erreurs"],
};

export default function AnomaliesPanel({ anomalies }: AnomaliesPanelProps) {
  const isV2 = useNewDesign();
  const [selectedCanals, setSelectedCanals] = useState<Set<string>>(new Set());
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [selectedSeverities, setSelectedSeverities] = useState<Set<string>>(new Set());

  // Unique values for filter options
  const uniqueCanals = useMemo(
    () => Array.from(new Set(anomalies.map((a) => a.canal))).sort(),
    [anomalies],
  );
  const uniqueTypes = useMemo(
    () => Array.from(new Set(anomalies.map((a) => a.type))).sort(),
    [anomalies],
  );
  const uniqueSeverities = useMemo(
    () =>
      Array.from(new Set(anomalies.map((a) => a.severity))).sort(
        (a, b) => getSeverityMeta(a).order - getSeverityMeta(b).order,
      ),
    [anomalies],
  );

  // Filtered anomalies
  const filteredAnomalies = useMemo(() => {
    let result = anomalies;
    if (selectedCanals.size > 0) {
      result = result.filter((a) => selectedCanals.has(a.canal));
    }
    if (selectedTypes.size > 0) {
      result = result.filter((a) => selectedTypes.has(a.type));
    }
    if (selectedSeverities.size > 0) {
      result = result.filter((a) => selectedSeverities.has(a.severity));
    }
    return result;
  }, [anomalies, selectedCanals, selectedTypes, selectedSeverities]);

  // Sort by severity order (stable sort)
  const sortedAnomalies = useMemo(
    () =>
      filteredAnomalies.slice().sort(
        (a, b) => getSeverityMeta(a.severity).order - getSeverityMeta(b.severity).order,
      ),
    [filteredAnomalies],
  );

  // Severity counts — unique visual cards (matches rendered card count exactly)
  const severityCounts = useMemo(() => {
    return countVisualCardsBySeverity(filteredAnomalies);
  }, [filteredAnomalies]);

  const isFiltered =
    selectedCanals.size > 0 || selectedTypes.size > 0 || selectedSeverities.size > 0;

  // Toggle helpers
  const toggleCanal = (canal: string) => {
    setSelectedCanals((prev) => {
      const next = new Set(prev);
      if (next.has(canal)) next.delete(canal);
      else next.add(canal);
      return next;
    });
  };

  const toggleType = (type: string) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const toggleSeverity = (severity: string) => {
    setSelectedSeverities((prev) => {
      const next = new Set(prev);
      if (next.has(severity)) next.delete(severity);
      else next.add(severity);
      return next;
    });
  };

  // Dropdown state for V2 filters
  const [canalDropdownOpen, setCanalDropdownOpen] = useState(false);
  const [sevDropdownOpen, setSevDropdownOpen] = useState(false);

  // Empty state
  if (anomalies.length === 0) {
    return (
      <div
        role="status"
        className="rounded-md border border-green-300 bg-green-50 p-6 text-center text-sm text-green-700 dark:border-green-700 dark:bg-green-950 dark:text-green-200"
      >
        Aucune anomalie détectée
      </div>
    );
  }

  // =====================================================================
  // V2 — Faithful .pen design: flat list, colored borders, inline badges
  // =====================================================================
  if (isV2) {
    const totalCount = severityCounts.info + severityCounts.warning + severityCounts.error;
    const totalAll = (() => {
      const allCounts = countVisualCardsBySeverity(anomalies);
      return allCounts.info + allCounts.warning + allCounts.error;
    })();

    // Build flat list sorted by severity (error first, then warning, then info)
    const v2Sorted = filteredAnomalies.slice().sort(
      (a, b) => getSeverityMeta(b.severity).order - getSeverityMeta(a.severity).order,
    );

    // Group anomalies for collapsible cards (same logic as V1 but rendered differently)
    const GROUPED_TYPES = new Set(["missing_payout", "missing_payout_summary", "negative_solde", "orphan_sale_summary", "orphan_sale", "direct_payment", "tva_mismatch", "payment_delay"]);
    const PRIOR_PERIOD_TYPES = new Set(["prior_period_settlement", "prior_period_refund", "prior_period_manomano_refund", "prior_period_lm_refund"]);

    // Build grouped structures per severity
    type GroupEntry = { key: string; severity: string; type: string; canal: string; label: string; items: Anomaly[]; summaries?: Anomaly[] };
    const groupedCards: GroupEntry[] = [];
    const flatCards: Anomaly[] = [];

    const SEVERITY_ORDER_ASC = ["info", "warning", "error"] as const;
    for (const severity of SEVERITY_ORDER_ASC) {
      const sevAnomalies = v2Sorted.filter((a) => a.severity === severity);
      if (sevAnomalies.length === 0) continue;

      const grouped = sevAnomalies.filter((a) => GROUPED_TYPES.has(a.type));
      const priorPeriod = sevAnomalies.filter((a) => PRIOR_PERIOD_TYPES.has(a.type));
      const others = sevAnomalies.filter((a) => !GROUPED_TYPES.has(a.type) && !PRIOR_PERIOD_TYPES.has(a.type));

      // Prior period → flat
      for (const a of priorPeriod) flatCards.push(a);
      for (const a of others) flatCards.push(a);

      // missing_payout by canal
      const mpByCanal = new Map<string, Anomaly[]>();
      const summaryByCanal = new Map<string, Anomaly[]>();
      for (const a of grouped.filter((a) => a.type === "missing_payout")) {
        const g = mpByCanal.get(a.canal) ?? []; g.push(a); mpByCanal.set(a.canal, g);
      }
      for (const a of grouped.filter((a) => a.type === "missing_payout_summary" || a.type === "negative_solde")) {
        const g = summaryByCanal.get(a.canal) ?? []; g.push(a); summaryByCanal.set(a.canal, g);
      }
      Array.from(mpByCanal.entries()).forEach(([canal, items]) => {
        groupedCards.push({ key: `mp-${severity}-${canal}`, severity, type: "missing_payout", canal, label: `${items.length} ${items.length > 1 ? "reversements manquants" : "reversement manquant"}`, items, summaries: summaryByCanal.get(canal) });
      });

      // payment_delay by canal
      const pdByCanal = new Map<string, Anomaly[]>();
      for (const a of grouped.filter((a) => a.type === "payment_delay")) {
        const g = pdByCanal.get(a.canal) ?? []; g.push(a); pdByCanal.set(a.canal, g);
      }
      Array.from(pdByCanal.entries()).forEach(([canal, items]) => {
        groupedCards.push({ key: `pd-${severity}-${canal}`, severity, type: "payment_delay", canal, label: `${items.length} ${items.length > 1 ? "retards de paiement" : "retard de paiement"}`, items });
      });

      // orphan_sale by canal
      const osByCanal = new Map<string, Anomaly[]>();
      for (const a of grouped.filter((a) => a.type === "orphan_sale_summary" || a.type === "orphan_sale")) {
        const g = osByCanal.get(a.canal) ?? []; g.push(a); osByCanal.set(a.canal, g);
      }
      Array.from(osByCanal.entries()).forEach(([canal, items]) => {
        const count = getOrphanSaleCount(items);
        groupedCards.push({ key: `os-${severity}-${canal}`, severity, type: "orphan_sale", canal, label: `${count} ${count > 1 ? "commandes sans encaissement" : "commande sans encaissement"}`, items });
      });

      // direct_payment by method
      const dpByMethod = new Map<string, Anomaly[]>();
      for (const a of grouped.filter((a) => a.type === "direct_payment")) {
        const method = extractPaymentMethod(a.detail);
        const g = dpByMethod.get(method) ?? []; g.push(a); dpByMethod.set(method, g);
      }
      Array.from(dpByMethod.entries()).forEach(([method, items]) => {
        groupedCards.push({ key: `dp-${severity}-${method}`, severity, type: "direct_payment", canal: items[0].canal, label: `${items.length} ${items.length > 1 ? "paiements directs" : "paiement direct"} — ${method}`, items });
      });

      // tva_mismatch by rate
      const tvaByRate = new Map<string, Anomaly[]>();
      for (const a of grouped.filter((a) => a.type === "tva_mismatch")) {
        const rk = `${a.actual_value ?? "?"}% au lieu de ${a.expected_value ?? "?"}%`;
        const g = tvaByRate.get(rk) ?? []; g.push(a); tvaByRate.set(rk, g);
      }
      Array.from(tvaByRate.entries()).forEach(([rateKey, items]) => {
        groupedCards.push({ key: `tva-${severity}-${rateKey}`, severity, type: "tva_mismatch", canal: items[0].canal, label: `${items.length} ${items.length > 1 ? "factures" : "facture"} avec taux de TVA incohérent — ${rateKey}`, items });
      });
    }

    const renderV2Card = (anomaly: Anomaly, idx: number) => {
      const sev = V2_SEV[anomaly.severity as keyof typeof V2_SEV] ?? V2_SEV.info;
      const channelMeta = getChannelMeta(anomaly.canal);
      return (
        <div
          key={`v2-flat-${idx}`}
          className="rounded-lg bg-card p-3 px-4 border"
          style={{ borderColor: sev.stroke }}
        >
          <div className="flex items-center gap-2.5">
            <span
              className="rounded px-2 py-0.5 text-[10px] font-semibold border"
              style={{ background: sev.bg, borderColor: sev.stroke, color: sev.text }}
            >
              {sev.label}
            </span>
            <span className="text-xs font-semibold text-foreground">{getTypeLabel(anomaly.type)}</span>
            <span className="flex-1" />
            <span className="text-[11px] font-medium" style={{ color: getCanalColor(anomaly.canal) }}>
              {channelMeta.label}
            </span>
            {anomaly.reference && (
              <span className="text-[11px] text-muted-foreground">{anomaly.reference}</span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">{anomaly.detail}</p>
        </div>
      );
    };

    const renderV2GroupedCard = (group: GroupEntry) => {
      const sev = V2_SEV[group.severity as keyof typeof V2_SEV] ?? V2_SEV.info;
      const channelMeta = getChannelMeta(group.canal);
      return (
        <details
          key={group.key}
          className="group rounded-lg bg-card border"
          style={{ borderColor: sev.stroke }}
        >
          <summary className="cursor-pointer list-none p-3 px-4">
            <div className="flex items-center gap-2.5">
              <ChevronRight className="h-3.5 w-3.5 shrink-0 transition-transform group-open:rotate-90 text-muted-foreground" />
              <span
                className="rounded px-2 py-0.5 text-[10px] font-semibold border"
                style={{ background: sev.bg, borderColor: sev.stroke, color: sev.text }}
              >
                {sev.label}
              </span>
              <span className="text-xs font-semibold text-foreground">{group.label}</span>
              <span className="flex-1" />
              <span className="text-[11px] font-medium" style={{ color: getCanalColor(group.canal) }}>
                {channelMeta.label}
              </span>
            </div>
            {group.summaries && group.summaries.map((s, i) => (
              <div key={i} className="text-[11px] text-muted-foreground mt-1 ml-8">
                {s.detail}
              </div>
            ))}
            <div className="text-[11px] italic text-muted-foreground mt-1 ml-8">
              Cliquer pour voir les {group.items.length} references
            </div>
          </summary>
          <div className="px-4 pb-3 space-y-1">
            {group.items.map((anomaly, i) => (
              <div key={i} className="text-xs text-muted-foreground pl-1 py-1 border-t first:border-t-0">
                <span className="font-medium text-foreground">{anomaly.reference}</span>
                {" — "}{anomaly.detail}
              </div>
            ))}
          </div>
        </details>
      );
    };

    return (
      <div>
        {/* Severity badges bar + filters */}
        <div className="flex items-center gap-3 mb-6 flex-wrap">
          {(["info", "warning", "error"] as const).map((sev) => {
            const count = severityCounts[sev];
            if (count === 0) return null;
            const s = V2_SEV[sev];
            const [singular, plural] = V2_SEV_PLURAL[sev];
            return (
              <div
                key={sev}
                className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold border"
                style={{ background: s.bg, borderColor: s.stroke, color: s.text }}
              >
                <span className="w-2 h-2 rounded-full" style={{ background: s.dot }} />
                {count} {count > 1 ? plural : singular}
              </div>
            );
          })}
          <div className="flex-1" />

          {/* Canal filter dropdown */}
          {uniqueCanals.length > 1 && (
            <div className="relative">
              <button
                type="button"
                onClick={() => { setCanalDropdownOpen((v) => !v); setSevDropdownOpen(false); }}
                className="flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent"
              >
                <ListFilter className="h-3.5 w-3.5" />
                Canal
                {selectedCanals.size > 0 && <span className="text-muted-foreground">({selectedCanals.size})</span>}
                <ChevronDown className="h-3 w-3" />
              </button>
              {canalDropdownOpen && (
                <div className="absolute right-0 top-full mt-1 z-50 rounded-md border border-border bg-card p-2 shadow-md min-w-[160px]">
                  {uniqueCanals.map((canal) => (
                    <label key={canal} className="flex items-center gap-2 px-2 py-1 text-xs cursor-pointer hover:bg-accent rounded">
                      <input
                        type="checkbox"
                        checked={selectedCanals.has(canal)}
                        onChange={() => toggleCanal(canal)}
                        className="rounded"
                      />
                      <span style={{ color: getCanalColor(canal) }} className="font-medium">
                        {getChannelMeta(canal).label}
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Severity filter dropdown */}
          {uniqueSeverities.length > 1 && (
            <div className="relative">
              <button
                type="button"
                onClick={() => { setSevDropdownOpen((v) => !v); setCanalDropdownOpen(false); }}
                className="flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent"
              >
                Sévérité
                {selectedSeverities.size > 0 && <span className="text-muted-foreground">({selectedSeverities.size})</span>}
                <ChevronDown className="h-3 w-3" />
              </button>
              {sevDropdownOpen && (
                <div className="absolute right-0 top-full mt-1 z-50 rounded-md border border-border bg-card p-2 shadow-md min-w-[160px]">
                  {uniqueSeverities.map((sev) => {
                    const s = V2_SEV[sev as keyof typeof V2_SEV] ?? V2_SEV.info;
                    return (
                      <label key={sev} className="flex items-center gap-2 px-2 py-1 text-xs cursor-pointer hover:bg-accent rounded">
                        <input
                          type="checkbox"
                          checked={selectedSeverities.has(sev)}
                          onChange={() => toggleSeverity(sev)}
                          className="rounded"
                        />
                        <span className="w-2 h-2 rounded-full" style={{ background: s.dot }} />
                        <span style={{ color: s.text }} className="font-medium">{s.label}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <span className="text-xs text-muted-foreground">{totalCount} anomalies sur {totalAll} total</span>
        </div>

        {/* Flat card list */}
        <div className="space-y-2">
          {(() => {
            // Interleave grouped and flat cards by severity order
            const rendered: React.ReactNode[] = [];
            for (const severity of (["info", "warning", "error"] as const)) {
              // Grouped cards for this severity
              for (const gc of groupedCards.filter((g) => g.severity === severity)) {
                rendered.push(renderV2GroupedCard(gc));
              }
              // Flat cards for this severity
              const sevFlat = flatCards.filter((a) => a.severity === severity);
              for (let i = 0; i < sevFlat.length; i++) {
                rendered.push(renderV2Card(sevFlat[i], rendered.length));
              }
            }
            return rendered;
          })()}
        </div>
      </div>
    );
  }

  // =====================================================================
  // V1 — Original design
  // =====================================================================

  return (
    <div>
      {/* Severity counters */}
      {isV2 ? (
        <div className="flex items-center gap-3 mb-6">
          {(["info", "warning", "error"] as const).map((sev) => {
            const count = severityCounts[sev];
            if (count === 0) return null;
            const [singular, plural] = V2_BADGE_LABELS[sev];
            return (
              <span
                key={sev}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${V2_BADGE_STYLES[sev]}`}
              >
                {count} {count > 1 ? plural : singular}
              </span>
            );
          })}
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${V2_BADGE_STYLES.total}`}
          >
            {severityCounts.info + severityCounts.warning + severityCounts.error} au total
          </span>
        </div>
      ) : (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {severityCounts.info > 0 && (
            <Badge variant="outline" className={SEVERITY_META.info.badgeClass}>
              {severityCounts.info} {severityCounts.info > 1 ? "infos" : "info"}
            </Badge>
          )}
          {severityCounts.warning > 0 && (
            <Badge variant="outline" className={SEVERITY_META.warning.badgeClass}>
              {severityCounts.warning} {severityCounts.warning > 1 ? "avertissements" : "avertissement"}
            </Badge>
          )}
          {severityCounts.error > 0 && (
            <Badge variant="outline" className={SEVERITY_META.error.badgeClass}>
              {severityCounts.error} {severityCounts.error > 1 ? "erreurs" : "erreur"}
            </Badge>
          )}
          {isFiltered && (
            <span className="text-sm text-muted-foreground">
              (sur {anomalies.length} total)
            </span>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 space-y-3">
        {uniqueCanals.length > 1 && (
          <div>
            <span className="text-sm font-medium mr-2">Canal :</span>
            {uniqueCanals.map((canal) => (
              <label
                key={canal}
                className="inline-flex items-center mr-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selectedCanals.has(canal)}
                  onChange={() => toggleCanal(canal)}
                  className="mr-1"
                />
                {getChannelMeta(canal).label}
              </label>
            ))}
          </div>
        )}

        {uniqueTypes.length > 1 && (
          <div>
            <span className="text-sm font-medium mr-2">Type :</span>
            {uniqueTypes.map((type) => (
              <label
                key={type}
                className="inline-flex items-center mr-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selectedTypes.has(type)}
                  onChange={() => toggleType(type)}
                  className="mr-1"
                />
                {getTypeLabel(type)}
              </label>
            ))}
          </div>
        )}

        {uniqueSeverities.length > 1 && (
          <div>
            <span className="text-sm font-medium mr-2">Sévérité :</span>
            {uniqueSeverities.map((sev) => (
              <label
                key={sev}
                className="inline-flex items-center mr-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selectedSeverities.has(sev)}
                  onChange={() => toggleSeverity(sev)}
                  className="mr-1"
                />
                {getSeverityMeta(sev).label}
              </label>
            ))}
          </div>
        )}
      </div>

      {/* Anomaly cards — severity-first ordering, then type grouping within each severity */}
      <div className="space-y-2">
        {(() => {
          const GROUPED_TYPES = new Set(["missing_payout", "missing_payout_summary", "negative_solde", "orphan_sale_summary", "orphan_sale", "direct_payment", "tva_mismatch", "payment_delay"]);
          const PRIOR_PERIOD_TYPES = new Set(["prior_period_settlement", "prior_period_refund", "prior_period_manomano_refund", "prior_period_lm_refund"]);
          const SEVERITY_ORDER = ["info", "warning", "error"] as const;

          return SEVERITY_ORDER.map((severity) => {
            const sevAnomalies = sortedAnomalies.filter((a) => a.severity === severity);
            if (sevAnomalies.length === 0) return null;

            const grouped = sevAnomalies.filter((a) => GROUPED_TYPES.has(a.type));
            const priorPeriod = sevAnomalies.filter((a) => PRIOR_PERIOD_TYPES.has(a.type));
            const others = sevAnomalies.filter((a) => !GROUPED_TYPES.has(a.type) && !PRIOR_PERIOD_TYPES.has(a.type));

            // Group missing_payout by canal
            const missingPayoutByCanal = new Map<string, Anomaly[]>();
            for (const a of grouped.filter((a) => a.type === "missing_payout")) {
              const group = missingPayoutByCanal.get(a.canal) ?? [];
              group.push(a);
              missingPayoutByCanal.set(a.canal, group);
            }

            // Group payment_delay by canal
            const paymentDelayByCanal = new Map<string, Anomaly[]>();
            for (const a of grouped.filter((a) => a.type === "payment_delay")) {
              const group = paymentDelayByCanal.get(a.canal) ?? [];
              group.push(a);
              paymentDelayByCanal.set(a.canal, group);
            }

            // Collect missing_payout_summary and negative_solde by canal (for group headers)
            const summaryByCanal = new Map<string, Anomaly[]>();
            for (const a of grouped.filter((a) => a.type === "missing_payout_summary" || a.type === "negative_solde")) {
              const group = summaryByCanal.get(a.canal) ?? [];
              group.push(a);
              summaryByCanal.set(a.canal, group);
            }

            // Group orphan_sale_summary + orphan_sale by canal
            const orphanSaleByCanal = new Map<string, Anomaly[]>();
            for (const a of grouped.filter((a) => a.type === "orphan_sale_summary" || a.type === "orphan_sale")) {
              const group = orphanSaleByCanal.get(a.canal) ?? [];
              group.push(a);
              orphanSaleByCanal.set(a.canal, group);
            }

            // Group direct_payment by payment method
            const directPaymentByMethod = new Map<string, Anomaly[]>();
            for (const a of grouped.filter((a) => a.type === "direct_payment")) {
              const method = extractPaymentMethod(a.detail);
              const group = directPaymentByMethod.get(method) ?? [];
              group.push(a);
              directPaymentByMethod.set(method, group);
            }

            // Group tva_mismatch by rate discrepancy (actual vs expected)
            const tvaMismatchByRate = new Map<string, Anomaly[]>();
            for (const a of grouped.filter((a) => a.type === "tva_mismatch")) {
              const key = `${a.actual_value ?? "?"}% au lieu de ${a.expected_value ?? "?"}%`;
              const group = tvaMismatchByRate.get(key) ?? [];
              group.push(a);
              tvaMismatchByRate.set(key, group);
            }

            return (
              <Fragment key={severity}>
                {/* Prior period cards */}
                {priorPeriod.map((anomaly, i) => {
                  const meta = getSeverityMeta(anomaly.severity);
                  const channelMeta = getChannelMeta(anomaly.canal);
                  return (
                    <div
                      key={`pp-${severity}-${i}`}
                      className={isV2
                        ? `rounded-lg p-4 mb-3 ${V2_CARD_BG[anomaly.severity] ?? ""}`
                        : `rounded-md border border-l-4 ${meta.borderClass} bg-card p-3`}
                    >
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <Badge variant="outline" className={meta.badgeClass}>
                          {meta.label}
                        </Badge>
                        <span>{getTypeLabel(anomaly.type)}</span>
                        {anomaly.canal && (
                          <Badge variant="outline" className={channelMeta.badgeClass}>
                            {channelMeta.label}
                          </Badge>
                        )}
                      </div>
                      <div className="mt-1 text-sm text-muted-foreground pl-1">
                        {anomaly.detail}
                      </div>
                    </div>
                  );
                })}

                {/* Grouped missing_payout sections */}
                {Array.from(missingPayoutByCanal.entries()).map(([canal, group]) => {
                  const channelMeta = getChannelMeta(canal);
                  const meta = getSeverityMeta(group[0].severity);
                  const canalSummaries = summaryByCanal.get(canal);
                  return (
                    <details key={`mp-${severity}-${canal}`} className={isV2
                      ? `group rounded-lg mb-3 ${V2_CARD_BG[group[0].severity] ?? ""}`
                      : `group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
                      <summary className="cursor-pointer list-none p-3 text-sm font-medium">
                        <div className="flex items-center gap-2">
                          <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" />
                          <Badge variant="outline" className={meta.badgeClass}>
                            {meta.label}
                          </Badge>
                          <Badge variant="outline" className={channelMeta.badgeClass}>
                            {channelMeta.label}
                          </Badge>
                          <span>
                            {group.length} {group.length > 1 ? "reversements manquants" : "reversement manquant"}
                          </span>
                        </div>
                        {canalSummaries && canalSummaries.map((s, i) => (
                          <div key={i} className="text-xs font-normal text-muted-foreground mt-1 ml-6">
                            {s.detail}
                          </div>
                        ))}
                      </summary>
                      <div className="px-3 pb-3 space-y-1">
                        {group.map((anomaly, i) => (
                          <div key={i} className="text-sm text-muted-foreground pl-1 py-1 border-t first:border-t-0">
                            <span className="font-medium text-foreground">{anomaly.reference}</span>
                            {" — "}{anomaly.detail}
                          </div>
                        ))}
                      </div>
                    </details>
                  );
                })}

                {/* Grouped payment_delay sections */}
                {Array.from(paymentDelayByCanal.entries()).map(([canal, group]) => {
                  const channelMeta = getChannelMeta(canal);
                  const meta = getSeverityMeta(group[0].severity);
                  return (
                    <details key={`pd-${severity}-${canal}`} className={isV2
                      ? `group rounded-lg mb-3 ${V2_CARD_BG[group[0].severity] ?? ""}`
                      : `group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
                      <summary className="cursor-pointer list-none p-3 text-sm font-medium">
                        <div className="flex items-center gap-2">
                          <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" />
                          <Badge variant="outline" className={meta.badgeClass}>
                            {meta.label}
                          </Badge>
                          <Badge variant="outline" className={channelMeta.badgeClass}>
                            {channelMeta.label}
                          </Badge>
                          <span>
                            {group.length} {group.length > 1 ? "retards de paiement" : "retard de paiement"}
                          </span>
                        </div>
                      </summary>
                      <div className="px-3 pb-3 space-y-1">
                        {group.map((anomaly, i) => (
                          <div key={i} className="text-sm text-muted-foreground pl-1 py-1 border-t first:border-t-0">
                            <span className="font-medium text-foreground">{anomaly.reference}</span>
                            {" — "}{anomaly.detail}
                          </div>
                        ))}
                      </div>
                    </details>
                  );
                })}

                {/* Grouped orphan_sale_summary / orphan_sale sections */}
                {Array.from(orphanSaleByCanal.entries()).map(([canal, group]) => {
                  const channelMeta = getChannelMeta(canal);
                  const meta = getSeverityMeta(group[0].severity);
                  const orderCount = getOrphanSaleCount(group);
                  return (
                    <details key={`os-${severity}-${canal}`} className={isV2
                      ? `group rounded-lg mb-3 ${V2_CARD_BG[group[0].severity] ?? ""}`
                      : `group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
                      <summary className="cursor-pointer list-none p-3 flex items-center gap-2 text-sm font-medium">
                        <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" />
                        <Badge variant="outline" className={meta.badgeClass}>
                          {meta.label}
                        </Badge>
                        <Badge variant="outline" className={channelMeta.badgeClass}>
                          {channelMeta.label}
                        </Badge>
                        <span>
                          {orderCount} {orderCount > 1 ? "commandes sans encaissement" : "commande sans encaissement"}
                        </span>
                      </summary>
                      <div className="px-3 pb-3 space-y-1">
                        {group.map((anomaly, i) => (
                          <div key={i} className="text-sm text-muted-foreground pl-1 py-1 border-t first:border-t-0">
                            <span className="font-medium text-foreground">{anomaly.reference}</span>
                            {" — "}{anomaly.detail}
                          </div>
                        ))}
                      </div>
                    </details>
                  );
                })}

                {/* Grouped direct_payment sections — one card per payment method */}
                {Array.from(directPaymentByMethod.entries()).map(([method, group]) => {
                  const meta = getSeverityMeta(group[0].severity);
                  const channelMeta = getChannelMeta(group[0].canal);
                  return (
                    <details key={`dp-${severity}-${method}`} className={isV2
                      ? `group rounded-lg mb-3 ${V2_CARD_BG[group[0].severity] ?? ""}`
                      : `group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
                      <summary className="cursor-pointer list-none p-3 flex items-center gap-2 text-sm font-medium">
                        <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" />
                        <Badge variant="outline" className={meta.badgeClass}>
                          {meta.label}
                        </Badge>
                        <Badge variant="outline" className={channelMeta.badgeClass}>
                          {channelMeta.label}
                        </Badge>
                        <span>
                          {group.length} {group.length > 1 ? "paiements directs" : "paiement direct"} — {method}
                        </span>
                      </summary>
                      <div className="px-3 pb-3 space-y-1">
                        {group.map((anomaly, i) => (
                          <div key={i} className="text-sm text-muted-foreground pl-1 py-1 border-t first:border-t-0">
                            <span className="font-medium text-foreground">{anomaly.reference}</span>
                            {" — "}{anomaly.detail}
                          </div>
                        ))}
                      </div>
                    </details>
                  );
                })}

                {/* Grouped tva_mismatch sections — one card per rate discrepancy */}
                {Array.from(tvaMismatchByRate.entries()).map(([rateKey, group]) => {
                  const meta = getSeverityMeta(group[0].severity);
                  const channelMeta = getChannelMeta(group[0].canal);
                  return (
                    <details key={`tva-${severity}-${rateKey}`} className={isV2
                      ? `group rounded-lg mb-3 ${V2_CARD_BG[group[0].severity] ?? ""}`
                      : `group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
                      <summary className="cursor-pointer list-none p-3 flex items-center gap-2 text-sm font-medium">
                        <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" />
                        <Badge variant="outline" className={meta.badgeClass}>
                          {meta.label}
                        </Badge>
                        <Badge variant="outline" className={channelMeta.badgeClass}>
                          {channelMeta.label}
                        </Badge>
                        <span>
                          {group.length} {group.length > 1 ? "factures" : "facture"} avec taux de TVA incohérent — {rateKey}
                        </span>
                      </summary>
                      <div className="px-3 pb-3 space-y-1">
                        {group.map((anomaly, i) => (
                          <div key={i} className="text-sm text-muted-foreground pl-1 py-1 border-t first:border-t-0">
                            <span className="font-medium text-foreground">{anomaly.reference}</span>
                            {" — "}{anomaly.detail}
                          </div>
                        ))}
                      </div>
                    </details>
                  );
                })}

                {/* Other anomalies — flat list */}
                {others.map((anomaly, i) => {
                  const meta = getSeverityMeta(anomaly.severity);
                  const channelMeta = getChannelMeta(anomaly.canal);
                  return (
                    <div
                      key={`other-${severity}-${i}`}
                      className={isV2
                        ? `rounded-lg p-4 mb-3 ${V2_CARD_BG[anomaly.severity] ?? ""}`
                        : `rounded-md border border-l-4 ${meta.borderClass} bg-card p-3`}
                    >
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <Badge variant="outline" className={meta.badgeClass}>
                          {meta.label}
                        </Badge>
                        <span>{getTypeLabel(anomaly.type)}</span>
                        <Badge variant="outline" className={channelMeta.badgeClass}>
                          {channelMeta.label}
                        </Badge>
                        <span className="text-muted-foreground">{anomaly.reference}</span>
                      </div>
                      <div className="mt-1 text-sm text-muted-foreground pl-1">
                        {anomaly.detail}
                      </div>
                    </div>
                  );
                })}
              </Fragment>
            );
          });
        })()}
      </div>
    </div>
  );
}
