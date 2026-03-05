"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import dynamic from "next/dynamic";
import { HelpCircle, BarChart3, ArrowLeft, X } from "lucide-react";
import { Separator } from "@/components/ui/separator";
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
import FlashPdfButton from "@/components/FlashPdfButton";
import AnomalyPdfButton from "@/components/AnomalyPdfButton";
import AccountSettingsPanel, { hasAccountValidationErrors } from "@/components/AccountSettingsPanel";
import PeriodFilter from "@/components/PeriodFilter";
import { useAccountOverrides } from "@/hooks/useAccountOverrides";
import { useNewDesign } from "@/hooks/useNewDesign";
import Sidebar from "@/components/Sidebar";
import { processFiles, fetchDefaults } from "@/lib/api";
import { CHANNEL_CONFIGS, matchFileToSlot } from "@/lib/channels";
import { DEFAULT_PRESET, getPresetRange, computeDataRange } from "@/lib/datePresets";
import { computeSummary } from "@/lib/computeSummary";
import { countVisualCards } from "@/lib/anomalyCardKey";
import type { DateRange } from "@/lib/datePresets";
import type { UploadedFile, ProcessResponse, ChannelStatus, FileSlotConfig } from "@/lib/types";

const DashboardTab = dynamic(
  () => import("@/components/dashboard").then((m) => m.DashboardTab),
  { loading: () => <div className="h-96 animate-pulse bg-muted rounded-lg" /> }
);

export default function Home() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const isHelpButtonClickRef = useRef(false);
  const [dateRange, setDateRange] = useState<DateRange>(() => getPresetRange(DEFAULT_PRESET));
  const [htTtcMode, setHtTtcMode] = useState<"ht" | "ttc">("ht");
  const [activeTab, setActiveTab] = useState("ecritures");
  const [showFlash, setShowFlash] = useState(false);
  const account = useAccountOverrides();
  const isV2 = useNewDesign();
  const [activeView, setActiveView] = useState("upload");

  // Fetch defaults on mount
  useEffect(() => {
    fetchDefaults()
      .then((d) => account.setDefaults(d))
      .catch(() => {
        // Defaults unavailable — panel will stay hidden
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close Flash overlay on Escape key
  useEffect(() => {
    if (!showFlash) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowFlash(false);
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [showFlash]);

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
        (slot) => slot.regex && files.some((f) => slot.regex!.test(f.file.name.normalize("NFC")))
      ).length;

      // fileGroups mode: at least one group must have all its slots filled
      if (config.fileGroups) {
        const filledSlotKeys = new Set<string>();
        for (const slot of config.files) {
          if (slot.regex && files.some((f) => slot.regex!.test(f.file.name.normalize("NFC")))) {
            filledSlotKeys.add(slot.key);
          }
        }
        const completed: string[] = [];
        for (const group of config.fileGroups) {
          if (group.slots.every((s) => filledSlotKeys.has(s))) {
            completed.push(group.label);
          }
        }
        return {
          channelKey: config.key,
          label: config.meta.label,
          requiredCount: requiredSlots.length,
          uploadedRequiredCount,
          isComplete: completed.length > 0,
          completedGroups: completed,
          activeMode: completed.length > 0 ? completed[completed.length - 1] : undefined,
        };
      }

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
        const isFilled = files.some((f) => slot.regex!.test(f.file.name.normalize("NFC")));
        if (!isFilled) {
          missing.push({ channel: config.key, slot });
        }
      }
    }
    return missing;
  }, [files]);

  // --- Period filtering ---
  const filteredEntries = useMemo(() => {
    if (!result) return [];
    return result.entries.filter((e) => {
      const d = new Date(e.date + "T00:00:00");
      return d >= dateRange.from && d <= dateRange.to;
    });
  }, [result, dateRange]);

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

  const uniqueAnomalyCount = useMemo(() => {
    return countVisualCards(filteredAnomalies);
  }, [filteredAnomalies]);

  const handleAddFiles = useCallback((newFiles: UploadedFile[]) => {
    setFiles((prev) => [...prev, ...newFiles]);
    setError(null);
  }, []);

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const accountHasErrors = useMemo(
    () => hasAccountValidationErrors(account),
    [account],
  );

  const tolerance = useMemo(() => {
    const raw = account.getValue("matching_tolerance");
    const num = parseFloat(raw);
    return isNaN(num) ? 0.01 : num;
  }, [account]);

  const handleProcess = useCallback(async () => {
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await processFiles(
        files.map((f) => f.file),
        account.modifiedCount > 0 ? account.overrides : undefined,
      );
      setResult(response);

      // Auto-detect date range from all entry and transaction dates
      const allDates = [
        ...response.entries.map((e) => e.date),
        ...response.transactions.map((t) => t.date),
      ];
      const dataRange = computeDataRange(allDates);
      if (dataRange) {
        setDateRange(dataRange);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }, [files, account.overrides, account.modifiedCount]);

  // ── V2 layout with sidebar ──
  if (isV2) {
    return (
      <>
        <HelpDrawer isOpen={isHelpOpen} onOpenChange={(open) => {
          if (isHelpButtonClickRef.current) return;
          setIsHelpOpen(open);
        }} />
        <div className="flex min-h-screen">
          <Sidebar
            activeView={activeView}
            onViewChange={setActiveView}
            anomalyCount={filteredAnomalies.length}
            hasResult={!!result}
            onOpenHelp={() => setIsHelpOpen(true)}
          />
          <main className="flex-1 min-w-0 p-8">
            {activeView === "upload" && (
              <>
                <h1 className="text-2xl font-bold mb-6">Import fichiers</h1>
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
                    disabled={accountHasErrors}
                  />
                </div>
                {error && (
                  <div role="alert" className="mt-4 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-200">
                    {error}
                  </div>
                )}
              </>
            )}
            {activeView === "parametres" && (
              <>
                <h1 className="text-2xl font-bold mb-6">Parametres</h1>
                <AccountSettingsPanel account={account} />
              </>
            )}
            {activeView === "ecritures" && result && (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h1 className="text-2xl font-bold">Ecritures</h1>
                  <DownloadButtons
                    files={files.map((f) => f.file)}
                    entries={filteredEntries}
                    anomalies={filteredAnomalies}
                    overrides={account.modifiedCount > 0 ? account.overrides : undefined}
                    dateRange={dateRange}
                  />
                </div>
                <PeriodFilter dateRange={dateRange} onChange={setDateRange} />
                <EntriesTable entries={filteredEntries} />
              </>
            )}
            {activeView === "anomalies" && result && (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h1 className="text-2xl font-bold">Anomalies</h1>
                  <AnomalyPdfButton anomalies={filteredAnomalies} dateRange={dateRange} />
                </div>
                <PeriodFilter dateRange={dateRange} onChange={setDateRange} />
                <AnomaliesPanel anomalies={filteredAnomalies} />
              </>
            )}
            {activeView === "resume" && filteredSummary && (
              <>
                <h1 className="text-2xl font-bold mb-4">Resume</h1>
                <PeriodFilter dateRange={dateRange} onChange={setDateRange} />
                <StatsBoard summary={filteredSummary} entries={filteredEntries} anomalies={filteredAnomalies} htTtcMode={htTtcMode} onHtTtcModeChange={setHtTtcMode} tolerance={tolerance} />
              </>
            )}
            {activeView === "flash" && filteredSummary && (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h1 className="text-2xl font-bold">Flash e-commerce</h1>
                  <FlashPdfButton
                    summary={filteredSummary}
                    dateRange={dateRange}
                    htTtcMode={htTtcMode}
                    countryNames={result?.country_names ?? {}}
                    anomalies={filteredAnomalies}
                  />
                </div>
                <PeriodFilter dateRange={dateRange} onChange={setDateRange} />
                <DashboardTab
                  summary={filteredSummary}
                  anomalies={filteredAnomalies}
                  htTtcMode={htTtcMode}
                  onHtTtcModeChange={setHtTtcMode}
                  onNavigateTab={(tab) => setActiveView(tab)}
                  tolerance={tolerance}
                />
              </>
            )}
          </main>
        </div>
      </>
    );
  }

  // ── V1 layout (original) ──
  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <HelpDrawer isOpen={isHelpOpen} onOpenChange={(open) => {
        if (isHelpButtonClickRef.current) return;
        setIsHelpOpen(open);
      }} />

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">
          MAPP E-COMMERCE — Générateur d&apos;écritures comptables
        </h1>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Button
            variant="outline"
            size="icon"
            onPointerDown={() => { isHelpButtonClickRef.current = true; }}
            onClick={() => {
              setIsHelpOpen((prev) => !prev);
              requestAnimationFrame(() => { isHelpButtonClickRef.current = false; });
            }}
            aria-label="Aide sur les formats de fichiers"
          >
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
        <AccountSettingsPanel account={account} />
      </div>

      <div className="mt-4">
        <ValidationBar
          channelStatuses={channelStatuses}
          hasFiles={files.length > 0}
          isLoading={loading}
          onGenerate={handleProcess}
          disabled={accountHasErrors}
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
        <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-6">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <TabsList>
              <TabsTrigger value="ecritures">Écritures</TabsTrigger>
              <TabsTrigger value="anomalies">
                Anomalies{uniqueAnomalyCount > 0 && ` (${uniqueAnomalyCount})`}
              </TabsTrigger>
              <TabsTrigger value="resume">Résumé</TabsTrigger>
            </TabsList>
            <div className="flex gap-2 flex-wrap items-center">
              <DownloadButtons
                files={files.map((f) => f.file)}
                entries={filteredEntries}
                anomalies={filteredAnomalies}
                overrides={account.modifiedCount > 0 ? account.overrides : undefined}
                dateRange={dateRange}
              />
              <Separator orientation="vertical" className="h-6 mx-2" />
              <Button
                variant="default"
                onClick={() => setShowFlash(true)}
                className="gap-2"
                aria-label="Ouvrir le Flash e-commerce"
              >
                <BarChart3 className="h-4 w-4" />
                Flash e-commerce
              </Button>
            </div>
          </div>
          <PeriodFilter dateRange={dateRange} onChange={setDateRange} />
          <TabsContent value="ecritures">
            <EntriesTable entries={filteredEntries} />
          </TabsContent>
          <TabsContent value="anomalies">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Anomalies détectées</h2>
              <AnomalyPdfButton anomalies={filteredAnomalies} dateRange={dateRange} />
            </div>
            <AnomaliesPanel anomalies={filteredAnomalies} />
          </TabsContent>
          <TabsContent value="resume">
            {filteredSummary && (
              <StatsBoard summary={filteredSummary} entries={filteredEntries} anomalies={filteredAnomalies} htTtcMode={htTtcMode} onHtTtcModeChange={setHtTtcMode} tolerance={tolerance} />
            )}
          </TabsContent>
        </Tabs>
      )}

      {showFlash && (
        <div className="fixed inset-0 z-50 bg-background overflow-y-auto animate-in fade-in duration-200">
          {/* Header sticky */}
          <div className="sticky top-0 z-10 bg-background border-b px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={() => setShowFlash(false)}>
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div>
                <h2 className="text-lg font-semibold">Flash e-commerce</h2>
                <p className="text-sm text-muted-foreground">Tableau de bord synthétique</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {filteredSummary && (
                <FlashPdfButton
                  summary={filteredSummary}
                  dateRange={dateRange}
                  htTtcMode={htTtcMode}
                  countryNames={result?.country_names ?? {}}
                  anomalies={filteredAnomalies}
                />
              )}
              <Button variant="ghost" size="icon" onClick={() => setShowFlash(false)}>
                <X className="h-5 w-5" />
              </Button>
            </div>
          </div>

          {/* Contenu dashboard */}
          <div className="max-w-7xl mx-auto px-6 py-6">
            {filteredSummary && (
              <DashboardTab
                summary={filteredSummary}
                anomalies={filteredAnomalies}
                htTtcMode={htTtcMode}
                onHtTtcModeChange={setHtTtcMode}
                onNavigateTab={(tab) => {
                  setShowFlash(false);
                  setActiveTab(tab);
                }}
                tolerance={tolerance}
              />
            )}
          </div>
        </div>
      )}
    </main>
  );
}
