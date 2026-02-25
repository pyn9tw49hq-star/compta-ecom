"use client";

import { Card } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";

const BORDER_COLORS = {
  green: "border-l-green-500",
  red: "border-l-red-500",
  orange: "border-l-orange-500",
} as const;

interface KpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon?: LucideIcon;
  variant?: "metric" | "status";
  borderColor?: "green" | "red" | "orange";
  onNavigate?: () => void;
  loading?: boolean;
}

/**
 * KPI card for dashboard Zone 1.
 * Variants: "metric" (standard) and "status" (with colored left border).
 */
export default function KpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = "metric",
  borderColor,
  onNavigate,
  loading,
}: KpiCardProps) {
  const isStatus = variant === "status";
  const borderClass = isStatus && borderColor ? `border-l-4 ${BORDER_COLORS[borderColor]}` : "";
  const clickable = !!onNavigate;

  if (loading) {
    return (
      <Card className="p-4">
        <div className="h-4 w-24 animate-pulse rounded bg-muted mb-2" />
        <div className="h-7 w-20 animate-pulse rounded bg-muted" />
      </Card>
    );
  }

  const card = (
    <Card
      className={`p-4 ${borderClass} ${
        clickable
          ? "cursor-pointer hover:-translate-y-0.5 hover:shadow-lg motion-reduce:hover:translate-y-0"
          : "hover:-translate-y-0.5 hover:shadow-lg motion-reduce:hover:translate-y-0"
      } transition duration-200`}
      onClick={onNavigate}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onNavigate?.(); } } : undefined}
      aria-label={`${title} : ${value}${subtitle ? ` — ${subtitle}` : ""}`}
    >
      <div className="flex items-start justify-between">
        <p className="text-xs text-muted-foreground">{title}</p>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
      </div>
      <p className="text-2xl font-bold tabular-nums mt-1">{value}</p>
      {subtitle && (
        <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>
      )}
    </Card>
  );

  return card;
}
