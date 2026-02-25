"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import ChartCard from "./ChartCard";
import { useReducedMotion } from "./useReducedMotion";
import { METRIC_COLORS } from "./chartColors";
import { formatCurrency, formatPercent } from "@/lib/format";

interface ProfitabilityItem {
  channel: string;
  label: string;
  ca: number;
  commissions: number;
  net: number;
  commissionRate: number;
}

interface ProfitabilityChartProps {
  data: ProfitabilityItem[];
  isDark: boolean;
}

/**
 * Stacked vertical bar chart — CA HT decomposed into Net vendeur + Commissions per channel.
 * Each bar shows the financial breakdown: CA = Net + Commissions.
 */
export default function ProfitabilityChart({ data, isDark }: ProfitabilityChartProps) {
  const reducedMotion = useReducedMotion();
  const commColor = isDark ? METRIC_COLORS.commissions.dark : METRIC_COLORS.commissions.light;
  const netColor = isDark ? METRIC_COLORS.net_vendeur.dark : METRIC_COLORS.net_vendeur.light;

  return (
    <ChartCard
      title="Rentabilité par canal"
      subtitle="Décomposition du CA HT : net vendeur + commissions"
      minHeight={320}
      empty={data.length === 0}
      accessibleTable={{
        caption: "Rentabilité par canal de vente",
        headers: ["Canal", "CA HT", "Commissions HT", "Net vendeur", "Taux comm."],
        rows: data.map((d) => [
          d.label,
          `${formatCurrency(d.ca)} €`,
          `${formatCurrency(d.commissions)} €`,
          `${formatCurrency(d.net)} €`,
          formatPercent(d.commissionRate),
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height={320}>
        <BarChart
          data={data}
          role="img"
          aria-label="Rentabilité par canal, barres empilées verticales — net vendeur et commissions"
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} className="fill-foreground" />
          <YAxis tick={{ fontSize: 11 }} className="fill-foreground" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              const item = payload[0]?.payload as ProfitabilityItem;
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium">{label}</p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm space-y-0.5">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">CA HT</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.ca)} €</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Net vendeur</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.net)} €</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Commissions HT</dt>
                      <dd className="tabular-nums text-right">{formatCurrency(item.commissions)} €</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Taux commission</dt>
                      <dd className="tabular-nums text-right">{formatPercent(item.commissionRate)}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Legend
            content={() => (
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2 text-xs">
                <span className="flex items-center gap-1">
                  <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: netColor }} />
                  Net vendeur
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: commColor }} />
                  Commissions HT
                </span>
              </div>
            )}
          />
          <Bar dataKey="net" stackId="profitability" name="Net vendeur" fill={netColor} isAnimationActive={!reducedMotion} />
          <Bar dataKey="commissions" stackId="profitability" name="Commissions HT" fill={commColor} isAnimationActive={!reducedMotion} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
