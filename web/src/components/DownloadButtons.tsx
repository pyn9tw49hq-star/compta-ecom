"use client";

import { useState } from "react";
import { Download, FileDown, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { downloadExcel } from "@/lib/api";
import type { Entry, Anomaly } from "@/lib/types";

interface DownloadButtonsProps {
  files: File[];
  entries: Entry[];
  anomalies: Anomaly[];
}

/** Return today's date as YYYY-MM-DD. */
function getDateSuffix(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Generate a RFC 4180 CSV string from headers and rows.
 * Values containing commas, quotes, or newlines are escaped.
 */
function generateCsv(headers: string[], rows: string[][]): string {
  const escape = (val: string): string => {
    if (val.includes(",") || val.includes('"') || val.includes("\n")) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  };
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(row.map(escape).join(","));
  }
  return lines.join("\n");
}

/** Trigger a browser download from a Blob. */
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Delay revocation so the browser has time to start the download
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const ENTRY_CSV_HEADERS = [
  "date",
  "journal",
  "account",
  "label",
  "debit",
  "credit",
  "piece_number",
  "lettrage",
  "channel",
  "entry_type",
];

const ANOMALY_CSV_HEADERS = [
  "type",
  "severity",
  "reference",
  "channel",
  "detail",
];

export default function DownloadButtons({
  files,
  entries,
  anomalies,
}: DownloadButtonsProps) {
  const [downloadingExcel, setDownloadingExcel] = useState(false);
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDownloading = downloadingExcel || downloadingCsv;

  const handleExcelDownload = async () => {
    setError(null);
    setDownloadingExcel(true);
    try {
      const blob = await downloadExcel(files);
      triggerDownload(blob, `ecritures-${getDateSuffix()}.xlsx`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      const isServerError =
        msg.includes("serveur") || msg.includes("fetch") || msg.includes("network");
      const prefix = isServerError
        ? "Le serveur est temporairement indisponible. "
        : "";
      setError(
        `${prefix}La génération du fichier Excel a échoué. Vous pouvez réessayer ou utiliser le téléchargement CSV qui fonctionne sans connexion au serveur.`,
      );
    } finally {
      setDownloadingExcel(false);
    }
  };

  const handleCsvDownload = async () => {
    setError(null);
    setDownloadingCsv(true);
    try {
      const dateSuffix = getDateSuffix();

      // Entries CSV
      const entryRows = entries.map((e) => [
        e.date,
        e.journal,
        e.compte,
        e.libelle,
        String(e.debit),
        String(e.credit),
        e.piece,
        e.lettrage,
        e.canal,
        e.type_ecriture,
      ]);
      const entriesCsv = "\uFEFF" + generateCsv(ENTRY_CSV_HEADERS, entryRows);
      const entriesBlob = new Blob([entriesCsv], {
        type: "text/csv;charset=utf-8",
      });
      triggerDownload(entriesBlob, `ecritures-${dateSuffix}.csv`);

      // Anomalies CSV — delay for browser to process first download (Safari needs ~500ms)
      await new Promise<void>((resolve) => setTimeout(resolve, 500));

      const anomalyRows = anomalies.map((a) => [
        a.type,
        a.severity,
        a.reference,
        a.canal,
        a.detail,
      ]);
      const anomaliesCsv =
        "\uFEFF" + generateCsv(ANOMALY_CSV_HEADERS, anomalyRows);
      const anomaliesBlob = new Blob([anomaliesCsv], {
        type: "text/csv;charset=utf-8",
      });
      triggerDownload(anomaliesBlob, `anomalies-${dateSuffix}.csv`);
    } catch {
      setError(
        "La génération des fichiers CSV a échoué. Veuillez réessayer.",
      );
    } finally {
      setDownloadingCsv(false);
    }
  };

  return (
    <div>
      <div className="flex gap-2 flex-wrap" aria-live="polite">
        <Button
          onClick={handleExcelDownload}
          disabled={isDownloading}
          aria-busy={downloadingExcel}
        >
          {downloadingExcel ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Download className="mr-2 h-4 w-4" />
          )}
          {downloadingExcel
            ? "Préparation du fichier..."
            : "Télécharger Excel (.xlsx)"}
        </Button>
        <Button
          variant="outline"
          onClick={handleCsvDownload}
          disabled={isDownloading}
          aria-busy={downloadingCsv}
        >
          {downloadingCsv ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <FileDown className="mr-2 h-4 w-4" />
          )}
          {downloadingCsv ? (
            "Génération en cours..."
          ) : (
            <>
              Télécharger CSV
              <span className="text-xs opacity-70 ml-1">(2 fichiers)</span>
            </>
          )}
        </Button>
      </div>
      {error && (
        <div
          role="alert"
          className="mt-2 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800"
        >
          {error}
        </div>
      )}
    </div>
  );
}
