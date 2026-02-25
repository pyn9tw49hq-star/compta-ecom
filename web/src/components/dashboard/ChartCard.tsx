"use client";

import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";

interface AccessibleTableData {
  caption: string;
  headers: string[];
  rows: (string | number)[][];
}

interface ChartCardProps {
  title: string;
  subtitle?: string;
  minHeight: number;
  children: ReactNode;
  fullWidth?: boolean;
  accessibleTable?: AccessibleTableData;
  empty?: boolean;
  emptyMessage?: string;
}

/**
 * Wrapper card for Recharts charts — consistent layout with title, subtitle,
 * fixed height, empty state, and sr-only accessible table.
 */
export default function ChartCard({
  title,
  subtitle,
  minHeight,
  children,
  accessibleTable,
  empty,
  emptyMessage = "Aucune donnée",
}: ChartCardProps) {
  return (
    <Card className="p-4">
      <h3 className="text-base font-semibold">{title}</h3>
      {subtitle && (
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      )}
      <div className="mt-3" style={{ minHeight }}>
        {empty ? (
          <div
            className="flex flex-col items-center justify-center text-muted-foreground/60"
            style={{ minHeight }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-10 w-10 mb-2 opacity-40"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3v18h18" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16l4-4 4 4 5-5" />
            </svg>
            <span className="text-sm">{emptyMessage}</span>
          </div>
        ) : (
          children
        )}
      </div>
      {accessibleTable && (
        <table className="sr-only">
          <caption>{accessibleTable.caption}</caption>
          <thead>
            <tr>
              {accessibleTable.headers.map((h) => (
                <th key={h} scope="col">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {accessibleTable.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  j === 0
                    ? <th key={j} scope="row">{cell}</th>
                    : <td key={j}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
