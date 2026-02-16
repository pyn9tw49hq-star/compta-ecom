import type { AccountDefaults, AccountOverrides, ProcessResponse } from "@/lib/types";
import type { DateRange } from "@/lib/datePresets";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Send CSV files to the backend for processing.
 * Returns parsed entries, anomalies, and summary.
 */
export async function processFiles(
  files: File[],
  overrides?: AccountOverrides,
  dateRange?: DateRange,
): Promise<ProcessResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  if (overrides && Object.keys(overrides).length > 0) {
    formData.append("overrides", JSON.stringify(overrides));
  }
  if (dateRange) {
    formData.append("date_from", dateRange.from.toISOString().slice(0, 10));
    formData.append("date_to", dateRange.to.toISOString().slice(0, 10));
  }

  const response = await fetch(`${API_URL}/api/process`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const message = errorBody?.detail ?? `Erreur serveur (${response.status})`;
    throw new Error(message);
  }

  return response.json() as Promise<ProcessResponse>;
}

/**
 * Send CSV files and get back an Excel workbook as a Blob.
 */
export async function downloadExcel(
  files: File[],
  overrides?: AccountOverrides,
  dateRange?: DateRange,
): Promise<Blob> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  if (overrides && Object.keys(overrides).length > 0) {
    formData.append("overrides", JSON.stringify(overrides));
  }
  if (dateRange) {
    formData.append("date_from", dateRange.from.toISOString().slice(0, 10));
    formData.append("date_to", dateRange.to.toISOString().slice(0, 10));
  }

  const response = await fetch(`${API_URL}/api/download/excel`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const message = errorBody?.detail ?? `Erreur serveur (${response.status})`;
    throw new Error(message);
  }

  return response.blob();
}

/**
 * Fetch default account values from the backend.
 */
export async function fetchDefaults(): Promise<AccountDefaults> {
  const response = await fetch(`${API_URL}/api/defaults`);

  if (!response.ok) {
    throw new Error(`Erreur chargement des défauts (${response.status})`);
  }

  return response.json() as Promise<AccountDefaults>;
}
