"use client";

import { useState, useCallback, useMemo } from "react";
import { format, startOfMonth, addMonths, subMonths, startOfWeek, addDays, isSameMonth, isSameDay, isWithinInterval, isBefore } from "date-fns";
import { fr } from "date-fns/locale";
import * as Popover from "@radix-ui/react-popover";
import { Calendar } from "lucide-react";
import type { DateRange, PresetKey } from "@/lib/datePresets";
import { getPresetRange } from "@/lib/datePresets";

/* ── Design tokens from .pen spec ── */
const C = {
  dark: "#1E293B",
  white: "#FFFFFF",
  dimmed: "#CBD5E1",
  muted: "#94A3B8",
  gray: "#64748B",
  rangeBg: "#F1F5F9",
  border: "#E2E8F0",
} as const;

const DAY_HEADERS = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"] as const;

/** Preset pills displayed inside the calendar popover. */
const PICKER_PRESETS: { key: Exclude<PresetKey, "custom">; label: string }[] = [
  { key: "month", label: "Mois" },
  { key: "quarter", label: "Trim." },
  { key: "year", label: "Annee" },
  { key: "30d", label: "30 j." },
  { key: "90d", label: "90 j." },
];

interface V2CalendarPickerProps {
  dateRange: DateRange;
  onChange: (range: DateRange) => void;
}

/**
 * V2 Calendar Picker — Popover with preset pills, month navigation,
 * day grid with range selection, and an "Appliquer" button.
 *
 * Matches the .pen design spec exactly (300px wide, 12px corner radius,
 * Inter font, specific color tokens).
 */
export default function V2CalendarPicker({ dateRange, onChange }: V2CalendarPickerProps) {
  const [open, setOpen] = useState(false);

  // Internal state (not applied until "Appliquer")
  const [activePreset, setActivePreset] = useState<PresetKey>("month");
  const [selStart, setSelStart] = useState<Date | null>(null);
  const [selEnd, setSelEnd] = useState<Date | null>(null);
  const [displayMonth, setDisplayMonth] = useState<Date>(new Date());
  const [hoverDay, setHoverDay] = useState<Date | null>(null);

  /* ── Helpers ── */

  /** Reset internal state to reflect the current external dateRange. */
  const syncFromProps = useCallback(() => {
    setSelStart(dateRange.from);
    setSelEnd(dateRange.to);
    setDisplayMonth(dateRange.from);
  }, [dateRange]);

  /** Build the 6-week grid (42 days) starting from Monday of the week containing the 1st. */
  const calendarDays = useMemo(() => {
    const monthStart = startOfMonth(displayMonth);
    // Start on Monday (weekStartsOn: 1)
    const gridStart = startOfWeek(monthStart, { weekStartsOn: 1 });
    const days: Date[] = [];
    for (let i = 0; i < 42; i++) {
      days.push(addDays(gridStart, i));
    }
    return days;
  }, [displayMonth]);

  /** Determine the visual range for highlighting (accounts for hover during selection). */
  const visualRange = useMemo((): { from: Date; to: Date } | null => {
    if (selStart && selEnd) return { from: selStart, to: selEnd };
    if (selStart && hoverDay) {
      return isBefore(hoverDay, selStart)
        ? { from: hoverDay, to: selStart }
        : { from: selStart, to: hoverDay };
    }
    return null;
  }, [selStart, selEnd, hoverDay]);

  /* ── Handlers ── */

  const handleOpen = useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen);
      if (nextOpen) syncFromProps();
    },
    [syncFromProps],
  );

  const handlePresetClick = useCallback((key: Exclude<PresetKey, "custom">) => {
    setActivePreset(key);
    const range = getPresetRange(key);
    setSelStart(range.from);
    setSelEnd(range.to);
    setDisplayMonth(range.from);
  }, []);

  const handleDayClick = useCallback(
    (day: Date) => {
      setActivePreset("custom");
      if (!selStart || selEnd) {
        // Start new selection
        setSelStart(day);
        setSelEnd(null);
      } else {
        // Complete the range
        if (isBefore(day, selStart)) {
          setSelEnd(selStart);
          setSelStart(day);
        } else {
          setSelEnd(day);
        }
      }
    },
    [selStart, selEnd],
  );

  const handleApply = useCallback(() => {
    if (selStart && selEnd) {
      onChange({ from: selStart, to: selEnd });
      setOpen(false);
    }
  }, [selStart, selEnd, onChange]);

  const prevMonth = useCallback(() => setDisplayMonth((m) => subMonths(m, 1)), []);
  const nextMonth = useCallback(() => setDisplayMonth((m) => addMonths(m, 1)), []);

  const formatShort = (d: Date) => format(d, "dd/MM/yyyy", { locale: fr });

  const rangeComplete = selStart != null && selEnd != null;

  /* ── Render ── */

  return (
    <div className="flex items-center gap-4">
      {/* Preset pills (outside popover, inline in the PeriodFilter bar) */}
      <div className="flex items-center gap-1">
        {PICKER_PRESETS.map(({ key, label }) => {
          const isActive = activePreset === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => {
                const range = getPresetRange(key);
                setActivePreset(key);
                setSelStart(range.from);
                setSelEnd(range.to);
                setDisplayMonth(range.from);
                onChange(range);
              }}
              className="rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors"
              style={{
                backgroundColor: isActive ? C.dark : C.white,
                color: isActive ? C.white : C.gray,
                border: isActive ? "none" : `1px solid ${C.border}`,
              }}
            >
              {label}
            </button>
          );
        })}

        {/* Custom / Calendar trigger */}
        <Popover.Root open={open} onOpenChange={handleOpen}>
          <Popover.Trigger asChild>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors"
              style={{
                backgroundColor: activePreset === "custom" ? C.dark : C.white,
                color: activePreset === "custom" ? C.white : C.gray,
                border: activePreset === "custom" ? "none" : `1px solid ${C.border}`,
              }}
              aria-label="Choisir une periode personnalisee"
            >
              <Calendar className="h-3.5 w-3.5" />
              Personnalise
            </button>
          </Popover.Trigger>

          <Popover.Portal>
            <Popover.Content
              className="z-50"
              sideOffset={8}
              align="start"
            >
              {/* Calendar card: 300px, rounded-xl, white bg, outside stroke */}
              <div
                className="flex flex-col select-none"
                style={{
                  width: 300,
                  borderRadius: 12,
                  backgroundColor: C.white,
                  border: `1px solid ${C.border}`,
                  boxShadow: "0 8px 30px rgba(0,0,0,0.12)",
                  fontFamily: "Inter, sans-serif",
                }}
              >
                {/* ── Presets bar ── */}
                <div className="flex gap-1.5" style={{ padding: "12px 16px" }}>
                  {PICKER_PRESETS.map(({ key, label }) => {
                    const isActive = activePreset === key;
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => handlePresetClick(key)}
                        className="transition-colors"
                        style={{
                          padding: "6px 12px",
                          borderRadius: 6,
                          fontSize: 11,
                          fontWeight: isActive ? 600 : 400,
                          backgroundColor: isActive ? C.dark : "transparent",
                          color: isActive ? C.white : C.gray,
                          cursor: "pointer",
                          border: "none",
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>

                {/* Separator */}
                <div style={{ height: 1, backgroundColor: C.border }} />

                {/* ── Month navigation ── */}
                <div
                  className="flex items-center"
                  style={{ padding: "8px 16px" }}
                >
                  <button
                    type="button"
                    onClick={prevMonth}
                    className="flex items-center justify-center transition-colors hover:opacity-70"
                    style={{
                      width: 28,
                      color: C.gray,
                      fontSize: 18,
                      fontWeight: 600,
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                    }}
                    aria-label="Mois precedent"
                  >
                    &#8249;
                  </button>
                  <span
                    className="flex-1 text-center capitalize"
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: C.dark,
                    }}
                  >
                    {format(displayMonth, "MMMM yyyy", { locale: fr })}
                  </span>
                  <button
                    type="button"
                    onClick={nextMonth}
                    className="flex items-center justify-center transition-colors hover:opacity-70"
                    style={{
                      width: 28,
                      color: C.gray,
                      fontSize: 18,
                      fontWeight: 600,
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                    }}
                    aria-label="Mois suivant"
                  >
                    &#8250;
                  </button>
                </div>

                {/* ── Day headers ── */}
                <div
                  className="grid grid-cols-7"
                  style={{ padding: "4px 16px" }}
                >
                  {DAY_HEADERS.map((dh) => (
                    <span
                      key={dh}
                      className="text-center"
                      style={{
                        width: 32,
                        fontSize: 10,
                        fontWeight: 600,
                        color: C.muted,
                        margin: "0 auto",
                      }}
                    >
                      {dh}
                    </span>
                  ))}
                </div>

                {/* ── Day grid (6 weeks) ── */}
                <div
                  className="flex flex-col gap-0.5"
                  style={{ padding: "0 16px" }}
                >
                  {Array.from({ length: 6 }, (_, weekIdx) => (
                    <div key={weekIdx} className="grid grid-cols-7" style={{ height: 32 }}>
                      {calendarDays.slice(weekIdx * 7, weekIdx * 7 + 7).map((day) => {
                        const inMonth = isSameMonth(day, displayMonth);
                        const isStart = selStart && isSameDay(day, selStart);
                        const isEnd = selEnd && isSameDay(day, selEnd);
                        const isSelected = isStart || isEnd;
                        const inRange =
                          visualRange &&
                          !isSelected &&
                          isWithinInterval(day, {
                            start: visualRange.from,
                            end: visualRange.to,
                          });

                        // Colors per .pen spec
                        let bgColor = "transparent";
                        let textColor: string = inMonth ? C.dark : C.dimmed;
                        let fontWeight: number = 400;
                        let borderRadius = 0;

                        if (isSelected) {
                          bgColor = C.dark;
                          textColor = C.white;
                          fontWeight = 600;
                          borderRadius = 16; // full circle
                        } else if (inRange) {
                          bgColor = C.rangeBg;
                        }

                        return (
                          <button
                            key={day.toISOString()}
                            type="button"
                            onClick={() => handleDayClick(day)}
                            onMouseEnter={() => {
                              if (selStart && !selEnd) setHoverDay(day);
                            }}
                            onMouseLeave={() => setHoverDay(null)}
                            className="flex items-center justify-center transition-colors"
                            style={{
                              width: 32,
                              height: 32,
                              margin: "0 auto",
                              backgroundColor: bgColor,
                              color: textColor,
                              fontSize: 11,
                              fontWeight,
                              borderRadius,
                              border: "none",
                              cursor: "pointer",
                            }}
                          >
                            {day.getDate()}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>

                {/* Separator */}
                <div style={{ height: 1, backgroundColor: C.border }} />

                {/* ── Range display ── */}
                <div
                  className="flex items-center gap-2"
                  style={{ padding: "8px 16px" }}
                >
                  <span style={{ fontSize: 11, fontWeight: 500, color: C.dark }}>
                    {selStart ? formatShort(selStart) : "--/--/----"}
                  </span>
                  <span style={{ fontSize: 11, color: C.muted }}>
                    &mdash;
                  </span>
                  <span style={{ fontSize: 11, fontWeight: 500, color: C.dark }}>
                    {selEnd ? formatShort(selEnd) : "--/--/----"}
                  </span>
                </div>

                {/* ── Apply button ── */}
                <div style={{ padding: "4px 16px 12px 16px" }}>
                  <button
                    type="button"
                    disabled={!rangeComplete}
                    onClick={handleApply}
                    style={{
                      padding: "8px 24px",
                      borderRadius: 8,
                      backgroundColor: rangeComplete ? C.dark : C.dimmed,
                      color: C.white,
                      fontSize: 12,
                      fontWeight: 600,
                      border: "none",
                      cursor: rangeComplete ? "pointer" : "not-allowed",
                      opacity: rangeComplete ? 1 : 0.5,
                    }}
                  >
                    Appliquer
                  </button>
                </div>
              </div>
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </div>

      {/* Period info text */}
      <span
        style={{
          fontSize: 11,
          fontWeight: 500,
          color: C.dimmed,
          fontFamily: "Inter, sans-serif",
        }}
      >
        Periode : {formatShort(dateRange.from)} &mdash; {formatShort(dateRange.to)}
      </span>
    </div>
  );
}
