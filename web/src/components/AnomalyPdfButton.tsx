"use client";

import { useState, useCallback, useMemo } from "react";
import { FileText, Loader2 } from "lucide-react";
import * as Popover from "@radix-ui/react-popover";
import * as Checkbox from "@radix-ui/react-checkbox";
import * as RadioGroup from "@radix-ui/react-radio-group";
import { Button } from "@/components/ui/button";
import { generateAnomalyPdf } from "@/lib/generateAnomalyPdf";
import type { AnomalyPdfSections } from "@/lib/generateAnomalyPdf";
import { ANOMALY_CATEGORIES, ANOMALY_TYPE_LABELS, SEVERITY_META } from "@/components/AnomaliesPanel";
import { fmtDate } from "@/lib/pdfStyles";
import { getChannelMeta } from "@/lib/channels";
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

export default function AnomalyPdfButton({ anomalies, dateRange }: AnomalyPdfButtonProps) {
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

  // Unique canals present in anomalies
  const uniqueCanals = useMemo(
    () => Array.from(new Set(anomalies.map((a) => a.canal))).sort(),
    [anomalies],
  );

  // Reset canal filter when popover opens (include all canals)
  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      if (isOpen) {
        setCanalFilter(new Set(uniqueCanals));
      }
      setOpen(isOpen);
    },
    [uniqueCanals],
  );

  // Compute filtered count
  const filteredCount = useMemo(() => {
    return anomalies.filter((a) => {
      if (a.severity === "error" && !severityFilter.errors) return false;
      if (a.severity === "warning" && !severityFilter.warnings) return false;
      if (a.severity === "info" && !severityFilter.infos) return false;
      if (!canalFilter.has(a.canal)) return false;
      if (a.type in typeFilter && !typeFilter[a.type]) return false;
      return true;
    }).length;
  }, [anomalies, severityFilter, typeFilter, canalFilter]);

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

  // Empty state: button disabled
  if (anomalies.length === 0) {
    return (
      <Button variant="outline" size="sm" disabled aria-label="Aucune anomalie à exporter" title="Aucune anomalie à exporter">
        <FileText className="mr-2 h-4 w-4" />
        Export PDF
      </Button>
    );
  }

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
