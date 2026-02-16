"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { getChannelMeta } from "@/lib/channels";
import { formatCurrency, formatCount, formatPercent } from "@/lib/format";
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

/**
 * Badge class for VAT anomaly rate: green < 1%, orange 1–5%, red > 5%.
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
 * Badge class for refund rate: green < 5%, orange 5–10%, red > 10%.
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

// --- Component ---

interface StatsBoardProps {
  summary: Summary;
  entries: Entry[];
  anomalies: Anomaly[];
  htTtcMode: "ht" | "ttc";
  onHtTtcModeChange: (mode: "ht" | "ttc") => void;
}

/**
 * Dashboard showing key processing metrics: balance, transactions per channel,
 * entries by type, and anomaly counts by severity.
 */
export default function StatsBoard({ summary, entries, anomalies, htTtcMode, onHtTtcModeChange }: StatsBoardProps) {
  const isHtMode = htTtcMode === "ht";
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
    const net = kpiChannels.reduce((s, c) => s + summary.net_vendeur_par_canal[c], 0);
    const taux = caTtc > 0 ? Math.round(rembTtc / caTtc * 1000) / 10 : 0;
    const tauxComm = caHt > 0 ? Math.round(commHt / caHt * 1000) / 10 : 0;
    return { caTtc, caHt, rembTtc, rembHt, commTtc, commHt, net, taux, tauxComm };
  }, [hasKpis, kpiChannels, summary]);

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
          <>
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

      <section>
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
                  <tr key={canal} className="border-b">
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
                              <div>Net vendeur : {formatCurrency(summary.net_vendeur_par_canal[canal])} €</div>
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

      <section>
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
                  <tr key={canal} className="border-b">
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
      {/* Fiscalité (AC20)                                        */}
      {/* ====================================================== */}

      <h2 className="text-lg font-bold mt-8">Fiscalité</h2>

      <section>
        <h3 className="text-base font-semibold mb-2">TVA collectée par canal</h3>
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
                <tr key={canal} className="border-b">
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

      <section>
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
                <tr key={pays} className="border-b">
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
