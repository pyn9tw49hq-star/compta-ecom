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
import { formatCurrency } from "@/lib/format";

interface VatItem {
  channel: string;
  label: string;
  amount: number;
  fill: string;
}

interface VatChartProps {
  data: VatItem[];
}

/**
 * Bar chart of TVA collected per channel.
 */
export default function VatChart({ data }: VatChartProps) {
  const reducedMotion = useReducedMotion();

  return (
    <ChartCard
      title="TVA collectée par canal"
      subtitle="Montants de TVA collectée"
      minHeight={280}
      empty={data.length === 0}
      accessibleTable={{
        caption: "TVA collectée par canal",
        headers: ["Canal", "TVA collectée"],
        rows: data.map((d) => [d.label, `${formatCurrency(d.amount)} €`]),
      }}
    >
      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={data}
          role="img"
          aria-label="TVA collectée par canal, diagramme en barres"
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} className="fill-foreground" />
          <YAxis tick={{ fontSize: 11 }} className="fill-foreground" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const item = payload[0].payload as VatItem;
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium flex items-center gap-1.5">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.fill }} />
                    {item.label}
                  </p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">TVA collectée</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.amount)} €</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Bar dataKey="amount" isAnimationActive={!reducedMotion}>
            {data.map((item) => (
              <Cell key={item.channel} fill={item.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
