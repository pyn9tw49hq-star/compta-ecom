import {
  startOfMonth,
  endOfMonth,
  startOfQuarter,
  endOfQuarter,
  startOfYear,
  endOfYear,
  subDays,
} from "date-fns";

export type PresetKey = "month" | "quarter" | "year" | "30d" | "90d" | "custom";

export interface DateRange {
  from: Date;
  to: Date;
}

export const DEFAULT_PRESET: Exclude<PresetKey, "custom"> = "month";

export const PRESET_LABELS: Record<Exclude<PresetKey, "custom">, string> = {
  month: "Mois",
  quarter: "Trimestre",
  year: "Année",
  "30d": "30 j.",
  "90d": "90 j.",
};

/**
 * Compute the date range for a given preset key.
 */
export function getPresetRange(key: Exclude<PresetKey, "custom">, now: Date = new Date()): DateRange {
  switch (key) {
    case "month":
      return { from: startOfMonth(now), to: endOfMonth(now) };
    case "quarter":
      return { from: startOfQuarter(now), to: endOfQuarter(now) };
    case "year":
      return { from: startOfYear(now), to: endOfYear(now) };
    case "30d":
      return { from: subDays(now, 30), to: now };
    case "90d":
      return { from: subDays(now, 90), to: now };
  }
}
