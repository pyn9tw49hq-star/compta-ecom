"use client";

import { useState, useMemo } from "react";
import { ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { getChannelMeta } from "@/lib/channels";
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
    order: 0,
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
    order: 2,
  },
};

export const ANOMALY_CATEGORIES: Record<string, { label: string; types: string[] }> = {
  coherence_tva: {
    label: "Cohérence TVA",
    types: ["tva_mismatch", "tva_amount_mismatch", "ttc_coherence_mismatch", "unknown_country"],
  },
  rapprochement: {
    label: "Rapprochement ventes/encaissements",
    types: ["orphan_sale", "orphan_sale_summary", "orphan_settlement", "amount_mismatch", "orphan_refund", "prior_period_settlement", "prior_period_refund", "pending_manomano_payout"],
  },
  versements: {
    label: "Versements & détails",
    types: [
      "missing_payout", "payout_detail_mismatch", "payout_missing_details",
      "orphan_payout_detail", "mixed_psp_payout", "unknown_psp_detail",
      "payout_detail_refund_discovered", "direct_payment",
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
  return_tva_rate_aberrant: "Taux TVA aberrant sur remboursement",
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
export default function AnomaliesPanel({ anomalies }: AnomaliesPanelProps) {
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

  // Severity counts (on filtered data)
  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { error: 0, warning: 0, info: 0 };
    for (const a of filteredAnomalies) {
      counts[a.severity] = (counts[a.severity] ?? 0) + 1;
    }
    return counts;
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

  return (
    <div>
      {/* Severity counters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {severityCounts.error > 0 && (
          <Badge variant="outline" className={SEVERITY_META.error.badgeClass}>
            {severityCounts.error} {severityCounts.error > 1 ? "erreurs" : "erreur"}
          </Badge>
        )}
        {severityCounts.warning > 0 && (
          <Badge variant="outline" className={SEVERITY_META.warning.badgeClass}>
            {severityCounts.warning} {severityCounts.warning > 1 ? "avertissements" : "avertissement"}
          </Badge>
        )}
        {severityCounts.info > 0 && (
          <Badge variant="outline" className={SEVERITY_META.info.badgeClass}>
            {severityCounts.info} {severityCounts.info > 1 ? "infos" : "info"}
          </Badge>
        )}
        {isFiltered && (
          <span className="text-sm text-muted-foreground">
            (sur {anomalies.length} total)
          </span>
        )}
      </div>

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

      {/* Anomaly cards — grouped types in <details>, rest flat */}
      <div className="space-y-2">
        {(() => {
          const GROUPED_TYPES = new Set(["missing_payout", "orphan_sale_summary", "orphan_sale", "direct_payment", "tva_mismatch"]);
          const PRIOR_PERIOD_TYPES = new Set(["prior_period_settlement", "prior_period_refund"]);
          const grouped = sortedAnomalies.filter((a) => GROUPED_TYPES.has(a.type));
          const priorPeriod = sortedAnomalies.filter((a) => PRIOR_PERIOD_TYPES.has(a.type));
          const others = sortedAnomalies.filter((a) => !GROUPED_TYPES.has(a.type) && !PRIOR_PERIOD_TYPES.has(a.type));

          // Group missing_payout by canal
          const missingPayoutByCanal = new Map<string, Anomaly[]>();
          for (const a of grouped.filter((a) => a.type === "missing_payout")) {
            const group = missingPayoutByCanal.get(a.canal) ?? [];
            group.push(a);
            missingPayoutByCanal.set(a.canal, group);
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
            <>
              {/* Prior period cards — rendered first (Issue #1) */}
              {priorPeriod.map((anomaly, i) => {
                const meta = getSeverityMeta(anomaly.severity);
                const channelMeta = getChannelMeta(anomaly.canal);
                return (
                  <div
                    key={`pp-${i}`}
                    className={`rounded-md border border-l-4 ${meta.borderClass} bg-card p-3`}
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
                    {anomaly.actual_value && (
                      <details className="group mt-2 pl-1">
                        <summary className="cursor-pointer list-none text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                          <ChevronRight className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90" />
                          Voir les références
                        </summary>
                        <div className="mt-1 text-xs text-muted-foreground whitespace-pre-wrap">
                          {anomaly.actual_value}
                        </div>
                      </details>
                    )}
                  </div>
                );
              })}

              {/* Grouped missing_payout sections */}
              {Array.from(missingPayoutByCanal.entries()).map(([canal, group]) => {
                const channelMeta = getChannelMeta(canal);
                const meta = getSeverityMeta(group[0].severity);
                return (
                  <details key={`mp-${canal}`} className={`group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
                    <summary className="cursor-pointer list-none p-3 flex items-center gap-2 text-sm font-medium">
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
                  <details key={`os-${canal}`} className={`group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
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
                  <details key={`dp-${method}`} className={`group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
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
                  <details key={`tva-${rateKey}`} className={`group rounded-md border border-l-4 ${meta.borderClass} bg-card`}>
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
                    key={`other-${i}`}
                    className={`rounded-md border border-l-4 ${meta.borderClass} bg-card p-3`}
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
                    {anomaly.actual_value && (
                      <details className="group mt-2 pl-1">
                        <summary className="cursor-pointer list-none text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                          <ChevronRight className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90" />
                          Voir les références
                        </summary>
                        <div className="mt-1 text-xs text-muted-foreground whitespace-pre-wrap">
                          {anomaly.actual_value}
                        </div>
                      </details>
                    )}
                  </div>
                );
              })}
            </>
          );
        })()}
      </div>
    </div>
  );
}
