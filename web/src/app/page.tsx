"use client";

import { useState, useCallback } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import FileDropZone from "@/components/FileDropZone";
import EntriesTable from "@/components/EntriesTable";
import AnomaliesPanel from "@/components/AnomaliesPanel";
import StatsBoard from "@/components/StatsBoard";
import DownloadButtons from "@/components/DownloadButtons";
import { processFiles } from "@/lib/api";
import type { UploadedFile, ProcessResponse } from "@/lib/types";

export default function Home() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFilesChange = useCallback((updated: UploadedFile[]) => {
    setFiles(updated);
    setError(null);
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
      <h1 className="text-2xl font-bold mb-6">
        compta-ecom — Générateur d&apos;écritures comptables
      </h1>

      <FileDropZone onFilesChange={handleFilesChange} />

      <div className="mt-4">
        <Button
          onClick={handleProcess}
          disabled={files.length === 0 || loading}
          className="w-full sm:w-auto"
        >
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Générer les écritures
        </Button>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800"
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
