"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";
import ChartCard from "./ChartCard";
import { useReducedMotion } from "./useReducedMotion";
import { formatCurrency, formatPercent, formatCount } from "@/lib/format";

interface GeoItem {
  country: string;
  ca_ttc: number;
  count: number;
  fill: string;
}

interface GeoChartProps {
  data: GeoItem[];
  total: number;
  isDark: boolean;
}

/**
 * Horizontal bar chart of top 10 countries by CA TTC — neutral grey palette.
 */
export default function GeoChart({ data, total, isDark }: GeoChartProps) {
  const reducedMotion = useReducedMotion();

  return (
    <ChartCard
      title="Répartition géographique"
      subtitle="CA TTC par pays (toutes marketplaces)"
      minHeight={300}
      empty={data.length === 0}
      accessibleTable={{
        caption: "Répartition géographique du CA TTC",
        headers: ["Pays", "CA TTC", "Part", "Transactions"],
        rows: data.map((d) => [
          d.country,
          `${formatCurrency(d.ca_ttc)} €`,
          formatPercent(total > 0 ? (d.ca_ttc / total) * 100 : 0),
          formatCount(d.count),
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={data}
          layout="vertical"
          role="img"
          aria-label="Répartition géographique du CA TTC, diagramme en barres horizontales"
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} className="fill-foreground" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
          <YAxis type="category" dataKey="country" tick={{ fontSize: 11 }} className="fill-foreground" width={70} />
          <Tooltip
            cursor={{ fill: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const item = payload[0].payload as GeoItem;
              const pct = total > 0 ? (item.ca_ttc / total) * 100 : 0;
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium">{item.country}</p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm space-y-0.5">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">CA TTC</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.ca_ttc)} €</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Part du total</dt>
                      <dd className="tabular-nums text-right">{formatPercent(pct)}</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Transactions</dt>
                      <dd className="tabular-nums text-right">{formatCount(item.count)}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Bar dataKey="ca_ttc" isAnimationActive={!reducedMotion}>
            {data.map((item) => (
              <Cell key={item.country} fill={item.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
