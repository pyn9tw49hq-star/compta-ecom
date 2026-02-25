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
import { formatCurrency } from "@/lib/format";

interface VentilationItem {
  channel: string;
  label: string;
  produits_ht: number;
  port_ht: number;
}

interface VentilationChartProps {
  data: VentilationItem[];
  isDark: boolean;
}

/**
 * Horizontal stacked bar chart — Products HT + Shipping HT per channel.
 */
export default function VentilationChart({ data, isDark }: VentilationChartProps) {
  const reducedMotion = useReducedMotion();
  const prodColor = isDark ? "#60a5fa" : "#2563eb";
  const portColor = isDark ? "rgba(96,165,250,0.4)" : "rgba(37,99,235,0.4)";

  return (
    <ChartCard
      title="Ventilation CA"
      subtitle="Produits vs frais de port (HT)"
      minHeight={240}
      empty={data.length === 0}
      accessibleTable={{
        caption: "Ventilation CA produits vs frais de port par canal",
        headers: ["Canal", "Produits HT", "Port HT", "Total HT"],
        rows: data.map((d) => [
          d.label,
          `${formatCurrency(d.produits_ht)} €`,
          `${formatCurrency(d.port_ht)} €`,
          `${formatCurrency(d.produits_ht + d.port_ht)} €`,
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          data={data}
          layout="vertical"
          role="img"
          aria-label="Ventilation CA produits et frais de port par canal, barres empilées"
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} className="fill-foreground" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
          <YAxis type="category" dataKey="label" tick={{ fontSize: 12 }} className="fill-foreground" width={90} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const item = payload[0]?.payload as VentilationItem;
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium">{item.label}</p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm space-y-0.5">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Produits HT</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.produits_ht)} €</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Port HT</dt>
                      <dd className="tabular-nums text-right">{formatCurrency(item.port_ht)} €</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Total HT</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.produits_ht + item.port_ht)} €</dd>
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
                  <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: prodColor }} />
                  Produits HT
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: portColor }} />
                  Port HT
                </span>
              </div>
            )}
          />
          <Bar dataKey="produits_ht" stackId="a" fill={prodColor} name="Produits HT" isAnimationActive={!reducedMotion} />
          <Bar dataKey="port_ht" stackId="a" fill={portColor} name="Port HT" isAnimationActive={!reducedMotion} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
