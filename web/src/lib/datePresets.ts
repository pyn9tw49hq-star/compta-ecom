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

/**
 * Compute the date range that covers all provided ISO date strings.
 * Rounds to month boundaries (start of earliest month → end of latest month).
 * Returns null if the array is empty.
 */
export function computeDataRange(dates: string[]): DateRange | null {
  if (dates.length === 0) return null;
  const timestamps = dates.map((d) => new Date(d + "T00:00:00").getTime());
  const min = new Date(Math.min(...timestamps));
  const max = new Date(Math.max(...timestamps));
  return { from: startOfMonth(min), to: endOfMonth(max) };
}
