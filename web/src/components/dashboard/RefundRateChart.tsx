"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
  ResponsiveContainer,
} from "recharts";
import ChartCard from "./ChartCard";
import { useReducedMotion } from "./useReducedMotion";
import { formatPercent } from "@/lib/format";

interface RefundRateItem {
  channel: string;
  label: string;
  rate: number;
  fill: string;
}

interface RefundRateChartProps {
  data: RefundRateItem[];
}

/**
 * Horizontal bar chart with 5%/10% threshold reference lines.
 */
export default function RefundRateChart({ data }: RefundRateChartProps) {
  const reducedMotion = useReducedMotion();
  const maxRate = Math.max(...data.map((d) => d.rate), 12);

  return (
    <ChartCard
      title="Taux de remboursement"
      subtitle="Par canal avec seuils 5 % / 10 %"
      minHeight={220}
      empty={data.length === 0}
      accessibleTable={{
        caption: "Taux de remboursement par canal",
        headers: ["Canal", "Taux", "Statut"],
        rows: data.map((d) => [
          d.label,
          formatPercent(d.rate),
          d.rate < 5 ? "OK" : d.rate <= 10 ? "Attention" : "Alerte",
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={data}
          layout="vertical"
          role="img"
          aria-label="Taux de remboursement par canal, diagramme en barres horizontales"
          margin={{ right: 30 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis type="number" domain={[0, maxRate]} tick={{ fontSize: 11 }} className="fill-foreground" tickFormatter={(v) => `${v}%`} />
          <YAxis type="category" dataKey="label" tick={{ fontSize: 12 }} className="fill-foreground" width={90} />
          <ReferenceLine x={5} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: "5 %", position: "top", fontSize: 10, fill: "#f59e0b" }} />
          <ReferenceLine x={10} stroke="#ef4444" strokeDasharray="4 4" label={{ value: "10 %", position: "top", fontSize: 10, fill: "#ef4444" }} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const item = payload[0].payload as RefundRateItem;
              const status = item.rate < 5 ? "✓ OK" : item.rate <= 10 ? "⚠ Attention" : "⊘ Alerte";
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium">{item.label}</p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm space-y-0.5">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Taux remb.</dt>
                      <dd className="tabular-nums text-right font-medium">{formatPercent(item.rate)}</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Statut</dt>
                      <dd className="text-right">{status}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Bar dataKey="rate" isAnimationActive={!reducedMotion}>
            {data.map((item) => (
              <Cell key={item.channel} fill={item.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
