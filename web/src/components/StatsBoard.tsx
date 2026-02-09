"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { getChannelMeta } from "@/lib/channels";
import { formatCurrency } from "@/lib/format";
import { formatCount } from "@/lib/format";
import type { Summary, Entry, Anomaly } from "@/lib/types";

// --- Constants ---

const ENTRY_TYPE_LABELS: Record<string, string> = {
  sale: "Vente",
  refund: "Remboursement",
  settlement: "Règlement",
  commission: "Commission",
  payout: "Reversement",
  fee: "Frais",
};

interface SeverityMeta {
  label: string;
  badgeClass: string;
}

const SEVERITY_META: Record<string, SeverityMeta> = {
  error: {
    label: "Erreur(s)",
    badgeClass: "bg-red-100 text-red-800 border-red-300 dark:bg-red-900 dark:text-red-200 dark:border-red-700",
  },
  warning: {
    label: "Avertissement(s)",
    badgeClass: "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700",
  },
  info: {
    label: "Info(s)",
    badgeClass: "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-700",
  },
};

// --- Component ---

interface StatsBoardProps {
  summary: Summary;
  entries: Entry[];
  anomalies: Anomaly[];
}

/**
 * Dashboard showing key processing metrics: balance, transactions per channel,
 * entries by type, and anomaly counts by severity.
 */
export default function StatsBoard({ summary, entries, anomalies }: StatsBoardProps) {
  const isBalanced = Math.abs(summary.totaux.debit - summary.totaux.credit) < 0.01;
  const ecart = Math.abs(summary.totaux.debit - summary.totaux.credit);

  const totalTransactions = useMemo(
    () => Object.values(summary.transactions_par_canal).reduce((sum, n) => sum + n, 0),
    [summary.transactions_par_canal],
  );

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { error: 0, warning: 0, info: 0 };
    for (const a of anomalies) {
      counts[a.severity] = (counts[a.severity] ?? 0) + 1;
    }
    return counts;
  }, [anomalies]);

  return (
    <div className="space-y-6">
      {/* Section 1: Équilibre comptable */}
      <section>
        <h3 className="text-base font-semibold mb-2">Équilibre comptable</h3>
        <div
          className={`rounded-md border p-4 ${
            isBalanced
              ? "text-green-700 bg-green-50 border-green-300 dark:text-green-200 dark:bg-green-950 dark:border-green-700"
              : "text-red-700 bg-red-50 border-red-300 dark:text-red-200 dark:bg-red-950 dark:border-red-700"
          }`}
        >
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="font-semibold">
              {isBalanced ? "Équilibré" : "Déséquilibré"}
            </span>
            <div className="flex gap-4 text-sm">
              <span>Débit : {formatCurrency(summary.totaux.debit)} €</span>
              <span>Crédit : {formatCurrency(summary.totaux.credit)} €</span>
            </div>
          </div>
          {!isBalanced && (
            <div className="mt-1 text-sm">
              Écart : {formatCurrency(ecart)} €
            </div>
          )}
        </div>
      </section>

      {/* Section 2: Transactions par canal */}
      <section>
        <h3 className="text-base font-semibold mb-2">Transactions par canal</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th scope="col" className="text-left py-2 font-medium">Canal</th>
              <th scope="col" className="text-right py-2 font-medium">Transactions</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(summary.transactions_par_canal).map(([canal, count]) => {
              const meta = getChannelMeta(canal);
              return (
                <tr key={canal} className="border-b">
                  <th scope="row" className="text-left py-2 font-normal">
                    <Badge variant="outline" className={meta.badgeClass}>
                      {meta.label}
                    </Badge>
                  </th>
                  <td className="text-right py-2">{formatCount(count)}</td>
                </tr>
              );
            })}
            <tr className="border-t-2">
              <th scope="row" className="text-left py-2 font-semibold">Total</th>
              <td className="text-right py-2 font-semibold">{formatCount(totalTransactions)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* Section 3: Écritures générées */}
      <section>
        <h3 className="text-base font-semibold mb-2">Écritures générées</h3>
        <p className="text-sm mb-2">
          Total : <span className="font-semibold">{formatCount(entries.length)}</span>
        </p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th scope="col" className="text-left py-2 font-medium">Type</th>
              <th scope="col" className="text-right py-2 font-medium">Nombre</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(summary.ecritures_par_type).map(([type, count]) => (
              <tr key={type} className="border-b">
                <th scope="row" className="text-left py-2 font-normal">
                  {ENTRY_TYPE_LABELS[type] ?? type}
                </th>
                <td className="text-right py-2">{formatCount(count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Section 4: Anomalies */}
      <section>
        <h3 className="text-base font-semibold mb-2">Anomalies</h3>
        {anomalies.length === 0 ? (
          <div className="rounded-md border border-green-300 bg-green-50 p-4 text-sm text-green-700 dark:border-green-700 dark:bg-green-950 dark:text-green-200">
            Aucune anomalie
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {(["error", "warning", "info"] as const).map((severity) => {
              const count = severityCounts[severity];
              if (count === 0) return null;
              const meta = SEVERITY_META[severity];
              return (
                <Badge key={severity} variant="outline" className={meta.badgeClass}>
                  {count} {meta.label}
                </Badge>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
