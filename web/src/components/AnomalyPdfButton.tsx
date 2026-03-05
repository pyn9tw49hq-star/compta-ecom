"use client";

import { useState, useCallback, useMemo } from "react";
import { ChevronRight, FileText, Loader2 } from "lucide-react";
import * as Popover from "@radix-ui/react-popover";
import * as Checkbox from "@radix-ui/react-checkbox";
import * as RadioGroup from "@radix-ui/react-radio-group";
import { Button } from "@/components/ui/button";
import { generateAnomalyPdf } from "@/lib/generateAnomalyPdf";
import type { AnomalyPdfSections } from "@/lib/generateAnomalyPdf";
import { ANOMALY_CATEGORIES, ANOMALY_TYPE_LABELS, SEVERITY_META } from "@/components/AnomaliesPanel";
import { countVisualCards, getVisualCardKey, HIDDEN_TYPES } from "@/lib/anomalyCardKey";
import { fmtDate } from "@/lib/pdfStyles";
import { getChannelMeta } from "@/lib/channels";
import { useNewDesign } from "@/hooks/useNewDesign";
import type { Anomaly } from "@/lib/types";
import type { DateRange } from "@/lib/datePresets";

interface AnomalyPdfButtonProps {
  anomalies: Anomaly[];
  dateRange: DateRange;
}

const CHECK_SVG = (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
    <path
      d="M2 5L4 7L8 3"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const CHECKBOX_CLASS =
  "flex h-4 w-4 shrink-0 items-center justify-center rounded border border-input bg-background duration-0 data-[state=checked]:bg-foreground data-[state=checked]:text-background";

const RADIO_CLASS =
  "h-4 w-4 rounded-full border border-input bg-background";

const RADIO_INDICATOR_CLASS =
  "flex items-center justify-center after:block after:h-2 after:w-2 after:rounded-full after:bg-foreground";

/* ──────────────────────────────────────────────────────────────── */
/*  V2 design constants (from .pen specs)                          */
/* ──────────────────────────────────────────────────────────────── */

const TEAL = "#0D6E6E";

/** Severity checkbox fill colors matching .pen design */
const SEVERITY_COLORS: Record<string, string> = {
  errors: "#DC2626",
  warnings: "#F59E0B",
  infos: "#3B82F6",
};

/** Channel indicator colors matching .pen design */
const CHANNEL_COLORS: Record<string, string> = {
  shopify: "#95BF47",
  manomano: "#00B2A9",
  decathlon: "#0055A0",
  leroy_merlin: "#2D8C3C",
};

/* ──────────────────────────────────────────────────────────────── */
/*  V1 sub-components                                              */
/* ──────────────────────────────────────────────────────────────── */

function CheckboxItem({
  checked,
  onCheckedChange,
  label,
}: {
  checked: boolean;
  onCheckedChange: () => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer text-sm">
      <Checkbox.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        className={CHECKBOX_CLASS}
      >
        <Checkbox.Indicator className="duration-0">{CHECK_SVG}</Checkbox.Indicator>
      </Checkbox.Root>
      {label}
    </label>
  );
}

function ToggleAllButton({ allChecked, onToggle }: { allChecked: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="text-xs text-muted-foreground underline hover:text-foreground transition-colors"
    >
      {allChecked ? "Tout désélectionner" : "Tout sélectionner"}
    </button>
  );
}

/* ──────────────────────────────────────────────────────────────── */
/*  V2 sub-components                                              */
/* ──────────────────────────────────────────────────────────────── */

function V2ToggleLink({ allChecked, onToggle }: { allChecked: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="text-[10px] hover:underline transition-colors"
      style={{ color: TEAL }}
    >
      {allChecked ? "Tout désélectionner" : "Tout sélectionner"}
    </button>
  );
}

function V2SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="text-[10px] font-semibold uppercase text-muted-foreground"
      style={{ letterSpacing: "1px" }}
    >
      {children}
    </span>
  );
}

function V2Separator() {
  return <div className="h-px w-full bg-border" />;
}

/** Colored checkbox for V2: custom fill when checked, white border when unchecked */
function V2ColorCheckbox({
  checked,
  onCheckedChange,
  fillColor,
  onClick,
}: {
  checked: boolean | "indeterminate";
  onCheckedChange: () => void;
  fillColor: string;
  onClick?: (e: React.MouseEvent) => void;
}) {
  const isChecked = checked === true || checked === "indeterminate";
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked === "indeterminate" ? "mixed" : !!checked}
      onClick={(e) => {
        onClick?.(e);
        onCheckedChange();
      }}
      className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-[3px] border transition-none ${!isChecked ? "border-slate-300 dark:border-slate-500 bg-transparent" : ""}`}
      style={{
        backgroundColor: isChecked ? fillColor : undefined,
        borderColor: isChecked ? fillColor : undefined,
      }}
    >
      {checked === "indeterminate" ? (
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <rect x="2" y="4.5" width="6" height="1.5" rx="0.5" fill="white" />
        </svg>
      ) : isChecked ? (
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2 5L4 7L8 3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : null}
    </button>
  );
}

export default function AnomalyPdfButton({ anomalies, dateRange }: AnomalyPdfButtonProps) {
  const isV2 = useNewDesign();
  const [open, setOpen] = useState(false);
  const [severityFilter, setSeverityFilter] = useState({ errors: true, warnings: true, infos: true });
  const [typeFilter, setTypeFilter] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      Object.values(ANOMALY_CATEGORIES).flatMap((cat) => cat.types.map((t) => [t, true]))
    )
  );
  const [canalFilter, setCanalFilter] = useState<Set<string>>(new Set());
  const [groupBy, setGroupBy] = useState<"severity" | "canal" | "type">("severity");
  const [generating, setGenerating] = useState(false);
  const [expandedCats, setExpandedCats] = useState<Set<string>>(new Set());

  // Unique canals present in anomalies
  const uniqueCanals = useMemo(
    () => Array.from(new Set(anomalies.map((a) => a.canal))).sort(),
    [anomalies],
  );

  // Reset ALL filters when popover opens so the initial count matches the main page
  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      if (isOpen) {
        setSeverityFilter({ errors: true, warnings: true, infos: true });
        setTypeFilter(
          Object.fromEntries(
            Object.values(ANOMALY_CATEGORIES).flatMap((cat) =>
              cat.types.map((t) => [t, true]),
            ),
          ),
        );
        setCanalFilter(new Set(uniqueCanals));
      }
      setOpen(isOpen);
    },
    [uniqueCanals],
  );

  // Single-pass computation of total + per-channel counts.
  // Guarantees that sum(channelAnomalyCounts) === filteredCount.
  const { filteredCount, channelAnomalyCounts } = useMemo(() => {
    const allKeys = new Set<string>();
    const perChannel: Record<string, Set<string>> = {};

    for (const a of anomalies) {
      // Apply all filters
      if (a.severity === "error" && !severityFilter.errors) continue;
      if (a.severity === "warning" && !severityFilter.warnings) continue;
      if (a.severity === "info" && !severityFilter.infos) continue;
      if (!canalFilter.has(a.canal)) continue;
      if (a.type in typeFilter && !typeFilter[a.type]) continue;
      if (HIDDEN_TYPES.has(a.type)) continue;

      const key = getVisualCardKey(a);
      allKeys.add(key);
      if (!perChannel[a.canal]) perChannel[a.canal] = new Set();
      perChannel[a.canal].add(key);
    }

    const counts: Record<string, number> = {};
    for (const canal of uniqueCanals) {
      counts[canal] = perChannel[canal]?.size ?? 0;
    }

    return { filteredCount: allKeys.size, channelAnomalyCounts: counts };
  }, [anomalies, severityFilter, typeFilter, canalFilter, uniqueCanals]);

  // Severity toggles
  const toggleSeverity = useCallback((key: "errors" | "warnings" | "infos") => {
    setSeverityFilter((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const allSeverities = severityFilter.errors && severityFilter.warnings && severityFilter.infos;
  const toggleAllSeverities = useCallback(() => {
    const next = !allSeverities;
    setSeverityFilter({ errors: next, warnings: next, infos: next });
  }, [allSeverities]);

  // Type toggles
  const toggleType = useCallback((type: string) => {
    setTypeFilter((prev) => ({ ...prev, [type]: !prev[type] }));
  }, []);

  // Toggle all types within a category (select all / deselect all)
  const toggleCategoryTypes = useCallback((catTypes: string[]) => {
    setTypeFilter((prev) => {
      const allChecked = catTypes.every((t) => prev[t]);
      const next = !allChecked;
      const update = { ...prev };
      for (const t of catTypes) update[t] = next;
      return update;
    });
  }, []);

  const allTypes = Object.values(typeFilter).every(Boolean);
  const toggleAllTypes = useCallback(() => {
    const next = !allTypes;
    setTypeFilter((prev) => Object.fromEntries(Object.keys(prev).map((k) => [k, next])));
  }, [allTypes]);

  // Canal toggles
  const toggleCanal = useCallback((canal: string) => {
    setCanalFilter((prev) => {
      const next = new Set(prev);
      if (next.has(canal)) next.delete(canal);
      else next.add(canal);
      return next;
    });
  }, []);

  const allCanals = uniqueCanals.length > 0 && uniqueCanals.every((c) => canalFilter.has(c));
  const toggleAllCanals = useCallback(() => {
    if (allCanals) {
      setCanalFilter(new Set());
    } else {
      setCanalFilter(new Set(uniqueCanals));
    }
  }, [allCanals, uniqueCanals]);

  // Generate handler
  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    try {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

      const sections: AnomalyPdfSections = {
        ...severityFilter,
        types: typeFilter,
        channels: canalFilter,
      };

      generateAnomalyPdf({
        anomalies,
        sections,
        groupBy,
        dateRange,
        generatedAt: fmtDate(new Date()),
        channels: uniqueCanals,
      });

      setOpen(false);
    } finally {
      setGenerating(false);
    }
  }, [anomalies, severityFilter, typeFilter, canalFilter, groupBy, dateRange, uniqueCanals]);

  // Empty state: button disabled (use visual card count to match main panel)
  if (countVisualCards(anomalies) === 0) {
    return (
      <Button variant="outline" size="sm" disabled aria-label="Aucune anomalie à exporter" title="Aucune anomalie à exporter">
        <FileText className="mr-2 h-4 w-4" />
        Export PDF
      </Button>
    );
  }

  /* ── V2 popover content ───────────────────────────────────────── */
  if (isV2) {
    return (
      <Popover.Root open={open} onOpenChange={handleOpenChange}>
        <Popover.Trigger asChild>
          <Button variant="outline" size="sm" aria-label="Exporter les anomalies en PDF">
            <FileText className="mr-2 h-4 w-4" />
            Export PDF
          </Button>
        </Popover.Trigger>

        <Popover.Portal>
          <Popover.Content
            className="z-50 w-80 max-h-[90vh] overflow-y-auto rounded-xl border bg-popover text-popover-foreground shadow-lg"
            sideOffset={8}
            align="end"
            style={{ fontFamily: "Inter, system-ui, sans-serif" }}
          >
            {/* Header */}
            <div className="flex flex-col gap-1 px-5 pt-4 pb-3">
              <h3 className="text-[13px] font-bold text-foreground">
                RAPPORT D&apos;ANOMALIES
              </h3>
              <p className="text-[11px] text-muted-foreground">
                Sélectionnez les filtres et le regroupement
              </p>
            </div>

            <V2Separator />

            {/* Severities */}
            <div className="flex flex-col gap-2 px-5 py-3">
              <div className="flex items-center justify-between">
                <V2SectionLabel>Sévérités</V2SectionLabel>
                <V2ToggleLink allChecked={allSeverities} onToggle={toggleAllSeverities} />
              </div>
              <div className="flex flex-col gap-1.5">
                {([
                  { key: "errors" as const, label: "Erreurs", color: SEVERITY_COLORS.errors },
                  { key: "warnings" as const, label: "Avertissements", color: SEVERITY_COLORS.warnings },
                  { key: "infos" as const, label: "Infos", color: SEVERITY_COLORS.infos },
                ] as const).map(({ key, label, color }) => (
                  <label key={key} className="flex items-center gap-2 cursor-pointer">
                    <V2ColorCheckbox
                      checked={severityFilter[key]}
                      onCheckedChange={() => toggleSeverity(key)}
                      fillColor={color}
                    />
                    <span className="text-[12px] font-medium text-foreground">{label}</span>
                  </label>
                ))}
              </div>
            </div>

            <V2Separator />

            {/* Categories */}
            <div className="flex flex-col gap-2 px-5 py-3">
              <div className="flex items-center justify-between">
                <V2SectionLabel>Catégories</V2SectionLabel>
                <V2ToggleLink allChecked={allTypes} onToggle={toggleAllTypes} />
              </div>
              <div className="flex flex-col gap-1">
                {Object.entries(ANOMALY_CATEGORIES).map(([key, cat]) => {
                  const checkedCount = cat.types.filter((t) => typeFilter[t]).length;
                  const allCatChecked = checkedCount === cat.types.length;
                  const noneCatChecked = checkedCount === 0;
                  const parentChecked = allCatChecked ? true : noneCatChecked ? false : ("indeterminate" as const);
                  const isExpanded = expandedCats.has(key);
                  return (
                    <div key={key} className="flex flex-col">
                      <div className="flex items-center gap-1.5 cursor-pointer">
                        <button
                          type="button"
                          onClick={() => setExpandedCats((prev) => {
                            const next = new Set(prev);
                            if (next.has(key)) next.delete(key); else next.add(key);
                            return next;
                          })}
                          className="p-0 bg-transparent border-none"
                        >
                          <ChevronRight className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                        </button>
                        <V2ColorCheckbox
                          checked={parentChecked}
                          onCheckedChange={() => toggleCategoryTypes(cat.types)}
                          fillColor={TEAL}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <span
                          className="text-[11px] font-medium text-foreground flex-1"
                          onClick={() => setExpandedCats((prev) => {
                            const next = new Set(prev);
                            if (next.has(key)) next.delete(key); else next.add(key);
                            return next;
                          })}
                        >
                          {cat.label}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          ({checkedCount}/{cat.types.length})
                        </span>
                      </div>
                      {isExpanded && (
                        <div className="flex flex-col gap-1 ml-8 mt-1">
                          {cat.types.map((t) => (
                            <label key={t} className="flex items-center gap-2 cursor-pointer">
                              <V2ColorCheckbox
                                checked={!!typeFilter[t]}
                                onCheckedChange={() => toggleType(t)}
                                fillColor={TEAL}
                              />
                              <span className="text-[10px] text-foreground">
                                {ANOMALY_TYPE_LABELS[t] ?? t}
                              </span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <V2Separator />

            {/* Channels */}
            <div className="flex flex-col gap-2 px-5 py-3">
              <div className="flex items-center justify-between">
                <V2SectionLabel>Canaux</V2SectionLabel>
                <V2ToggleLink allChecked={allCanals} onToggle={toggleAllCanals} />
              </div>
              <div className="flex flex-col gap-1.5">
                {uniqueCanals.map((canal) => {
                  const color = CHANNEL_COLORS[canal] ?? "#6B7280";
                  const count = channelAnomalyCounts[canal] ?? 0;
                  return (
                    <label key={canal} className="flex items-center gap-2 cursor-pointer">
                      <V2ColorCheckbox
                        checked={canalFilter.has(canal)}
                        onCheckedChange={() => toggleCanal(canal)}
                        fillColor={color}
                      />
                      <span className="text-[11px] font-medium text-foreground">
                        {getChannelMeta(canal).label}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        ({count})
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>

            <V2Separator />

            {/* Grouping */}
            <div className="flex flex-col gap-2 px-5 py-3">
              <V2SectionLabel>Regroupement</V2SectionLabel>
              <RadioGroup.Root
                value={groupBy}
                onValueChange={(v) => setGroupBy(v as "severity" | "canal" | "type")}
                className="flex flex-col gap-1.5"
              >
                {([
                  { value: "severity", label: "Par sévérité" },
                  { value: "canal", label: "Par canal" },
                  { value: "type", label: "Par type" },
                ] as const).map(({ value, label }) => (
                  <label key={value} className="flex items-center gap-2 cursor-pointer">
                    <RadioGroup.Item
                      value={value}
                      className={`h-3.5 w-3.5 rounded-full border bg-transparent ${groupBy === value ? "" : "border-slate-300 dark:border-slate-500"}`}
                      style={{ borderColor: groupBy === value ? TEAL : undefined }}
                    >
                      <RadioGroup.Indicator className="flex items-center justify-center">
                        <span className="block h-2 w-2 rounded-full" style={{ backgroundColor: TEAL }} />
                      </RadioGroup.Indicator>
                    </RadioGroup.Item>
                    <span
                      className={`text-[11px] ${groupBy === value ? "text-foreground font-medium" : "text-muted-foreground"}`}
                    >
                      {label}
                    </span>
                  </label>
                ))}
              </RadioGroup.Root>
            </div>

            <V2Separator />

            {/* Period */}
            <div className="px-5 py-3">
              <span className="text-[11px] text-muted-foreground">
                Période : {fmtDate(dateRange.from)} — {fmtDate(dateRange.to)}
              </span>
            </div>

            <V2Separator />

            {/* Generate button */}
            <div className="px-5 py-3">
              <button
                type="button"
                onClick={handleGenerate}
                disabled={filteredCount === 0 || generating}
                className="w-full flex items-center justify-center gap-2 rounded-lg py-2.5 text-[12px] font-semibold text-white transition-opacity disabled:opacity-50"
                style={{ backgroundColor: TEAL }}
                aria-busy={generating}
              >
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Génération...
                  </>
                ) : (
                  <>
                    <FileText className="h-4 w-4" />
                    Générer le PDF ({filteredCount} anomalie{filteredCount > 1 ? "s" : ""})
                  </>
                )}
              </button>
            </div>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    );
  }

  /* ── V1 popover content (original) ─────────────────────────────── */
  return (
    <Popover.Root open={open} onOpenChange={handleOpenChange}>
      <Popover.Trigger asChild>
        <Button variant="outline" size="sm" aria-label="Exporter les anomalies en PDF">
          <FileText className="mr-2 h-4 w-4" />
          Export PDF
        </Button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          className="z-50 w-80 max-h-[70vh] overflow-y-auto rounded-lg border bg-popover p-4 text-popover-foreground shadow-md"
          sideOffset={8}
          align="end"
        >
          {/* Title */}
          <div className="mb-3">
            <h3 className="text-sm font-bold">RAPPORT D&apos;ANOMALIES</h3>
            <p className="text-xs text-muted-foreground">
              Sélectionnez les filtres et le regroupement
            </p>
          </div>

          {/* Severity filters */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Sévérités</span>
              <ToggleAllButton allChecked={allSeverities} onToggle={toggleAllSeverities} />
            </div>
            <div className="space-y-1">
              <CheckboxItem checked={severityFilter.errors} onCheckedChange={() => toggleSeverity("errors")} label={`${SEVERITY_META.error.label}s`} />
              <CheckboxItem checked={severityFilter.warnings} onCheckedChange={() => toggleSeverity("warnings")} label={`${SEVERITY_META.warning.label}s`} />
              <CheckboxItem checked={severityFilter.infos} onCheckedChange={() => toggleSeverity("infos")} label={`${SEVERITY_META.info.label}s`} />
            </div>
          </div>

          <div className="h-px bg-border" />

          {/* Category / type filters */}
          <div className="my-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Catégories</span>
              <ToggleAllButton allChecked={allTypes} onToggle={toggleAllTypes} />
            </div>
            <div className="space-y-1">
              {Object.entries(ANOMALY_CATEGORIES).map(([key, cat]) => {
                const checkedCount = cat.types.filter((t) => typeFilter[t]).length;
                const allChecked = checkedCount === cat.types.length;
                const noneChecked = checkedCount === 0;
                const parentChecked = allChecked ? true : noneChecked ? false : "indeterminate";
                return (
                  <details key={key} className="group">
                    <summary className="flex items-center gap-2 cursor-pointer text-sm list-none">
                      <ChevronRight className="h-4 w-4 shrink-0 transition-transform group-open:rotate-90" />
                      <Checkbox.Root
                        checked={parentChecked}
                        onCheckedChange={() => toggleCategoryTypes(cat.types)}
                        className={CHECKBOX_CLASS}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Checkbox.Indicator className="duration-0">
                          {parentChecked === "indeterminate" ? (
                            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                              <rect x="2" y="4.5" width="6" height="1.5" rx="0.5" fill="currentColor" />
                            </svg>
                          ) : (
                            CHECK_SVG
                          )}
                        </Checkbox.Indicator>
                      </Checkbox.Root>
                      <span className="font-medium">{cat.label}</span>
                      <span className="text-xs text-muted-foreground">({checkedCount}/{cat.types.length})</span>
                    </summary>
                    <div className="ml-6 mt-1 mb-1 space-y-0.5">
                      {cat.types.map((t) => (
                        <label key={t} className="flex items-center gap-2 cursor-pointer text-xs text-muted-foreground">
                          <Checkbox.Root
                            checked={typeFilter[t]}
                            onCheckedChange={() => toggleType(t)}
                            className={CHECKBOX_CLASS}
                          >
                            <Checkbox.Indicator className="duration-0">{CHECK_SVG}</Checkbox.Indicator>
                          </Checkbox.Root>
                          {ANOMALY_TYPE_LABELS[t] ?? t}
                        </label>
                      ))}
                    </div>
                  </details>
                );
              })}
            </div>
          </div>

          <div className="h-px bg-border" />

          {/* Canal filters */}
          {uniqueCanals.length > 1 && (
            <>
              <div className="my-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold uppercase text-muted-foreground">Canaux</span>
                  <ToggleAllButton allChecked={allCanals} onToggle={toggleAllCanals} />
                </div>
                <div className="space-y-1">
                  {uniqueCanals.map((canal) => (
                    <CheckboxItem
                      key={canal}
                      checked={canalFilter.has(canal)}
                      onCheckedChange={() => toggleCanal(canal)}
                      label={getChannelMeta(canal).label}
                    />
                  ))}
                </div>
              </div>
              <div className="h-px bg-border" />
            </>
          )}

          {/* Grouping radio */}
          <div className="my-3">
            <span className="text-xs font-semibold uppercase text-muted-foreground block mb-1">Regroupement</span>
            <RadioGroup.Root
              value={groupBy}
              onValueChange={(v) => setGroupBy(v as "severity" | "canal" | "type")}
              className="space-y-1"
            >
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <RadioGroup.Item value="severity" className={RADIO_CLASS}>
                  <RadioGroup.Indicator className={RADIO_INDICATOR_CLASS} />
                </RadioGroup.Item>
                Par sévérité
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <RadioGroup.Item value="canal" className={RADIO_CLASS}>
                  <RadioGroup.Indicator className={RADIO_INDICATOR_CLASS} />
                </RadioGroup.Item>
                Par canal
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <RadioGroup.Item value="type" className={RADIO_CLASS}>
                  <RadioGroup.Indicator className={RADIO_INDICATOR_CLASS} />
                </RadioGroup.Item>
                Par type
              </label>
            </RadioGroup.Root>
          </div>

          <div className="h-px bg-border" />

          {/* Period display */}
          <div className="my-3 text-xs text-muted-foreground">
            <p>
              Période : {fmtDate(dateRange.from)} — {fmtDate(dateRange.to)}
            </p>
            <p className="mt-0.5 italic">Correspond au filtre actif</p>
          </div>

          {/* Generate button */}
          <Button
            onClick={handleGenerate}
            disabled={filteredCount === 0 || generating}
            className="w-full"
            aria-busy={generating}
          >
            {generating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Génération...
              </>
            ) : (
              <>
                <FileText className="mr-2 h-4 w-4" />
                Générer le PDF ({filteredCount} anomalie{filteredCount > 1 ? "s" : ""})
              </>
            )}
          </Button>

          <Popover.Arrow className="fill-border" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
