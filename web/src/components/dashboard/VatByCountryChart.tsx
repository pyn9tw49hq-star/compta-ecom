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
import { GEO_PALETTE } from "./chartColors";
import { formatCurrency, formatPercent } from "@/lib/format";

interface VatCountryItem {
  country: string;
  amount: number;
  fill: string;
}

interface VatByCountryChartProps {
  data: VatCountryItem[];
  total: number;
  isDark: boolean;
}

/**
 * Horizontal bar chart of TVA collected by country (all channels combined).
 */
export default function VatByCountryChart({ data, total, isDark }: VatByCountryChartProps) {
  const reducedMotion = useReducedMotion();

  return (
    <ChartCard
      title="TVA collectée par pays"
      subtitle="Tous canaux confondus (top 10)"
      minHeight={300}
      empty={data.length === 0}
      accessibleTable={{
        caption: "TVA collectée par pays",
        headers: ["Pays", "TVA", "Part"],
        rows: data.map((d) => [
          d.country,
          `${formatCurrency(d.amount)} €`,
          formatPercent(total > 0 ? (d.amount / total) * 100 : 0),
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={data}
          layout="vertical"
          role="img"
          aria-label="TVA collectée par pays, diagramme en barres horizontales"
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 11 }}
            className="fill-foreground"
            tickFormatter={(v: number) => v > 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`}
          />
          <YAxis type="category" dataKey="country" tick={{ fontSize: 12 }} className="fill-foreground" width={70} />
          <Tooltip
            cursor={{ fill: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const item = payload[0].payload as VatCountryItem;
              const pct = total > 0 ? (item.amount / total) * 100 : 0;
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium">{item.country}</p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm space-y-0.5">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">TVA collectée</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.amount)} €</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Part du total</dt>
                      <dd className="tabular-nums text-right">{formatPercent(pct)}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Bar dataKey="amount" isAnimationActive={!reducedMotion}>
            {data.map((item, i) => {
              const geo = GEO_PALETTE[i % GEO_PALETTE.length];
              return <Cell key={item.country} fill={isDark ? geo.dark : geo.light} />;
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
