"use client";

import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getChannelMeta } from "@/lib/channels";
import { formatCount, formatPercent } from "@/lib/format";

interface MatchingRateCardProps {
  tauxParCanal: Record<string, number>;
  ventesParCanal: Record<string, number>;
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

/**
 * Matching rate summary card for the Flash e-commerce dashboard.
 * Displays a table of channels with their sales count, matched count, and rate.
 */
export default function MatchingRateCard({ tauxParCanal, ventesParCanal }: MatchingRateCardProps) {
  const rapChannels = useMemo(() => Object.keys(ventesParCanal), [ventesParCanal]);

  const { totalVentes, totalMatched, totalRate, allPerfect } = useMemo(() => {
    const tv = rapChannels.reduce((s, c) => s + ventesParCanal[c], 0);
    const tm = rapChannels.reduce(
      (s, c) => s + Math.round(ventesParCanal[c] * tauxParCanal[c] / 100),
      0,
    );
    const tr = tv > 0 ? Math.round(tm / tv * 1000) / 10 : 0;
    const ap = rapChannels.every((c) => tauxParCanal[c] === 100);
    return { totalVentes: tv, totalMatched: tm, totalRate: tr, allPerfect: ap };
  }, [rapChannels, tauxParCanal, ventesParCanal]);

  if (rapChannels.length === 0) return null;

  return (
    <Card className="p-4">
      <h3 className="text-base font-semibold">Taux de rapprochement</h3>
      <p className="text-sm text-muted-foreground">Rapprochement des ventes par canal</p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm" aria-label="Taux de rapprochement par canal de vente">
          <thead>
            <tr className="border-b">
              <th scope="col" className="text-left py-2 font-medium">Canal</th>
              <th scope="col" className="text-right py-2 font-medium">Ventes</th>
              <th scope="col" className="text-right py-2 font-medium">Rapprochees</th>
              <th scope="col" className="text-right py-2 font-medium">Taux</th>
            </tr>
          </thead>
          <tbody>
            {rapChannels.map((canal) => {
              const meta = getChannelMeta(canal);
              const ventes = ventesParCanal[canal];
              const taux = tauxParCanal[canal];
              const matched = Math.round(ventes * taux / 100);
              return (
                <tr key={canal} className="border-b">
                  <th scope="row" className="text-left py-2 font-normal">
                    <Badge variant="outline" className={meta.badgeClass}>
                      {meta.label}
                    </Badge>
                  </th>
                  <td className="text-right py-2 tabular-nums">{formatCount(ventes)}</td>
                  <td className="text-right py-2 tabular-nums">{formatCount(matched)}</td>
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
              <td className="text-right py-2 font-semibold tabular-nums">{formatCount(totalVentes)}</td>
              <td className="text-right py-2 font-semibold tabular-nums">{formatCount(totalMatched)}</td>
              <td className="text-right py-2">
                <Badge variant="outline" className={getRapprochementBadgeClass(totalRate)}>
                  {formatPercent(totalRate)}
                </Badge>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="text-sm mt-2 text-muted-foreground">
        {allPerfect
          ? "Toutes les transactions ont ete rapprochees avec succes."
          : "Certains canaux presentent des transactions non rapprochees."}
      </p>
    </Card>
  );
}
