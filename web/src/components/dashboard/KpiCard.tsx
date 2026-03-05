"use client";

import { Card } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";
import { useNewDesign } from "@/hooks/useNewDesign";

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
  const isV2 = useNewDesign();
  const isStatus = variant === "status";
  const borderClass = isStatus && borderColor ? `border-l-4 ${BORDER_COLORS[borderColor]}` : "";
  const clickable = !!onNavigate;

  /* ─── V2 Design ─── */
  if (isV2) {
    if (loading) {
      return (
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="h-3 w-24 animate-pulse rounded bg-muted mb-3" />
          <div className="h-8 w-32 animate-pulse rounded bg-muted mb-3" />
          <div className="h-3 w-20 animate-pulse rounded bg-muted" />
        </div>
      );
    }

    const cardContent = (
      <div
        className={`rounded-xl border border-border bg-card p-6 flex flex-col gap-3 ${
          clickable
            ? "cursor-pointer hover:-translate-y-0.5 hover:shadow-lg transition duration-200"
            : "hover:-translate-y-0.5 hover:shadow-lg transition duration-200"
        }`}
        onClick={onNavigate}
        role={clickable ? "button" : undefined}
        tabIndex={clickable ? 0 : undefined}
        onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onNavigate?.(); } } : undefined}
      >
        {/* Header: label (Inter 11px 600) + icon circle */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[2px] text-muted-foreground">
            {title}
          </span>
          {Icon && (
            <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/10">
              <Icon className="h-[18px] w-[18px] text-primary" aria-hidden="true" />
            </div>
          )}
        </div>

        {/* Value (Newsreader 26px 700) */}
        <p className="font-newsreader text-[26px] font-bold leading-tight text-foreground">
          {value}
        </p>

        {/* Subtitle/footer (Inter 12px normal) */}
        {subtitle && (
          <p className="text-xs text-muted-foreground">
            {subtitle}
          </p>
        )}
      </div>
    );

    return cardContent;
  }

  /* ─── V1 Design (legacy) ─── */
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
      <p className={`${value.length > 8 ? "text-xl" : "text-2xl"} font-bold tabular-nums mt-1${isV2 ? " font-mono-numbers" : ""}`}>{value}</p>
      {subtitle && (
        <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>
      )}
    </Card>
  );

  return card;
}
