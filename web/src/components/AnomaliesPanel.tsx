"use client";

import { useState, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { getChannelMeta } from "@/lib/channels";
import type { Anomaly } from "@/lib/types";

// --- Task 1: Constants ---

interface SeverityMeta {
  label: string;
  badgeClass: string;
  borderClass: string;
  order: number;
}

const SEVERITY_META: Record<string, SeverityMeta> = {
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

const ANOMALY_TYPE_LABELS: Record<string, string> = {
  tva_mismatch: "Incohérence TVA",
  orphan_sale: "Vente orpheline",
  amount_mismatch: "Écart de montant",
  balance_error: "Déséquilibre débit/crédit",
  missing_payout: "Reversement manquant",
  orphan_settlement: "Règlement orphelin",
  orphan_refund: "Remboursement orphelin",
  lettrage_511_unbalanced: "Lettrage 511 déséquilibré",
  payout_detail_mismatch: "Écart détail versement",
  payout_missing_details: "Détail versement manquant",
  orphan_payout_detail: "Détail versement orphelin",
  unknown_psp_detail: "PSP inconnu (détail)",
  mixed_psp_payout: "Versement multi-PSP",
};

function getTypeLabel(type: string): string {
  return ANOMALY_TYPE_LABELS[type] ?? type;
}

function getSeverityMeta(severity: string): SeverityMeta {
  return SEVERITY_META[severity] ?? SEVERITY_META.info;
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

      {/* Anomaly cards */}
      <div className="space-y-2">
        {sortedAnomalies.map((anomaly, i) => {
          const meta = getSeverityMeta(anomaly.severity);
          const channelMeta = getChannelMeta(anomaly.canal);
          return (
            <div
              key={i}
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
            </div>
          );
        })}
      </div>
    </div>
  );
}
