"use client";

import { useState } from "react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { DayPicker } from "react-day-picker";
import "react-day-picker/style.css";
import * as Popover from "@radix-ui/react-popover";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { Calendar, X } from "lucide-react";
import type { DateRange } from "@/lib/datePresets";
import {
  DEFAULT_PRESET,
  PRESET_LABELS,
  getPresetRange,
  type PresetKey,
} from "@/lib/datePresets";

interface PeriodFilterProps {
  dateRange: DateRange;
  onChange: (range: DateRange) => void;
}

/**
 * Period filter: preset toggle buttons + custom calendar picker.
 */
export default function PeriodFilter({ dateRange, onChange }: PeriodFilterProps) {
  const [activePreset, setActivePreset] = useState<PresetKey>(DEFAULT_PRESET);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [customFrom, setCustomFrom] = useState<Date | undefined>(undefined);
  const [customTo, setCustomTo] = useState<Date | undefined>(undefined);

  const handlePresetChange = (value: string) => {
    if (!value || value === "custom") return;
    const key = value as Exclude<PresetKey, "custom">;
    setActivePreset(key);
    setCustomFrom(undefined);
    setCustomTo(undefined);
    onChange(getPresetRange(key));
  };

  const handleApplyCustom = () => {
    if (customFrom && customTo) {
      setActivePreset("custom");
      onChange({ from: customFrom, to: customTo });
      setPopoverOpen(false);
    }
  };

  const handleReset = () => {
    setActivePreset(DEFAULT_PRESET);
    setCustomFrom(undefined);
    setCustomTo(undefined);
    onChange(getPresetRange(DEFAULT_PRESET));
  };

  const formatShort = (d: Date) => format(d, "dd/MM/yyyy", { locale: fr });

  return (
    <div className="sticky top-0 z-10 bg-background border-b shadow-sm py-3 -mx-4 px-4">
      <div className="flex items-center gap-2 flex-wrap">
        <ToggleGroup.Root
          type="single"
          value={activePreset === "custom" ? "" : activePreset}
          onValueChange={handlePresetChange}
          className="inline-flex rounded-md border"
          aria-label="Sélection de la période"
        >
          {(Object.keys(PRESET_LABELS) as Exclude<PresetKey, "custom">[]).map(
            (key) => (
              <ToggleGroup.Item
                key={key}
                value={key}
                className={`px-3 py-1.5 text-sm font-medium transition-colors first:rounded-l-md last:rounded-r-md border-r last:border-r-0 ${
                  activePreset === key
                    ? "bg-foreground text-background"
                    : "bg-background text-muted-foreground hover:bg-muted"
                }`}
              >
                {PRESET_LABELS[key]}
              </ToggleGroup.Item>
            ),
          )}
        </ToggleGroup.Root>

        <Popover.Root open={popoverOpen} onOpenChange={setPopoverOpen}>
          <Popover.Trigger asChild>
            <button
              type="button"
              className={`inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md border transition-colors ${
                activePreset === "custom"
                  ? "bg-foreground text-background"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
              aria-label="Choisir une période personnalisée"
            >
              <Calendar className="h-4 w-4" />
              Custom
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              className="z-50 rounded-lg border bg-popover p-4 shadow-md"
              sideOffset={8}
              align="start"
            >
              <DayPicker
                mode="range"
                locale={fr}
                selected={
                  customFrom && customTo
                    ? { from: customFrom, to: customTo }
                    : customFrom
                      ? { from: customFrom, to: undefined }
                      : undefined
                }
                onSelect={(range) => {
                  setCustomFrom(range?.from ?? undefined);
                  setCustomTo(range?.to ?? undefined);
                }}
              />
              <div className="mt-2 flex justify-end">
                <button
                  type="button"
                  disabled={!customFrom || !customTo}
                  onClick={handleApplyCustom}
                  className="rounded-md bg-foreground px-4 py-1.5 text-sm font-medium text-background disabled:opacity-50"
                >
                  Appliquer
                </button>
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>

      <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
        <span>
          Période : {formatShort(dateRange.from)} — {formatShort(dateRange.to)}
        </span>
        <button
          type="button"
          onClick={handleReset}
          className="inline-flex items-center gap-0.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Réinitialiser la période"
        >
          <X className="h-3 w-3" />
          Réinitialiser
        </button>
      </div>
    </div>
  );
}
