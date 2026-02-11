"use client";

import { useState, useCallback, useMemo } from "react";
import { HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import FileDropZone from "@/components/FileDropZone";
import ChannelDashboard from "@/components/ChannelDashboard";
import UnmatchedFilesPanel from "@/components/UnmatchedFilesPanel";
import ValidationBar from "@/components/ValidationBar";
import ThemeToggle from "@/components/ThemeToggle";
import HelpDrawer from "@/components/HelpDrawer";
import EntriesTable from "@/components/EntriesTable";
import AnomaliesPanel from "@/components/AnomaliesPanel";
import StatsBoard from "@/components/StatsBoard";
import DownloadButtons from "@/components/DownloadButtons";
import PeriodFilter from "@/components/PeriodFilter";
import { processFiles } from "@/lib/api";
import { CHANNEL_CONFIGS, matchFileToSlot } from "@/lib/channels";
import { DEFAULT_PRESET, getPresetRange } from "@/lib/datePresets";
import { computeSummary } from "@/lib/computeSummary";
import type { DateRange } from "@/lib/datePresets";
import type { UploadedFile, ProcessResponse, ChannelStatus, FileSlotConfig } from "@/lib/types";

export default function Home() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [dateRange, setDateRange] = useState<DateRange>(() => getPresetRange(DEFAULT_PRESET));

  const { unmatchedFiles, unmatchedGlobalIndices } = useMemo(() => {
    const unmatched: UploadedFile[] = [];
    const indices: number[] = [];
    files.forEach((f, i) => {
      const match = matchFileToSlot(f.file.name, CHANNEL_CONFIGS);
      if (!match) {
        unmatched.push(f);
        indices.push(i);
      }
    });
    return { unmatchedFiles: unmatched, unmatchedGlobalIndices: indices };
  }, [files]);

  const channelStatuses: ChannelStatus[] = useMemo(() => {
    return CHANNEL_CONFIGS.map((config) => {
      const requiredSlots = config.files.filter((f) => f.required);
      const uploadedRequiredCount = requiredSlots.filter(
        (slot) => slot.regex && files.some((f) => slot.regex!.test(f.file.name))
      ).length;
      return {
        channelKey: config.key,
        label: config.meta.label,
        requiredCount: requiredSlots.length,
        uploadedRequiredCount,
        isComplete: uploadedRequiredCount === requiredSlots.length,
      };
    });
  }, [files]);

  const missingSlots = useMemo(() => {
    const missing: { channel: string; slot: FileSlotConfig }[] = [];
    for (const config of CHANNEL_CONFIGS) {
      for (const slot of config.files) {
        if (!slot.required || !slot.regex) continue;
        const isFilled = files.some((f) => slot.regex!.test(f.file.name));
        if (!isFilled) {
          missing.push({ channel: config.key, slot });
        }
      }
    }
    return missing;
  }, [files]);

  // --- Period filtering ---
  const filteredTransactions = useMemo(() => {
    if (!result) return [];
    return result.transactions.filter((t) => {
      const d = new Date(t.date + "T00:00:00");
      return d >= dateRange.from && d <= dateRange.to;
    });
  }, [result, dateRange]);

  const filteredRefSet = useMemo(() => {
    const set = new Set<string>();
    for (const t of filteredTransactions) {
      set.add(`${t.reference}|${t.channel}`);
    }
    return set;
  }, [filteredTransactions]);

  const filteredSummary = useMemo(() => {
    if (!result) return null;
    const countryMap = result.country_names ?? {};
    return computeSummary(filteredTransactions, result.entries, countryMap);
  }, [result, filteredTransactions]);

  const filteredAnomalies = useMemo(() => {
    if (!result) return [];
    return result.anomalies.filter((a) => {
      // Structural anomalies (no reference or no canal) are always shown
      if (!a.reference || !a.canal) return true;
      // Otherwise, only show if the ref+canal is in the filtered set
      return filteredRefSet.has(`${a.reference}|${a.canal}`);
    });
  }, [result, filteredRefSet]);

  const handleAddFiles = useCallback((newFiles: UploadedFile[]) => {
    setFiles((prev) => [...prev, ...newFiles]);
    setError(null);
  }, []);

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleProcess = useCallback(async () => {
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await processFiles(files.map((f) => f.file));
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }, [files]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <HelpDrawer isOpen={isHelpOpen} onOpenChange={setIsHelpOpen} />

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">
          MAPP E-COMMERCE — Générateur d&apos;écritures comptables
        </h1>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Button variant="outline" size="icon" onClick={() => setIsHelpOpen((prev) => !prev)} aria-label="Aide sur les formats de fichiers">
            <HelpCircle className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <FileDropZone files={files} onAddFiles={handleAddFiles} />

      <div className="mt-4">
        <ChannelDashboard
          files={files}
          channelConfig={CHANNEL_CONFIGS}
          onRemoveFile={handleRemoveFile}
        />
      </div>

      <div className="mt-4">
        <UnmatchedFilesPanel
          unmatchedFiles={unmatchedFiles}
          channelConfig={CHANNEL_CONFIGS}
          missingSlots={missingSlots}
          onRemoveFile={(unmatchedIndex) => {
            handleRemoveFile(unmatchedGlobalIndices[unmatchedIndex]);
          }}
          onOpenHelp={() => setIsHelpOpen(true)}
        />
      </div>

      <div className="mt-4">
        <ValidationBar
          channelStatuses={channelStatuses}
          hasFiles={files.length > 0}
          isLoading={loading}
          onGenerate={handleProcess}
        />
      </div>

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-200"
        >
          {error}
        </div>
      )}

      {result && (
        <Tabs defaultValue="ecritures" className="mt-6">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <TabsList>
              <TabsTrigger value="ecritures">Écritures</TabsTrigger>
              <TabsTrigger value="anomalies">
                Anomalies{filteredAnomalies.length > 0 && ` (${filteredAnomalies.length})`}
              </TabsTrigger>
              <TabsTrigger value="resume">Résumé</TabsTrigger>
            </TabsList>
            <DownloadButtons
              files={files.map((f) => f.file)}
              entries={result.entries}
              anomalies={result.anomalies}
            />
          </div>
          <PeriodFilter dateRange={dateRange} onChange={setDateRange} />
          <TabsContent value="ecritures">
            <EntriesTable entries={result.entries} />
          </TabsContent>
          <TabsContent value="anomalies">
            <AnomaliesPanel anomalies={filteredAnomalies} />
          </TabsContent>
          <TabsContent value="resume">
            {filteredSummary && (
              <StatsBoard summary={filteredSummary} entries={result.entries} anomalies={filteredAnomalies} />
            )}
          </TabsContent>
        </Tabs>
      )}
    </main>
  );
}
