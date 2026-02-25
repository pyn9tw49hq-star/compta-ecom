"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import ChartCard from "./ChartCard";
import { useReducedMotion } from "./useReducedMotion";
import { formatCount } from "@/lib/format";

interface SeverityItem {
  severity: "error" | "warning" | "info";
  label: string;
  count: number;
  fill: string;
}

interface AnomalySeverityChartProps {
  data: SeverityItem[];
  total: number;
  onNavigateAnomalies?: () => void;
}

const SEVERITY_LABELS: Record<string, string> = {
  error: "Erreur(s)",
  warning: "Avertissement(s)",
  info: "Info(s)",
};

/**
 * Horizontal bar chart showing anomaly counts by severity.
 */
export default function AnomalySeverityChart({ data, total, onNavigateAnomalies }: AnomalySeverityChartProps) {
  const reducedMotion = useReducedMotion();

  return (
    <ChartCard
      title="Santé des données"
      subtitle={`${formatCount(total)} anomalie${total !== 1 ? "s" : ""} détectée${total !== 1 ? "s" : ""}`}
      minHeight={220}
      empty={data.length === 0}
      accessibleTable={{
        caption: "Anomalies par sévérité",
        headers: ["Sévérité", "Nombre"],
        rows: data.map((d) => [SEVERITY_LABELS[d.severity] ?? d.severity, d.count]),
      }}
    >
      <div>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart
            data={data}
            layout="vertical"
            role="img"
            aria-label="Anomalies par sévérité, diagramme en barres horizontales"
          >
            <XAxis type="number" tick={{ fontSize: 11 }} className="fill-foreground" allowDecimals={false} />
            <YAxis type="category" dataKey="label" tick={{ fontSize: 12 }} className="fill-foreground" width={100} />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const item = payload[0].payload as SeverityItem;
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
            <Bar dataKey="count" isAnimationActive={!reducedMotion}>
              {data.map((item) => (
                <Cell key={item.severity} fill={item.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {onNavigateAnomalies && (
          <button
            onClick={onNavigateAnomalies}
            className="text-sm text-primary hover:underline mt-1"
          >
            Voir détails →
          </button>
        )}
      </div>
    </ChartCard>
  );
}
