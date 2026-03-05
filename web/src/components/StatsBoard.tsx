"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { getChannelMeta } from "@/lib/channels";
import { formatCurrency, formatCount, formatPercent } from "@/lib/format";
import { countVisualCardsBySeverity } from "@/lib/anomalyCardKey";
import { useNewDesign } from "@/hooks/useNewDesign";
import {
  CheckCircle,
  XCircle,
  BarChart3,
  Link2,
  FileText,
  AlertTriangle,
  TrendingUp,
  Package,
  Receipt,
  Globe,
  ChevronRight,
} from "lucide-react";
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

/** Canal background colors for TVA/Geo grouped tables */
const CANAL_BG: Record<string, string> = {
  shopify: "bg-[#F7FBF0] dark:bg-[#1a2410]",
  manomano: "bg-[#ECFEFF] dark:bg-[#0c1f21]",
  decathlon: "bg-[#E8F0FA] dark:bg-[#101828]",
  leroy_merlin: "bg-[#EBF5EC] dark:bg-[#0f1f10]",
};

/**
 * Badge class for VAT anomaly rate: green < 1%, orange 1-5%, red > 5%.
 */
function getVatAnomalyRateBadgeClass(rate: number): string {
  if (rate < 1) {
    return "bg-green-100 text-green-800 border-green-300 dark:bg-green-900 dark:text-green-200 dark:border-green-700";
  }
  if (rate <= 5) {
    return "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700";
  }
  return "bg-red-100 text-red-800 border-red-300 dark:bg-red-900 dark:text-red-200 dark:border-red-700";
}

/**
 * Badge class for refund rate: green < 5%, orange 5-10%, red > 10%.
 */
function getRefundRateBadgeClass(rate: number): string {
  if (rate < 5) {
    return "bg-green-100 text-green-800 border-green-300 dark:bg-green-900 dark:text-green-200 dark:border-green-700";
  }
  if (rate <= 10) {
    return "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700";
  }
  return "bg-red-100 text-red-800 border-red-300 dark:bg-red-900 dark:text-red-200 dark:border-red-700";
}

/**
 * Badge class for rapprochement rate: green >= 98%, orange 90-98%, red < 90%.
 */
function getRapprochementBadgeClass(rate: number): string {
  if (rate >= 98) {
    return "bg-green-100 text-green-800 border-green-300 dark:bg-green-900 dark:text-green-200 dark:border-green-700";
  }
  if (rate >= 90) {
    return "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700";
  }
  return "bg-red-100 text-red-800 border-red-300 dark:bg-red-900 dark:text-red-200 dark:border-red-700";
}

// --- V2 style helpers ---

/** V2 section card: rounded-xl, no internal padding (rows handle their own) */
const v2Card = "rounded-xl bg-card border border-border overflow-hidden mb-8";
/** V2 title row inside card */
const v2TitleRow = "flex items-center gap-2 px-5 py-3.5 font-semibold text-sm text-foreground";
/** V2 table header row */
const v2HeaderRow = "bg-[#F9FAFB] dark:bg-muted text-[11px] font-semibold uppercase tracking-wide text-muted-foreground border-b border-border";
/** V2 table header cell */
const v2HeaderCell = "px-5 py-2.5";
/** V2 data row base */
const v2DataRow = "text-sm border-b border-border";
/** V2 data cell */
const v2DataCell = "px-5 py-2.5";
/** V2 total row */
const v2TotalRow = "text-sm font-semibold bg-[#F3F4F6] dark:bg-muted border-t-2 border-border";
/** V2 total cell */
const v2TotalCell = "px-5 py-3";

function v2DataRowAlt(index: number): string {
  return `${v2DataRow} ${index % 2 === 1 ? "bg-[#FAFAFA] dark:bg-muted/30" : ""}`;
}

// --- Component ---

interface StatsBoardProps {
  summary: Summary;
  entries: Entry[];
  anomalies: Anomaly[];
  htTtcMode: "ht" | "ttc";
  onHtTtcModeChange: (mode: "ht" | "ttc") => void;
  tolerance?: number;
}

/**
 * Dashboard showing key processing metrics: balance, transactions per channel,
 * entries by type, and anomaly counts by severity.
 */
export default function StatsBoard({ summary, entries, anomalies, htTtcMode, onHtTtcModeChange, tolerance = 0.01 }: StatsBoardProps) {
  const isV2 = useNewDesign();
  const isHtMode = htTtcMode === "ht";
  const isBalanced = Math.abs(summary.totaux.debit - summary.totaux.credit) < tolerance;
  const ecart = Math.abs(summary.totaux.debit - summary.totaux.credit);

  const totalTransactions = useMemo(
    () => Object.values(summary.transactions_par_canal).reduce((sum, n) => sum + n, 0),
    [summary.transactions_par_canal],
  );

  const severityCounts = useMemo(() => {
    return countVisualCardsBySeverity(anomalies);
  }, [anomalies]);

  const vatAnomalyStats = useMemo(() => {
    const amountMismatch = anomalies.filter((a) => a.type === "tva_amount_mismatch");
    const rateMismatch = anomalies.filter((a) => a.type === "tva_mismatch");
    const total = totalTransactions || 0;

    const amountCount = amountMismatch.length;
    const rateCount = rateMismatch.length;

    const amountRate = total > 0 ? Math.round((amountCount / total) * 1000) / 10 : 0;
    const rateRate = total > 0 ? Math.round((rateCount / total) * 1000) / 10 : 0;

    let rateMismatchTotal = 0;
    for (const a of rateMismatch) {
      if (a.actual_value) {
        const val = parseFloat(a.actual_value);
        if (!isNaN(val)) rateMismatchTotal += val;
      }
    }
    rateMismatchTotal = Math.round(rateMismatchTotal * 100) / 100;

    return { amountCount, rateCount, amountRate, rateRate, rateMismatchTotal };
  }, [anomalies, totalTransactions]);

  const hasKpis = !!summary.ca_par_canal;

  const kpiChannels = useMemo(
    () => (hasKpis ? Object.keys(summary.ca_par_canal) : []),
    [hasKpis, summary.ca_par_canal],
  );

  const kpiTotals = useMemo(() => {
    if (!hasKpis) return { caTtc: 0, caHt: 0, rembTtc: 0, rembHt: 0, commTtc: 0, commHt: 0, net: 0, taux: 0, tauxComm: 0 };
    const caTtc = kpiChannels.reduce((s, c) => s + summary.ca_par_canal[c].ttc, 0);
    const caHt = kpiChannels.reduce((s, c) => s + summary.ca_par_canal[c].ht, 0);
    const rembTtc = kpiChannels.reduce((s, c) => s + summary.remboursements_par_canal[c].ttc, 0);
    const rembHt = kpiChannels.reduce((s, c) => s + summary.remboursements_par_canal[c].ht, 0);
    const commTtc = kpiChannels.reduce((s, c) => s + summary.commissions_par_canal[c].ttc, 0);
    const commHt = kpiChannels.reduce((s, c) => s + summary.commissions_par_canal[c].ht, 0);
    const net = isHtMode
      ? kpiChannels.reduce((s, c) => s + (summary.net_vendeur_ht_par_canal?.[c] ?? 0), 0)
      : kpiChannels.reduce((s, c) => s + summary.net_vendeur_par_canal[c], 0);
    const taux = caTtc > 0 ? Math.round(rembTtc / caTtc * 1000) / 10 : 0;
    const tauxComm = caHt > 0 ? Math.round(commHt / caHt * 1000) / 10 : 0;
    return { caTtc, caHt, rembTtc, rembHt, commTtc, commHt, net, taux, tauxComm };
  }, [hasKpis, kpiChannels, summary, isHtMode]);

  // --- Legacy (V1) style helpers ---
  const sectionCard = isV2 ? "" : "";
  const sectionTitle = isV2 ? "" : "text-base font-semibold mb-2";
  const tableRowAlt = isV2 ? "" : "border-b";

  // =====================================================================
  // V2 rendering
  // =====================================================================
  if (isV2) {
    return (
      <div className="space-y-2">
        {/* ── HT/TTC Toggle ── */}
        {hasKpis && (
          <div className="flex items-center justify-end mb-4">
            <div className="inline-flex rounded-lg border border-border overflow-hidden" role="group" aria-label="Affichage TTC ou HT">
              <button
                type="button"
                onClick={() => onHtTtcModeChange("ht")}
                className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                  isHtMode
                    ? "bg-teal-600 text-white"
                    : "bg-background text-muted-foreground hover:bg-muted"
                }`}
              >
                HT
              </button>
              <button
                type="button"
                onClick={() => onHtTtcModeChange("ttc")}
                className={`px-4 py-1.5 text-sm font-medium border-l border-border transition-colors ${
                  !isHtMode
                    ? "bg-teal-600 text-white"
                    : "bg-background text-muted-foreground hover:bg-muted"
                }`}
              >
                TTC
              </button>
            </div>
          </div>
        )}

        {/* ── Balance Card ── */}
        <div
          className={`flex items-center gap-6 rounded-xl p-4 px-5 mb-8 border ${
            isBalanced
              ? "border-[#B5E8C4] bg-green-50 dark:border-green-700 dark:bg-green-950"
              : "border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-950"
          }`}
        >
          {isBalanced ? (
            <CheckCircle className="h-5 w-5 shrink-0 text-green-600 dark:text-green-400" />
          ) : (
            <XCircle className="h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />
          )}
          <span className={`text-sm font-semibold ${isBalanced ? "text-[#065F46] dark:text-green-300" : "text-red-800 dark:text-red-300"}`}>
            {isBalanced ? "Équilibre comptable vérifié" : "Déséquilibre comptable"}
          </span>
          <span className="flex-1" />
          <div className={`flex items-center gap-6 text-sm ${isBalanced ? "text-[#065F46] dark:text-green-300" : "text-red-800 dark:text-red-300"}`}>
            <span>Débit : <span className="font-semibold">{formatCurrency(summary.totaux.debit)} €</span></span>
            <span>Crédit : <span className="font-semibold">{formatCurrency(summary.totaux.credit)} €</span></span>
            {!isBalanced && (
              <span>Écart : <span className="font-semibold">{formatCurrency(ecart)} €</span></span>
            )}
          </div>
        </div>

        {/* ── Synthèse des transactions ── */}
        <section className={v2Card}>
          <div className={v2TitleRow}>
            <BarChart3 className="h-4 w-4 text-primary" />
            <span>Synthèse des transactions</span>
          </div>
          <table className="w-full">
            <thead>
              <tr className={v2HeaderRow}>
                <th scope="col" className={`text-left ${v2HeaderCell}`}>Canal</th>
                <th scope="col" className={`text-right ${v2HeaderCell}`}>Transactions</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.transactions_par_canal).map(([canal, count], idx) => {
                const meta = getChannelMeta(canal);
                return (
                  <tr key={canal} className={v2DataRowAlt(idx)}>
                    <td className={`text-left ${v2DataCell}`}>
                      <Badge variant="outline" className={meta.badgeClass}>
                        {meta.label}
                      </Badge>
                    </td>
                    <td className={`text-right ${v2DataCell}`}>{formatCount(count)}</td>
                  </tr>
                );
              })}
              <tr className={v2TotalRow}>
                <td className={`text-left font-semibold ${v2TotalCell}`}>Total</td>
                <td className={`text-right font-semibold ${v2TotalCell}`}>{formatCount(totalTransactions)}</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* ── Taux de rapprochement ── */}
        {summary.taux_rapprochement_par_canal && summary.ventes_par_canal && (() => {
          const rapChannels = Object.keys(summary.ventes_par_canal);
          const totalVentes = rapChannels.reduce((s, c) => s + summary.ventes_par_canal[c], 0);
          const totalMatched = rapChannels.reduce(
            (s, c) => s + Math.round(summary.ventes_par_canal[c] * summary.taux_rapprochement_par_canal[c] / 100),
            0,
          );
          const totalRate = totalVentes > 0 ? Math.round(totalMatched / totalVentes * 1000) / 10 : 0;
          const allPerfect = rapChannels.every((c) => summary.taux_rapprochement_par_canal[c] === 100);

          return (
            <section className={v2Card}>
              <div className={v2TitleRow}>
                <Link2 className="h-4 w-4 text-primary" />
                <span>Taux de rapprochement</span>
              </div>
              <table className="w-full">
                <thead>
                  <tr className={v2HeaderRow}>
                    <th scope="col" className={`text-left ${v2HeaderCell}`}>Canal</th>
                    <th scope="col" className={`text-right ${v2HeaderCell}`}>Ventes</th>
                    <th scope="col" className={`text-right ${v2HeaderCell}`}>Rapprochées</th>
                    <th scope="col" className={`text-right ${v2HeaderCell}`}>Taux</th>
                  </tr>
                </thead>
                <tbody>
                  {rapChannels.map((canal, idx) => {
                    const meta = getChannelMeta(canal);
                    const ventes = summary.ventes_par_canal[canal];
                    const taux = summary.taux_rapprochement_par_canal[canal];
                    const matched = Math.round(ventes * taux / 100);
                    return (
                      <tr key={canal} className={v2DataRowAlt(idx)}>
                        <td className={`text-left ${v2DataCell}`}>
                          <Badge variant="outline" className={meta.badgeClass}>
                            {meta.label}
                          </Badge>
                        </td>
                        <td className={`text-right ${v2DataCell}`}>{formatCount(ventes)}</td>
                        <td className={`text-right ${v2DataCell}`}>{formatCount(matched)}</td>
                        <td className={`text-right ${v2DataCell}`}>
                          <Badge variant="outline" className={getRapprochementBadgeClass(taux)}>
                            {formatPercent(taux)}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
                  <tr className={v2TotalRow}>
                    <td className={`text-left font-semibold ${v2TotalCell}`}>Total</td>
                    <td className={`text-right font-semibold ${v2TotalCell}`}>{formatCount(totalVentes)}</td>
                    <td className={`text-right font-semibold ${v2TotalCell}`}>{formatCount(totalMatched)}</td>
                    <td className={`text-right ${v2TotalCell}`}>
                      <Badge variant="outline" className={getRapprochementBadgeClass(totalRate)}>
                        {formatPercent(totalRate)}
                      </Badge>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p className="text-sm px-5 py-3 text-muted-foreground border-t border-border">
                {allPerfect
                  ? "\u2713 Toutes les transactions ont été rapprochées avec succès."
                  : "\u26A0 Certains canaux présentent des transactions non rapprochées."}
              </p>
            </section>
          );
        })()}

        {/* ── Écritures générées ── */}
        <section className={v2Card}>
          <div className={v2TitleRow}>
            <FileText className="h-4 w-4 text-primary" />
            <span>Écritures générées</span>
            <span className="ml-auto text-muted-foreground text-xs font-normal">
              Total : {formatCount(entries.length)}
            </span>
          </div>
          <table className="w-full">
            <thead>
              <tr className={v2HeaderRow}>
                <th scope="col" className={`text-left ${v2HeaderCell}`}>Type</th>
                <th scope="col" className={`text-right ${v2HeaderCell}`}>Nombre</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.ecritures_par_type).map(([type, count], idx) => (
                <tr key={type} className={v2DataRowAlt(idx)}>
                  <td className={`text-left ${v2DataCell}`}>
                    {ENTRY_TYPE_LABELS[type] ?? type}
                  </td>
                  <td className={`text-right ${v2DataCell}`}>{formatCount(count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* ── Anomalies détectées ── */}
        <section className={v2Card}>
          <div className={v2TitleRow}>
            <AlertTriangle className="h-4 w-4 text-primary" />
            <span>Anomalies détectées</span>
          </div>
          <div className="px-5 py-3 border-t border-border">
            {anomalies.length === 0 ? (
              <div className="rounded-md border border-green-300 bg-green-50 p-4 text-sm text-green-700 dark:border-green-700 dark:bg-green-950 dark:text-green-200">
                Aucune anomalie
              </div>
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  {(["info", "warning", "error"] as const).map((severity) => {
                    const count = severityCounts[severity];
                    if (count === 0) return null;
                    const meta = SEVERITY_META[severity];
                    return (
                      <Badge key={severity} variant="outline" className={meta.badgeClass}>
                        {count} {severity === "error" ? (count > 1 ? "Erreurs" : "Erreur") : severity === "warning" ? (count > 1 ? "Avertissements" : "Avertissement") : (count > 1 ? "Infos" : "Info")}
                      </Badge>
                    );
                  })}
                </div>
                {(vatAnomalyStats.amountCount > 0 || vatAnomalyStats.rateCount > 0) && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {vatAnomalyStats.amountCount > 0 && (
                      <Badge variant="outline" className={getVatAnomalyRateBadgeClass(vatAnomalyStats.amountRate)}>
                        Montant TVA incorrect : {formatPercent(vatAnomalyStats.amountRate)}
                      </Badge>
                    )}
                    {vatAnomalyStats.rateCount > 0 && (
                      vatAnomalyStats.rateMismatchTotal === 0 ? (
                        <Badge variant="outline" className={getVatAnomalyRateBadgeClass(vatAnomalyStats.rateRate)}>
                          Taux TVA incohérent : {vatAnomalyStats.rateCount} {vatAnomalyStats.rateCount > 1 ? "factures" : "facture"} — 0,00 € d&apos;impact
                        </Badge>
                      ) : (
                        <Badge variant="outline" className={getVatAnomalyRateBadgeClass(vatAnomalyStats.rateRate)}>
                          Taux TVA incohérent : {formatPercent(vatAnomalyStats.rateRate)} — {formatCurrency(vatAnomalyStats.rateMismatchTotal)} €
                        </Badge>
                      )
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </section>

        {/* ====================================================== */}
        {/* Synthèse financière par canal                           */}
        {/* ====================================================== */}

        {hasKpis && (<>

        <section className={v2Card}>
          <div className={v2TitleRow}>
            <TrendingUp className="h-4 w-4 text-primary" />
            <span>Résultat financier par canal</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={v2HeaderRow}>
                  <th scope="col" className={`text-left ${v2HeaderCell}`}>Canal</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>{isHtMode ? "CA HT" : "CA TTC"}</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>{isHtMode ? "Remb. HT" : "Remb. TTC"}</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>Taux remb.</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>{isHtMode ? "Commissions HT" : "Commissions TTC"}</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>{isHtMode ? "Taux comm." : "Net vendeur"}</th>
                </tr>
              </thead>
              <tbody>
                {kpiChannels.map((canal, idx) => {
                  const meta = getChannelMeta(canal);
                  const taux = summary.taux_remboursement_par_canal[canal];
                  const commRate = summary.ca_par_canal[canal].ht > 0
                    ? Math.round(summary.commissions_par_canal[canal].ht / summary.ca_par_canal[canal].ht * 1000) / 10
                    : 0;
                  return (
                    <tr key={canal} className={v2DataRowAlt(idx)}>
                      <td className={`text-left align-top ${v2DataCell}`}>
                        <details className="group">
                          <summary className="cursor-pointer list-none flex items-center gap-1">
                            <ChevronRight className="h-4 w-4 transition-transform group-open:rotate-90" />
                            <Badge variant="outline" className={meta.badgeClass}>
                              {meta.label}
                            </Badge>
                          </summary>
                          <div className="mt-2 text-xs text-muted-foreground space-y-1 pl-1">
                            {isHtMode ? (
                              <>
                                <div>CA TTC : {formatCurrency(summary.ca_par_canal[canal].ttc)} €</div>
                                <div>TVA collectée : {formatCurrency(summary.tva_collectee_par_canal[canal])} €</div>
                                <div>Net vendeur HT : {formatCurrency(summary.net_vendeur_ht_par_canal?.[canal] ?? 0)} €</div>
                              </>
                            ) : (
                              <>
                                <div>CA HT : {formatCurrency(summary.ca_par_canal[canal].ht)} €</div>
                                <div>TVA collectée : {formatCurrency(summary.tva_collectee_par_canal[canal])} €</div>
                                <div>Commission HT : {formatCurrency(summary.commissions_par_canal[canal].ht)} €</div>
                                <div>Remboursement HT : {formatCurrency(summary.remboursements_par_canal[canal].ht)} €</div>
                              </>
                            )}
                          </div>
                        </details>
                      </td>
                      <td className={`text-right align-top ${v2DataCell}`}>
                        {formatCurrency(isHtMode ? summary.ca_par_canal[canal].ht : summary.ca_par_canal[canal].ttc)} €
                      </td>
                      <td className={`text-right align-top ${v2DataCell}`}>
                        {formatCurrency(isHtMode ? summary.remboursements_par_canal[canal].ht : summary.remboursements_par_canal[canal].ttc)} €
                      </td>
                      <td className={`text-right align-top ${v2DataCell}`}>
                        <Badge variant="outline" className={getRefundRateBadgeClass(taux)}>
                          {formatPercent(taux)}
                        </Badge>
                      </td>
                      <td className={`text-right align-top ${v2DataCell}`}>
                        {formatCurrency(isHtMode ? summary.commissions_par_canal[canal].ht : summary.commissions_par_canal[canal].ttc)} €
                      </td>
                      {isHtMode ? (
                        <td className={`text-right align-top font-semibold ${v2DataCell}`}>
                          {formatPercent(commRate)}
                        </td>
                      ) : (
                        <td className={`text-right align-top font-semibold text-emerald-700 dark:text-emerald-300 ${v2DataCell}`}>
                          {formatCurrency(summary.net_vendeur_par_canal[canal])} €
                        </td>
                      )}
                    </tr>
                  );
                })}
                <tr className={v2TotalRow}>
                  <td className={`text-left font-semibold ${v2TotalCell}`}>Total</td>
                  <td className={`text-right font-semibold ${v2TotalCell}`}>{formatCurrency(isHtMode ? kpiTotals.caHt : kpiTotals.caTtc)} €</td>
                  <td className={`text-right font-semibold ${v2TotalCell}`}>{formatCurrency(isHtMode ? kpiTotals.rembHt : kpiTotals.rembTtc)} €</td>
                  <td className={`text-right ${v2TotalCell}`}>
                    <Badge variant="outline" className={getRefundRateBadgeClass(kpiTotals.taux)}>
                      {formatPercent(kpiTotals.taux)}
                    </Badge>
                  </td>
                  <td className={`text-right font-semibold ${v2TotalCell}`}>{formatCurrency(isHtMode ? kpiTotals.commHt : kpiTotals.commTtc)} €</td>
                  {isHtMode ? (
                    <td className={`text-right font-semibold ${v2TotalCell}`}>
                      {formatPercent(kpiTotals.tauxComm)}
                    </td>
                  ) : (
                    <td className={`text-right font-semibold text-emerald-700 dark:text-emerald-300 ${v2TotalCell}`}>
                      {formatCurrency(kpiTotals.net)} €
                    </td>
                  )}
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Ventilation produits ── */}
        <section className={v2Card}>
          <div className={v2TitleRow}>
            <Package className="h-4 w-4 text-primary" />
            <span>Ventilation du CA : Produits / Frais de port</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={v2HeaderRow}>
                  <th scope="col" className={`text-left ${v2HeaderCell}`}>Canal</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>CA Produits HT</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>CA Frais de port HT</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>CA Total HT</th>
                </tr>
              </thead>
              <tbody>
                {kpiChannels.map((canal, idx) => {
                  const meta = getChannelMeta(canal);
                  const v = summary.ventilation_ca_par_canal[canal];
                  return (
                    <tr key={canal} className={v2DataRowAlt(idx)}>
                      <td className={`text-left ${v2DataCell}`}>
                        <Badge variant="outline" className={meta.badgeClass}>
                          {meta.label}
                        </Badge>
                      </td>
                      <td className={`text-right ${v2DataCell}`}>{formatCurrency(v.produits_ht)} €</td>
                      <td className={`text-right ${v2DataCell}`}>{formatCurrency(v.port_ht)} €</td>
                      <td className={`text-right font-semibold ${v2DataCell}`}>{formatCurrency(v.total_ht)} €</td>
                    </tr>
                  );
                })}
                <tr className={v2TotalRow}>
                  <td className={`text-left font-semibold ${v2TotalCell}`}>Total</td>
                  <td className={`text-right font-semibold ${v2TotalCell}`}>
                    {formatCurrency(kpiChannels.reduce((s, c) => s + summary.ventilation_ca_par_canal[c].produits_ht, 0))} €
                  </td>
                  <td className={`text-right font-semibold ${v2TotalCell}`}>
                    {formatCurrency(kpiChannels.reduce((s, c) => s + summary.ventilation_ca_par_canal[c].port_ht, 0))} €
                  </td>
                  <td className={`text-right font-semibold ${v2TotalCell}`}>
                    {formatCurrency(kpiTotals.caHt)} €
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Fiscalité TVA ── */}
        <section className={v2Card}>
          <div className={v2TitleRow}>
            <Receipt className="h-4 w-4 text-primary" />
            <span>Fiscalité TVA</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={v2HeaderRow}>
                  <th scope="col" className={`text-left ${v2HeaderCell}`}>Canal</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>Montant TVA</th>
                </tr>
              </thead>
              <tbody>
                {kpiChannels.map((canal) => {
                  const meta = getChannelMeta(canal);
                  const tvaPays = summary.tva_par_pays_par_canal[canal];
                  const canalBg = CANAL_BG[canal.toLowerCase()] ?? "";
                  return (
                    <tr key={canal} className={`${v2DataRow} ${canalBg}`}>
                      <td className={`text-left align-top ${v2DataCell}`}>
                        <details className="group">
                          <summary className="cursor-pointer list-none flex items-center gap-1">
                            <ChevronRight className="h-4 w-4 transition-transform group-open:rotate-90" />
                            <Badge variant="outline" className={meta.badgeClass}>
                              {meta.label}
                            </Badge>
                          </summary>
                          {tvaPays && (
                            <div className="overflow-x-auto mt-2">
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="border-b border-border">
                                    <th scope="col" className="text-left py-1.5 px-2 font-medium text-muted-foreground">Pays</th>
                                    <th scope="col" className="text-right py-1.5 px-2 font-medium text-muted-foreground">Taux TVA</th>
                                    <th scope="col" className="text-right py-1.5 px-2 font-medium text-muted-foreground">Montant TVA</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {Object.entries(tvaPays).map(([pays, rows]) =>
                                    rows.map((row, i) => (
                                      <tr key={`${pays}-${i}`} className="border-b border-border/50">
                                        <td className={`text-left py-1.5 px-2 ${i > 0 ? "text-muted-foreground italic" : ""}`}>
                                          {i === 0 ? pays : pays}
                                        </td>
                                        <td className="text-right py-1.5 px-2">{formatPercent(row.taux)}</td>
                                        <td className="text-right py-1.5 px-2">{formatCurrency(row.montant)} €</td>
                                      </tr>
                                    ))
                                  )}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </details>
                      </td>
                      <td className={`text-right align-top ${v2DataCell}`}>{formatCurrency(summary.tva_collectee_par_canal[canal])} €</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Répartition géographique ── */}
        <section className={v2Card}>
          <div className={v2TitleRow}>
            <Globe className="h-4 w-4 text-primary" />
            <span>Répartition géographique</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className={v2HeaderRow}>
                  <th scope="col" className={`text-left ${v2HeaderCell}`}>Pays</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>Transactions</th>
                  <th scope="col" className={`text-right ${v2HeaderCell}`}>CA HT</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary.repartition_geo_globale).map(([pays, data], idx) => (
                  <tr key={pays} className={v2DataRowAlt(idx)}>
                    <td className={`text-left ${v2DataCell}`}>{pays}</td>
                    <td className={`text-right ${v2DataCell}`}>{formatCount(data.count)}</td>
                    <td className={`text-right ${v2DataCell}`}>{formatCurrency(data.ca_ht)} €</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Per-canal breakdown */}
          {Object.entries(summary.repartition_geo_par_canal).map(([canal, countries]) => {
            const meta = getChannelMeta(canal);
            const canalBg = CANAL_BG[canal.toLowerCase()] ?? "";
            return (
              <div key={canal} className={`border-t border-border ${canalBg}`}>
                <details className="group">
                  <summary className={`cursor-pointer ${v2DataCell} py-3 text-sm font-medium flex items-center gap-2`}>
                    <ChevronRight className="h-4 w-4 transition-transform group-open:rotate-90" />
                    <Badge variant="outline" className={meta.badgeClass}>
                      {meta.label}
                    </Badge>
                  </summary>
                  <div className="overflow-x-auto px-5 pb-3">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border">
                          <th scope="col" className="text-left py-1.5 font-medium text-muted-foreground text-xs">Pays</th>
                          <th scope="col" className="text-right py-1.5 font-medium text-muted-foreground text-xs">Transactions</th>
                          <th scope="col" className="text-right py-1.5 font-medium text-muted-foreground text-xs">CA HT</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(countries).map(([pays, data]) => (
                          <tr key={pays} className="border-b border-border/50">
                            <td className="text-left py-1.5">{pays}</td>
                            <td className="text-right py-1.5">{formatCount(data.count)}</td>
                            <td className="text-right py-1.5">{formatCurrency(data.ca_ht)} €</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </div>
            );
          })}
        </section>

        </>)}
      </div>
    );
  }

  // =====================================================================
  // V1 (legacy) rendering — unchanged
  // =====================================================================
  return (
    <div className="space-y-6">
      {/* Section 1: Equilibre comptable */}
      <section className={sectionCard}>
        <h3 className={sectionTitle}>Équilibre comptable</h3>
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
      <section className={sectionCard}>
        <h3 className={sectionTitle}>Transactions par canal</h3>
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
                <tr key={canal} className={tableRowAlt}>
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

      {/* Section 2b: Taux de rapprochement */}
      {summary.taux_rapprochement_par_canal && summary.ventes_par_canal && (() => {
        const rapChannels = Object.keys(summary.ventes_par_canal);
        const totalVentes = rapChannels.reduce((s, c) => s + summary.ventes_par_canal[c], 0);
        const totalMatched = rapChannels.reduce(
          (s, c) => s + Math.round(summary.ventes_par_canal[c] * summary.taux_rapprochement_par_canal[c] / 100),
          0,
        );
        const totalRate = totalVentes > 0 ? Math.round(totalMatched / totalVentes * 1000) / 10 : 0;
        const allPerfect = rapChannels.every((c) => summary.taux_rapprochement_par_canal[c] === 100);

        return (
          <section className={sectionCard}>
            <h3 className={sectionTitle}>Taux de rapprochement</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th scope="col" className="text-left py-2 font-medium">Canal</th>
                  <th scope="col" className="text-right py-2 font-medium">Ventes</th>
                  <th scope="col" className="text-right py-2 font-medium">Rapprochées</th>
                  <th scope="col" className="text-right py-2 font-medium">Taux</th>
                </tr>
              </thead>
              <tbody>
                {rapChannels.map((canal) => {
                  const meta = getChannelMeta(canal);
                  const ventes = summary.ventes_par_canal[canal];
                  const taux = summary.taux_rapprochement_par_canal[canal];
                  const matched = Math.round(ventes * taux / 100);
                  return (
                    <tr key={canal} className={tableRowAlt}>
                      <th scope="row" className="text-left py-2 font-normal">
                        <Badge variant="outline" className={meta.badgeClass}>
                          {meta.label}
                        </Badge>
                      </th>
                      <td className="text-right py-2">{formatCount(ventes)}</td>
                      <td className="text-right py-2">{formatCount(matched)}</td>
                      <td className="text-right py-2">
                        <Badge variant="outline" className={getRapprochementBadgeClass(taux)}>
                          {formatPercent(taux)}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
                <tr className="border-t-2">
                  <th scope="row" className="text-left py-2 font-semibold">Total</th>
                  <td className="text-right py-2 font-semibold">{formatCount(totalVentes)}</td>
                  <td className="text-right py-2 font-semibold">{formatCount(totalMatched)}</td>
                  <td className="text-right py-2">
                    <Badge variant="outline" className={getRapprochementBadgeClass(totalRate)}>
                      {formatPercent(totalRate)}
                    </Badge>
                  </td>
                </tr>
              </tbody>
            </table>
            <p className="text-sm mt-2 text-muted-foreground">
              {allPerfect
                ? "\u2713 Toutes les transactions ont été rapprochées avec succès."
                : "\u26A0 Certains canaux présentent des transactions non rapprochées."}
            </p>
          </section>
        );
      })()}

      {/* Section 3: Écritures générées */}
      <section className={sectionCard}>
        <h3 className={sectionTitle}>Écritures générées</h3>
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
              <tr key={type} className={tableRowAlt}>
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
      <section className={sectionCard}>
        <h3 className={sectionTitle}>Anomalies</h3>
        {anomalies.length === 0 ? (
          <div className="rounded-md border border-green-300 bg-green-50 p-4 text-sm text-green-700 dark:border-green-700 dark:bg-green-950 dark:text-green-200">
            Aucune anomalie
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {(["info", "warning", "error"] as const).map((severity) => {
                const count = severityCounts[severity];
                if (count === 0) return null;
                const meta = SEVERITY_META[severity];
                return (
                  <Badge key={severity} variant="outline" className={meta.badgeClass}>
                    {count} {severity === "error" ? (count > 1 ? "Erreurs" : "Erreur") : severity === "warning" ? (count > 1 ? "Avertissements" : "Avertissement") : (count > 1 ? "Infos" : "Info")}
                  </Badge>
                );
              })}
            </div>
            {(vatAnomalyStats.amountCount > 0 || vatAnomalyStats.rateCount > 0) && (
              <div className="flex flex-wrap gap-2 mt-3">
                {vatAnomalyStats.amountCount > 0 && (
                  <Badge variant="outline" className={getVatAnomalyRateBadgeClass(vatAnomalyStats.amountRate)}>
                    Montant TVA incorrect : {formatPercent(vatAnomalyStats.amountRate)}
                  </Badge>
                )}
                {vatAnomalyStats.rateCount > 0 && (
                  vatAnomalyStats.rateMismatchTotal === 0 ? (
                    <Badge variant="outline" className={getVatAnomalyRateBadgeClass(vatAnomalyStats.rateRate)}>
                      Taux TVA incohérent : {vatAnomalyStats.rateCount} {vatAnomalyStats.rateCount > 1 ? "factures" : "facture"} — 0,00 € d&apos;impact
                    </Badge>
                  ) : (
                    <Badge variant="outline" className={getVatAnomalyRateBadgeClass(vatAnomalyStats.rateRate)}>
                      Taux TVA incohérent : {formatPercent(vatAnomalyStats.rateRate)} — {formatCurrency(vatAnomalyStats.rateMismatchTotal)} €
                    </Badge>
                  )
                )}
              </div>
            )}
          </>
        )}
      </section>

      {/* ====================================================== */}
      {/* Synthèse financière par canal (AC15-19)                 */}
      {/* ====================================================== */}

      {hasKpis && (<>

      <div className="flex items-center justify-between mt-8">
        <h2 className="text-lg font-bold">Synthèse financière par canal</h2>
        <div className="inline-flex rounded-md border" role="group" aria-label="Affichage TTC ou HT">
          <button
            type="button"
            onClick={() => onHtTtcModeChange("ttc")}
            className={`px-3 py-1 text-sm font-medium rounded-l-md transition-colors ${
              !isHtMode
                ? "bg-foreground text-background"
                : "bg-background text-muted-foreground hover:bg-muted"
            }`}
          >
            TTC
          </button>
          <button
            type="button"
            onClick={() => onHtTtcModeChange("ht")}
            className={`px-3 py-1 text-sm font-medium rounded-r-md border-l transition-colors ${
              isHtMode
                ? "bg-foreground text-background"
                : "bg-background text-muted-foreground hover:bg-muted"
            }`}
          >
            HT
          </button>
        </div>
      </div>

      <section className={sectionCard}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th scope="col" className="text-left py-2 font-medium">Canal</th>
                <th scope="col" className="text-right py-2 font-medium">{isHtMode ? "CA HT" : "CA TTC"}</th>
                <th scope="col" className="text-right py-2 font-medium">{isHtMode ? "Remb. HT" : "Remb. TTC"}</th>
                <th scope="col" className="text-right py-2 font-medium">Taux remb.</th>
                <th scope="col" className="text-right py-2 font-medium">{isHtMode ? "Commissions HT" : "Commissions TTC"}</th>
                <th scope="col" className="text-right py-2 font-medium">{isHtMode ? "Taux comm." : "Net vendeur"}</th>
              </tr>
            </thead>
            <tbody>
              {kpiChannels.map((canal) => {
                const meta = getChannelMeta(canal);
                const taux = summary.taux_remboursement_par_canal[canal];
                const commRate = summary.ca_par_canal[canal].ht > 0
                  ? Math.round(summary.commissions_par_canal[canal].ht / summary.ca_par_canal[canal].ht * 1000) / 10
                  : 0;
                return (
                  <tr key={canal} className={tableRowAlt}>
                    <th scope="row" className="text-left py-2 font-normal align-top">
                      <details>
                        <summary className="cursor-pointer list-none">
                          <Badge variant="outline" className={meta.badgeClass}>
                            {meta.label}
                          </Badge>
                        </summary>
                        <div className="mt-2 text-xs text-muted-foreground space-y-1 pl-1">
                          {isHtMode ? (
                            <>
                              <div>CA TTC : {formatCurrency(summary.ca_par_canal[canal].ttc)} €</div>
                              <div>TVA collectée : {formatCurrency(summary.tva_collectee_par_canal[canal])} €</div>
                              <div>Net vendeur HT : {formatCurrency(summary.net_vendeur_ht_par_canal?.[canal] ?? 0)} €</div>
                            </>
                          ) : (
                            <>
                              <div>CA HT : {formatCurrency(summary.ca_par_canal[canal].ht)} €</div>
                              <div>TVA collectée : {formatCurrency(summary.tva_collectee_par_canal[canal])} €</div>
                              <div>Commission HT : {formatCurrency(summary.commissions_par_canal[canal].ht)} €</div>
                              <div>Remboursement HT : {formatCurrency(summary.remboursements_par_canal[canal].ht)} €</div>
                            </>
                          )}
                        </div>
                      </details>
                    </th>
                    <td className="text-right py-2 align-top">
                      {formatCurrency(isHtMode ? summary.ca_par_canal[canal].ht : summary.ca_par_canal[canal].ttc)} €
                    </td>
                    <td className="text-right py-2 align-top">
                      {formatCurrency(isHtMode ? summary.remboursements_par_canal[canal].ht : summary.remboursements_par_canal[canal].ttc)} €
                    </td>
                    <td className="text-right py-2 align-top">
                      <Badge variant="outline" className={getRefundRateBadgeClass(taux)}>
                        {formatPercent(taux)}
                      </Badge>
                    </td>
                    <td className="text-right py-2 align-top">
                      {formatCurrency(isHtMode ? summary.commissions_par_canal[canal].ht : summary.commissions_par_canal[canal].ttc)} €
                    </td>
                    {isHtMode ? (
                      <td className="text-right py-2 align-top font-semibold">
                        {formatPercent(commRate)}
                      </td>
                    ) : (
                      <td className="text-right py-2 align-top font-semibold text-emerald-700 dark:text-emerald-300">
                        {formatCurrency(summary.net_vendeur_par_canal[canal])} €
                      </td>
                    )}
                  </tr>
                );
              })}
              <tr className="border-t-2">
                <th scope="row" className="text-left py-2 font-semibold">Total</th>
                <td className="text-right py-2 font-semibold">{formatCurrency(isHtMode ? kpiTotals.caHt : kpiTotals.caTtc)} €</td>
                <td className="text-right py-2 font-semibold">{formatCurrency(isHtMode ? kpiTotals.rembHt : kpiTotals.rembTtc)} €</td>
                <td className="text-right py-2">
                  <Badge variant="outline" className={getRefundRateBadgeClass(kpiTotals.taux)}>
                    {formatPercent(kpiTotals.taux)}
                  </Badge>
                </td>
                <td className="text-right py-2 font-semibold">{formatCurrency(isHtMode ? kpiTotals.commHt : kpiTotals.commTtc)} €</td>
                {isHtMode ? (
                  <td className="text-right py-2 font-semibold">
                    {formatPercent(kpiTotals.tauxComm)}
                  </td>
                ) : (
                  <td className="text-right py-2 font-semibold text-emerald-700 dark:text-emerald-300">
                    {formatCurrency(kpiTotals.net)} €
                  </td>
                )}
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* ====================================================== */}
      {/* Ventilation CA : Produits / Frais de port               */}
      {/* ====================================================== */}

      <h2 className="text-lg font-bold mt-8">Ventilation du CA : Produits / Frais de port</h2>

      <section className={sectionCard}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th scope="col" className="text-left py-2 font-medium">Canal</th>
                <th scope="col" className="text-right py-2 font-medium">CA Produits HT</th>
                <th scope="col" className="text-right py-2 font-medium">CA Frais de port HT</th>
                <th scope="col" className="text-right py-2 font-medium">CA Total HT</th>
              </tr>
            </thead>
            <tbody>
              {kpiChannels.map((canal) => {
                const meta = getChannelMeta(canal);
                const v = summary.ventilation_ca_par_canal[canal];
                return (
                  <tr key={canal} className={tableRowAlt}>
                    <th scope="row" className="text-left py-2 font-normal">
                      <Badge variant="outline" className={meta.badgeClass}>
                        {meta.label}
                      </Badge>
                    </th>
                    <td className="text-right py-2">{formatCurrency(v.produits_ht)} €</td>
                    <td className="text-right py-2">{formatCurrency(v.port_ht)} €</td>
                    <td className="text-right py-2 font-semibold">{formatCurrency(v.total_ht)} €</td>
                  </tr>
                );
              })}
              <tr className="border-t-2">
                <th scope="row" className="text-left py-2 font-semibold">Total</th>
                <td className="text-right py-2 font-semibold">
                  {formatCurrency(kpiChannels.reduce((s, c) => s + summary.ventilation_ca_par_canal[c].produits_ht, 0))} €
                </td>
                <td className="text-right py-2 font-semibold">
                  {formatCurrency(kpiChannels.reduce((s, c) => s + summary.ventilation_ca_par_canal[c].port_ht, 0))} €
                </td>
                <td className="text-right py-2 font-semibold">
                  {formatCurrency(kpiTotals.caHt)} €
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* ====================================================== */}
      {/* Fiscalite (AC20)                                        */}
      {/* ====================================================== */}

      <h2 className="text-lg font-bold mt-8">Fiscalité</h2>

      <section className={sectionCard}>
        <h3 className={sectionTitle}>TVA collectée par canal</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th scope="col" className="text-left py-2 font-medium">Canal</th>
              <th scope="col" className="text-right py-2 font-medium">Montant</th>
            </tr>
          </thead>
          <tbody>
            {kpiChannels.map((canal) => {
              const meta = getChannelMeta(canal);
              const tvaPays = summary.tva_par_pays_par_canal[canal];
              return (
                <tr key={canal} className={tableRowAlt}>
                  <th scope="row" className="text-left py-2 font-normal align-top">
                    <details>
                      <summary className="cursor-pointer list-none">
                        <Badge variant="outline" className={meta.badgeClass}>
                          {meta.label}
                        </Badge>
                      </summary>
                      {tvaPays && (
                        <div className="overflow-x-auto mt-2">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b">
                                <th scope="col" className="text-left py-1 font-medium">Pays</th>
                                <th scope="col" className="text-right py-1 font-medium">Taux TVA</th>
                                <th scope="col" className="text-right py-1 font-medium">Montant TVA</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(tvaPays).map(([pays, rows]) =>
                                rows.map((row, i) => (
                                  <tr key={`${pays}-${i}`} className="border-b">
                                    <th scope="row" className="text-left py-1 font-normal">{i === 0 ? pays : ""}</th>
                                    <td className="text-right py-1">{formatPercent(row.taux)}</td>
                                    <td className="text-right py-1">{formatCurrency(row.montant)} €</td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </details>
                  </th>
                  <td className="text-right py-2 align-top">{formatCurrency(summary.tva_collectee_par_canal[canal])} €</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {/* ====================================================== */}
      {/* Répartition géographique (AC21)                         */}
      {/* ====================================================== */}

      <h2 className="text-lg font-bold mt-8">Répartition géographique</h2>

      <section className={sectionCard}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th scope="col" className="text-left py-2 font-medium">Pays</th>
                <th scope="col" className="text-right py-2 font-medium">Transactions</th>
                <th scope="col" className="text-right py-2 font-medium">CA HT</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.repartition_geo_globale).map(([pays, data]) => (
                <tr key={pays} className={tableRowAlt}>
                  <th scope="row" className="text-left py-2 font-normal">{pays}</th>
                  <td className="text-right py-2">{formatCount(data.count)}</td>
                  <td className="text-right py-2">{formatCurrency(data.ca_ht)} €</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {Object.entries(summary.repartition_geo_par_canal).map(([canal, countries]) => {
          const meta = getChannelMeta(canal);
          return (
            <details key={canal} className="mt-2">
              <summary className="cursor-pointer text-sm font-medium">
                <Badge variant="outline" className={meta.badgeClass}>
                  {meta.label}
                </Badge>
              </summary>
              <div className="overflow-x-auto mt-1">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th scope="col" className="text-left py-1 font-medium">Pays</th>
                      <th scope="col" className="text-right py-1 font-medium">Transactions</th>
                      <th scope="col" className="text-right py-1 font-medium">CA HT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(countries).map(([pays, data]) => (
                      <tr key={pays} className="border-b">
                        <th scope="row" className="text-left py-1 font-normal">{pays}</th>
                        <td className="text-right py-1">{formatCount(data.count)}</td>
                        <td className="text-right py-1">{formatCurrency(data.ca_ht)} €</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          );
        })}
      </section>

      </>)}
    </div>
  );
}
