"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { FileText, Loader2, Check } from "lucide-react";
import * as Popover from "@radix-ui/react-popover";
import * as Checkbox from "@radix-ui/react-checkbox";
import * as RadioGroup from "@radix-ui/react-radio-group";
import { Button } from "@/components/ui/button";
import { useNewDesign } from "@/hooks/useNewDesign";
import { generateFlashPdf } from "@/lib/generateFlashPdf";
import type { FlashPdfSections, ChartImages } from "@/lib/generateFlashPdf";
import { renderChartImages, getChannelColor } from "@/lib/captureCharts";
import type { PieChartData, BarChartData } from "@/lib/captureCharts";
import { channelLabel } from "@/lib/pdfStyles";
import type { Summary, Anomaly } from "@/lib/types";
import type { DateRange } from "@/lib/datePresets";

interface FlashPdfButtonProps {
  summary: Summary;
  dateRange: DateRange;
  htTtcMode: "ht" | "ttc";
  countryNames: Record<string, string>;
  anomalies: Anomaly[];
}

const SECTION_DEFS: { key: keyof FlashPdfSections; label: string; desc: string }[] = [
  { key: "kpis", label: "Indicateurs clés (KPIs)", desc: "CA, net vendeur, transactions, taux" },
  { key: "profitability", label: "Rentabilité par canal", desc: "Commissions, abonnements, net vendeur HT" },
  { key: "ventilation", label: "Ventilation CA Produits / FdP", desc: "Répartition produits vs frais de port" },
  { key: "tva", label: "Fiscalité — TVA collectée", desc: "Détail par canal et par pays/taux" },
  { key: "geo", label: "Répartition géographique", desc: "CA HT par pays, détail par canal" },
  { key: "anomalies", label: "Anomalies", desc: "Résumé par sévérité et tableau détaillé" },
];

function fmtDate(d: Date): string {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

/* ------------------------------------------------------------------ */
/*  Shared hooks & generate logic                                      */
/* ------------------------------------------------------------------ */

function useFlashPdfState(htTtcMode: "ht" | "ttc") {
  const [open, setOpen] = useState(false);
  const [sections, setSections] = useState<FlashPdfSections>({
    kpis: true,
    profitability: true,
    ventilation: true,
    tva: true,
    geo: true,
    anomalies: true,
  });
  const [mode, setMode] = useState<"ht" | "ttc">(htTtcMode);
  const [generating, setGenerating] = useState(false);

  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      if (isOpen) setMode(htTtcMode);
      setOpen(isOpen);
    },
    [htTtcMode],
  );

  const toggleSection = useCallback((key: keyof FlashPdfSections) => {
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const allChecked = Object.values(sections).every(Boolean);
  const noneChecked = Object.values(sections).every((v) => !v);

  const toggleAll = useCallback(() => {
    const next = !allChecked;
    setSections({ kpis: next, profitability: next, ventilation: next, tva: next, geo: next, anomalies: next });
  }, [allChecked]);

  return {
    open, setOpen, sections, mode, setMode, generating, setGenerating,
    handleOpenChange, toggleSection, allChecked, noneChecked, toggleAll,
  };
}

function useGenerateHandler(
  summary: Summary,
  dateRange: DateRange,
  mode: "ht" | "ttc",
  countryNames: Record<string, string>,
  sections: FlashPdfSections,
  anomalies: Anomaly[],
  setGenerating: (v: boolean) => void,
  setOpen: (v: boolean) => void,
) {
  return useCallback(async () => {
    setGenerating(true);
    try {
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

      const channels = Object.keys(summary.ca_par_canal).sort();

      let chartImages: ChartImages | undefined;
      try {
        const totalCaHt = channels.reduce((s, c) => s + (summary.ca_par_canal[c]?.ht ?? 0), 0);
        const totalCommHt = channels.reduce((s, c) => s + (summary.commissions_par_canal[c]?.ht ?? 0), 0);

        const revenuePieData: PieChartData[] = channels.map((c) => ({
          label: channelLabel(c),
          value: summary.ca_par_canal[c]?.ht ?? 0,
          color: getChannelColor(c),
        }));

        const commissionPieData: PieChartData[] = channels.map((c) => ({
          label: channelLabel(c),
          value: summary.commissions_par_canal[c]?.ht ?? 0,
          color: getChannelColor(c),
        }));

        const ventilationData: BarChartData[] = channels.map((c) => ({
          label: channelLabel(c),
          segments: [
            { value: summary.ventilation_ca_par_canal[c]?.produits_ht ?? 0, color: getChannelColor(c), label: "Produits HT" },
            { value: summary.ventilation_ca_par_canal[c]?.port_ht ?? 0, color: getChannelColor(c) + "4D", label: "Frais de port HT" },
          ],
        }));
        const maxVentilation = Math.max(...channels.map((c) => summary.ventilation_ca_par_canal[c]?.total_ht ?? 0));

        chartImages = renderChartImages({
          revenuePie: { data: revenuePieData, total: totalCaHt, centerLabel: "CA HT" },
          commissionPie: { data: commissionPieData, total: totalCommHt, centerLabel: "Commissions HT" },
          ventilation: { data: ventilationData, maxValue: maxVentilation },
        });
      } catch {
        chartImages = undefined;
      }
      generateFlashPdf({
        summary,
        dateRange,
        mode,
        countryNames,
        channels,
        sections,
        generatedAt: new Date(),
        anomalies,
        chartImages,
      });

      setOpen(false);
    } finally {
      setGenerating(false);
    }
  }, [summary, dateRange, mode, countryNames, sections, anomalies, setGenerating, setOpen]);
}

/* ------------------------------------------------------------------ */
/*  V2 Popover — matches .pen "Popover Flash PDF" design               */
/* ------------------------------------------------------------------ */

function FlashPdfButtonV2({
  summary,
  dateRange,
  htTtcMode,
  countryNames,
  anomalies,
}: FlashPdfButtonProps) {
  const {
    open, setOpen, sections, mode, setMode, generating, setGenerating,
    handleOpenChange, toggleSection, allChecked, noneChecked, toggleAll,
  } = useFlashPdfState(htTtcMode);

  const handleGenerate = useGenerateHandler(
    summary, dateRange, mode, countryNames, sections, anomalies, setGenerating, setOpen,
  );

  // Click-outside-to-close via ref
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (
        popoverRef.current && !popoverRef.current.contains(target) &&
        triggerRef.current && !triggerRef.current.contains(target)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open, setOpen]);

  const TEAL = "#0D6E6E";

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => handleOpenChange(!open)}
        aria-label="Générer un PDF Flash E-Commerce"
        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        <FileText className="h-4 w-4" />
        Flash PDF
      </button>

      {/* Popover */}
      {open && (
        <div
          ref={popoverRef}
          className="absolute right-0 top-full z-50 mt-2 w-80 rounded-xl bg-white shadow-lg dark:bg-slate-800"
          style={{ borderRadius: 12 }}
        >
          {/* Header — py-4 px-5 = padding [16, 20] */}
          <div className="flex flex-col gap-1 px-5 pt-4 pb-3">
            <h3
              className="font-bold tracking-wide text-foreground"
              style={{ fontFamily: "Inter, sans-serif", fontSize: 13 }}
            >
              FLASH E-COMMERCE
            </h3>
            <p className="text-muted-foreground" style={{ fontFamily: "Inter, sans-serif", fontSize: 11 }}>
              Sélectionnez les sections à inclure
            </p>
          </div>

          {/* Separator */}
          <div className="h-px w-full bg-border" />

          {/* Checkboxes section — padding [12, 20], gap 10 */}
          <div className="flex flex-col gap-2.5 px-5 py-3">
            {SECTION_DEFS.map((sec) => (
              <label
                key={sec.key}
                className="flex cursor-pointer items-start gap-2.5"
              >
                {/* Custom checkbox matching .pen: 16x16, cornerRadius 3, teal when checked */}
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={sections[sec.key]}
                  onClick={() => toggleSection(sec.key)}
                  className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-[3px] transition-colors ${!sections[sec.key] ? "border-[1.5px] border-slate-300 dark:border-slate-500" : ""}`}
                  style={{
                    backgroundColor: sections[sec.key] ? TEAL : "transparent",
                  }}
                >
                  {sections[sec.key] && (
                    <Check className="h-3 w-3 text-white" strokeWidth={2.5} />
                  )}
                </button>
                <div className="flex flex-col gap-0.5 leading-tight">
                  <span className="text-foreground" style={{ fontFamily: "Inter, sans-serif", fontSize: 12, fontWeight: 500 }}>
                    {sec.label}
                  </span>
                  <span className="text-muted-foreground" style={{ fontFamily: "Inter, sans-serif", fontSize: 10 }}>
                    {sec.desc}
                  </span>
                </div>
              </label>
            ))}

            {/* Toggle all link */}
            <button
              type="button"
              onClick={toggleAll}
              className="mt-0.5 self-start text-left transition-opacity hover:opacity-80"
              style={{ fontFamily: "Inter, sans-serif", fontSize: 11, color: TEAL }}
            >
              {allChecked ? "Tout désélectionner" : "Tout sélectionner"}
            </button>
          </div>

          {/* Separator */}
          <div className="h-px w-full bg-border" />

          {/* Radio HT / TTC — padding [12, 20], gap 16 */}
          <div className="flex items-center gap-4 px-5 py-3">
            {(["ht", "ttc"] as const).map((val) => {
              const isActive = mode === val;
              return (
                <button
                  key={val}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  onClick={() => setMode(val)}
                  className="flex items-center gap-1.5 cursor-pointer"
                >
                  {/* Radio outer circle: 16x16 */}
                  <span
                    className="flex h-4 w-4 items-center justify-center rounded-full border-[1.5px] border-slate-300 dark:border-slate-500 bg-transparent"
                  >
                    {isActive && (
                      <span
                        className="block h-2 w-2 rounded-full"
                        style={{ backgroundColor: TEAL }}
                      />
                    )}
                  </span>
                  <span
                    className={isActive ? "text-foreground" : "text-muted-foreground"}
                    style={{ fontFamily: "Inter, sans-serif", fontSize: 12, fontWeight: 500 }}
                  >
                    {val.toUpperCase()}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Separator */}
          <div className="h-px w-full bg-border" />

          {/* Period display — padding [12, 20], gap 4 */}
          <div className="flex flex-col gap-1 px-5 py-3">
            <p className="text-muted-foreground" style={{ fontFamily: "Inter, sans-serif", fontSize: 11 }}>
              Période : {fmtDate(dateRange.from)} — {fmtDate(dateRange.to)}
            </p>
            <p className="text-muted-foreground" style={{ fontFamily: "Inter, sans-serif", fontSize: 10, fontStyle: "italic" }}>
              (Correspond au filtre actif)
            </p>
          </div>

          {/* Separator */}
          <div className="h-px w-full bg-border" />

          {/* Generate button — padding [12, 20] */}
          <div className="px-5 py-3">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={noneChecked || generating}
              className="flex w-full items-center justify-center gap-2 transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                height: 40,
                borderRadius: 8,
                backgroundColor: TEAL,
                fontFamily: "Inter, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#FFFFFF",
              }}
              aria-busy={generating}
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-white" />
                  Génération...
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4 text-white" />
                  Générer le PDF
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  V1 Popover — original Radix-based implementation                   */
/* ------------------------------------------------------------------ */

function FlashPdfButtonV1({
  summary,
  dateRange,
  htTtcMode,
  countryNames,
  anomalies,
}: FlashPdfButtonProps) {
  const {
    open, setOpen, sections, mode, setMode, generating, setGenerating,
    handleOpenChange, toggleSection, allChecked, noneChecked, toggleAll,
  } = useFlashPdfState(htTtcMode);

  const handleGenerate = useGenerateHandler(
    summary, dateRange, mode, countryNames, sections, anomalies, setGenerating, setOpen,
  );

  return (
    <Popover.Root open={open} onOpenChange={handleOpenChange}>
      <Popover.Trigger asChild>
        <Button variant="secondary" aria-label="Générer un PDF Flash E-Commerce">
          <FileText className="mr-2 h-4 w-4" />
          Flash PDF
        </Button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          className="z-50 w-80 rounded-lg border bg-popover p-4 text-popover-foreground shadow-md"
          sideOffset={8}
          align="end"
        >
          {/* Title */}
          <div className="mb-3">
            <h3 className="text-sm font-bold">FLASH E-COMMERCE</h3>
            <p className="text-xs text-muted-foreground">
              Sélectionnez les sections à inclure
            </p>
          </div>

          {/* Checkboxes */}
          <div className="space-y-2">
            {SECTION_DEFS.map((sec) => (
              <label
                key={sec.key}
                className="flex items-start gap-2 cursor-pointer"
              >
                <Checkbox.Root
                  checked={sections[sec.key]}
                  onCheckedChange={() => toggleSection(sec.key)}
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-input bg-background duration-0 data-[state=checked]:bg-foreground data-[state=checked]:text-background"
                >
                  <Checkbox.Indicator className="duration-0">
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                      <path
                        d="M2 5L4 7L8 3"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </Checkbox.Indicator>
                </Checkbox.Root>
                <div className="leading-tight">
                  <span className="text-sm font-medium">{sec.label}</span>
                  <span className="block text-xs text-muted-foreground">
                    {sec.desc}
                  </span>
                </div>
              </label>
            ))}
          </div>

          {/* Select all / deselect */}
          <button
            type="button"
            onClick={toggleAll}
            className="mt-2 text-xs text-muted-foreground underline hover:text-foreground transition-colors"
          >
            {allChecked ? "Tout désélectionner" : "Tout sélectionner"}
          </button>

          {/* Separator */}
          <div className="my-3 h-px bg-border" />

          {/* Radio HT / TTC */}
          <RadioGroup.Root
            value={mode}
            onValueChange={(v) => setMode(v as "ht" | "ttc")}
            className="flex gap-4"
          >
            <label className="flex items-center gap-1.5 cursor-pointer text-sm">
              <RadioGroup.Item
                value="ttc"
                className="h-4 w-4 rounded-full border border-input bg-background"
              >
                <RadioGroup.Indicator className="flex items-center justify-center after:block after:h-2 after:w-2 after:rounded-full after:bg-foreground" />
              </RadioGroup.Item>
              TTC
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer text-sm">
              <RadioGroup.Item
                value="ht"
                className="h-4 w-4 rounded-full border border-input bg-background"
              >
                <RadioGroup.Indicator className="flex items-center justify-center after:block after:h-2 after:w-2 after:rounded-full after:bg-foreground" />
              </RadioGroup.Item>
              HT
            </label>
          </RadioGroup.Root>

          {/* Separator */}
          <div className="my-3 h-px bg-border" />

          {/* Period display */}
          <div className="text-xs text-muted-foreground">
            <p>
              Période : {fmtDate(dateRange.from)} — {fmtDate(dateRange.to)}
            </p>
            <p className="mt-0.5 italic">Correspond au filtre actif</p>
          </div>

          {/* Separator */}
          <div className="my-3 h-px bg-border" />

          {/* Generate button */}
          <Button
            onClick={handleGenerate}
            disabled={noneChecked || generating}
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
                Générer le PDF
              </>
            )}
          </Button>

          <Popover.Arrow className="fill-border" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

/* ------------------------------------------------------------------ */
/*  Default export — switches V1 / V2 based on feature flag            */
/* ------------------------------------------------------------------ */

export default function FlashPdfButton(props: FlashPdfButtonProps) {
  const isV2 = useNewDesign();

  if (isV2) {
    return <FlashPdfButtonV2 {...props} />;
  }

  return <FlashPdfButtonV1 {...props} />;
}
