"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, Label, ResponsiveContainer } from "recharts";
import ChartCard from "./ChartCard";
import { useReducedMotion } from "./useReducedMotion";
import { formatCount } from "@/lib/format";

const ENTRY_TYPE_LABELS: Record<string, string> = {
  sale: "Vente",
  refund: "Remboursement",
  settlement: "Règlement",
  commission: "Commission",
  payout: "Reversement",
  fee: "Frais",
};

interface EntryTypeItem {
  type: string;
  label: string;
  count: number;
  fill: string;
}

interface EntryTypeDonutProps {
  data: EntryTypeItem[];
  total: number;
}

/**
 * Donut chart showing entry distribution by type.
 */
export default function EntryTypeDonut({ data, total }: EntryTypeDonutProps) {
  const reducedMotion = useReducedMotion();

  return (
    <ChartCard
      title="Écritures par type"
      subtitle="Répartition des écritures comptables"
      minHeight={280}
      empty={data.length === 0}
      accessibleTable={{
        caption: "Répartition des écritures par type",
        headers: ["Type", "Nombre"],
        rows: data.map((d) => [ENTRY_TYPE_LABELS[d.type] ?? d.type, d.count]),
      }}
    >
      <ResponsiveContainer width="100%" height={280}>
        <PieChart role="img" aria-label="Répartition des écritures comptables par type, diagramme en donut">
          <Pie
            data={data}
            dataKey="count"
            nameKey="label"
            cx="50%"
            cy="50%"
            innerRadius="55%"
            outerRadius="80%"
            paddingAngle={2}
            isAnimationActive={!reducedMotion}
          >
            {data.map((entry) => (
              <Cell key={entry.type} fill={entry.fill} />
            ))}
            <Label
              position="center"
              content={({ viewBox }) => {
                if (!viewBox || !("cx" in viewBox)) return null;
                return (
                  <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="central">
                    <tspan x={viewBox.cx} dy="-0.5em" className="fill-foreground text-lg font-bold">
                      {formatCount(total)}
                    </tspan>
                    <tspan x={viewBox.cx} dy="1.4em" className="fill-muted-foreground text-xs">
                      écritures
                    </tspan>
                  </text>
                );
              }}
            />
          </Pie>
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const item = payload[0].payload as EntryTypeItem;
              return (
                <div className="bg-popover text-popover-foreground border rounded-lg shadow-md p-3 max-w-[280px]">
                  <p className="font-medium flex items-center gap-1.5">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.fill }} />
                    {item.label}
                  </p>
                  <hr className="my-1.5 border-border" />
                  <dl className="text-sm">
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Nombre</dt>
                      <dd className="tabular-nums text-right font-medium">{formatCount(item.count)}</dd>
                    </div>
                  </dl>
                </div>
              );
            }}
          />
          <Legend
            content={({ payload }) => (
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2 text-xs">
                {payload?.map((entry) => (
                  <span key={entry.value} className="flex items-center gap-1">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                    {entry.value}
                  </span>
                ))}
              </div>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
