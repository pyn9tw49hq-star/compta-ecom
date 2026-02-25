"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, Label, ResponsiveContainer } from "recharts";
import ChartCard from "./ChartCard";
import { useReducedMotion } from "./useReducedMotion";
import { formatCurrency, formatPercent } from "@/lib/format";

interface ChannelRevenue {
  channel: string;
  label: string;
  value: number;
  fill: string;
}

interface RevenuePieChartProps {
  data: ChannelRevenue[];
  total: number;
  modeLabel: string;
}

/**
 * Donut chart showing CA distribution per channel.
 */
export default function RevenuePieChart({ data, total, modeLabel }: RevenuePieChartProps) {
  const reducedMotion = useReducedMotion();

  return (
    <ChartCard
      title={`Répartition CA ${modeLabel}`}
      subtitle="Part de chaque canal"
      minHeight={280}
      empty={data.length === 0}
      accessibleTable={{
        caption: `Répartition du chiffre d'affaires ${modeLabel} par canal`,
        headers: ["Canal", `CA ${modeLabel}`, "Part"],
        rows: data.map((d) => [
          d.label,
          `${formatCurrency(d.value)} €`,
          formatPercent(total > 0 ? (d.value / total) * 100 : 0),
        ]),
      }}
    >
      <ResponsiveContainer width="100%" height={280}>
        <PieChart role="img" aria-label={`Chiffre d'affaires par canal de vente, diagramme en donut`}>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            cx="50%"
            cy="50%"
            innerRadius="55%"
            outerRadius="80%"
            paddingAngle={2}
            isAnimationActive={!reducedMotion}
          >
            {data.map((entry) => (
              <Cell key={entry.channel} fill={entry.fill} />
            ))}
            <Label
              position="center"
              content={({ viewBox }) => {
                if (!viewBox || !("cx" in viewBox)) return null;
                return (
                  <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="central">
                    <tspan x={viewBox.cx} dy="-0.5em" className="fill-foreground text-lg font-bold">
                      {formatCurrency(total)} €
                    </tspan>
                    <tspan x={viewBox.cx} dy="1.4em" className="fill-muted-foreground text-xs">
                      CA {modeLabel}
                    </tspan>
                  </text>
                );
              }}
            />
          </Pie>
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const item = payload[0].payload as ChannelRevenue;
              const pct = total > 0 ? (item.value / total) * 100 : 0;
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium flex items-center gap-1.5">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.fill }} />
                    {item.label}
                  </p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm space-y-0.5">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">CA {modeLabel}</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCurrency(item.value)} €</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Part du CA</dt>
                      <dd className="tabular-nums text-right">{formatPercent(pct)}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Legend
            content={({ payload }) => (
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2 text-xs">
                {payload?.map((entry) => {
                  const val = (entry.payload as Record<string, unknown>)?.value;
                  const pct = total > 0 && typeof val === "number" ? (val / total) * 100 : 0;
                  return (
                    <span key={entry.value} className="flex items-center gap-1">
                      <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                      {entry.value} {formatPercent(pct)}
                    </span>
                  );
                })}
              </div>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
