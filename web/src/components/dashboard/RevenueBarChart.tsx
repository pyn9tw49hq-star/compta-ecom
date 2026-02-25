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

interface RevenueBarItem {
  channel: string;
  label: string;
  value: number;
  fill: string;
}

interface RevenueBarChartProps {
  data: RevenueBarItem[];
  modeLabel: string;
}

/**
 * Horizontal bar chart — CA HT per channel, sorted descending.
 */
export default function RevenueBarChart({ data, modeLabel }: RevenueBarChartProps) {
  const reducedMotion = useReducedMotion();

  return (
    <ChartCard
      title={`CA par canal (${modeLabel})`}
      subtitle="Montants par marketplace"
      minHeight={280}
      empty={data.length === 0}
      accessibleTable={{
        caption: `CA ${modeLabel} par canal`,
        headers: ["Canal", `CA ${modeLabel}`],
        rows: data.map((d) => [d.label, `${formatCurrency(d.value)} €`]),
      }}
    >
      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={data}
          layout="vertical"
          role="img"
          aria-label={`CA ${modeLabel} par canal, diagramme en barres horizontales`}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} className="fill-foreground" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
          <YAxis type="category" dataKey="label" tick={{ fontSize: 12 }} className="fill-foreground" width={90} />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const item = payload[0].payload as RevenueBarItem;
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium flex items-center gap-1.5">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.fill }} />
                    {item.label}
                  </p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">CA {modeLabel}</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.value)} €</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Bar dataKey="value" isAnimationActive={!reducedMotion}>
            {data.map((item) => (
              <Cell key={item.channel} fill={item.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
