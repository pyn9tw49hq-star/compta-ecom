"use client";

import { useState, useCallback } from "react";
import { FileText, Loader2 } from "lucide-react";
import * as Popover from "@radix-ui/react-popover";
import * as Checkbox from "@radix-ui/react-checkbox";
import * as RadioGroup from "@radix-ui/react-radio-group";
import { Button } from "@/components/ui/button";
import { generateFlashPdf } from "@/lib/generateFlashPdf";
import type { FlashPdfSections } from "@/lib/generateFlashPdf";
import type { Summary } from "@/lib/types";
import type { DateRange } from "@/lib/datePresets";

interface FlashPdfButtonProps {
  summary: Summary;
  dateRange: DateRange;
  htTtcMode: "ht" | "ttc";
  countryNames: Record<string, string>;
}

const SECTION_DEFS: { key: keyof FlashPdfSections; label: string; desc: string }[] = [
  { key: "synthese", label: "Synthèse financière par canal", desc: "CA, remboursements, commissions" },
  { key: "ventilation", label: "Ventilation CA Produits / FdP", desc: "Répartition produits vs frais de port" },
  { key: "tva", label: "Fiscalité — TVA collectée", desc: "Détail par canal et par pays/taux" },
  { key: "geo", label: "Répartition géographique", desc: "CA HT par pays, détail par canal" },
];

function fmtDate(d: Date): string {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export default function FlashPdfButton({
  summary,
  dateRange,
  htTtcMode,
  countryNames,
}: FlashPdfButtonProps) {
  const [open, setOpen] = useState(false);
  const [sections, setSections] = useState<FlashPdfSections>({
    synthese: true,
    ventilation: true,
    tva: true,
    geo: true,
  });
  const [mode, setMode] = useState<"ht" | "ttc">(htTtcMode);
  const [generating, setGenerating] = useState(false);

  // Sync mode when popover opens
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
    setSections({ synthese: next, ventilation: next, tva: next, geo: next });
  }, [allChecked]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    try {
      // Use requestAnimationFrame to let the UI update before heavy work
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

      const channels = Object.keys(summary.ca_par_canal).sort();
      generateFlashPdf({
        summary,
        dateRange,
        mode,
        countryNames,
        channels,
        sections,
        generatedAt: new Date(),
      });

      setOpen(false);
    } finally {
      setGenerating(false);
    }
  }, [summary, dateRange, mode, countryNames, sections]);

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
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-input bg-background data-[state=checked]:bg-foreground data-[state=checked]:text-background"
                >
                  <Checkbox.Indicator>
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
