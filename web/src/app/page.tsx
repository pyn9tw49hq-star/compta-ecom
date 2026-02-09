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
import { processFiles } from "@/lib/api";
import { CHANNEL_CONFIGS, matchFileToSlot } from "@/lib/channels";
import type { UploadedFile, ProcessResponse, ChannelStatus, FileSlotConfig } from "@/lib/types";

export default function Home() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isHelpOpen, setIsHelpOpen] = useState(false);

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
          compta-ecom — Générateur d&apos;écritures comptables
        </h1>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Button variant="outline" size="icon" onClick={() => setIsHelpOpen(true)} aria-label="Aide sur les formats de fichiers">
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
                Anomalies{result.anomalies.length > 0 && ` (${result.anomalies.length})`}
              </TabsTrigger>
              <TabsTrigger value="resume">Résumé</TabsTrigger>
            </TabsList>
            <DownloadButtons
              files={files.map((f) => f.file)}
              entries={result.entries}
              anomalies={result.anomalies}
            />
          </div>
          <TabsContent value="ecritures">
            <EntriesTable entries={result.entries} />
          </TabsContent>
          <TabsContent value="anomalies">
            <AnomaliesPanel anomalies={result.anomalies} />
          </TabsContent>
          <TabsContent value="resume">
            <StatsBoard summary={result.summary} entries={result.entries} anomalies={result.anomalies} />
          </TabsContent>
        </Tabs>
      )}
    </main>
  );
}
