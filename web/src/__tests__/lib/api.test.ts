import { describe, it, expect, vi, beforeEach } from "vitest";
import { processFiles, downloadExcel } from "@/lib/api";
import type { ProcessResponse } from "@/lib/types";

const MOCK_RESPONSE: ProcessResponse = {
  entries: [
    {
      date: "2026-01-15",
      journal: "VE",
      compte: "411SHOPIFY",
      libelle: "Vente #1118",
      debit: 119.0,
      credit: 0,
      piece: "#1118",
      lettrage: "A",
      canal: "shopify",
      type_ecriture: "sale",
    },
  ],
  anomalies: [],
  summary: {
    transactions_par_canal: { shopify: 1 },
    ecritures_par_type: { sale: 1 },
    totaux: { debit: 119.0, credit: 119.0 },
  },
};

function createMockFile(name: string, content = "a,b\n1,2"): File {
  return new File([content], name, { type: "text/csv" });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("processFiles", () => {
  it("sends files as multipart/form-data and returns ProcessResponse", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_RESPONSE),
    });
    vi.stubGlobal("fetch", mockFetch);

    const files = [createMockFile("Ventes Shopify Janvier.csv")];
    const result = await processFiles(files);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/api/process");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
    expect(result).toEqual(MOCK_RESPONSE);
  });

  it("throws error with detail message on HTTP 422", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: "Fichiers CSV requis" }),
      })
    );

    const files = [createMockFile("bad.csv")];
    await expect(processFiles(files)).rejects.toThrow("Fichiers CSV requis");
  });

  it("throws generic error when no detail in error response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error("not json")),
      })
    );

    const files = [createMockFile("test.csv")];
    await expect(processFiles(files)).rejects.toThrow("Erreur serveur (500)");
  });

  it("propagates network errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch"))
    );

    const files = [createMockFile("test.csv")];
    await expect(processFiles(files)).rejects.toThrow("Failed to fetch");
  });
});

describe("downloadExcel", () => {
  it("sends files and returns a Blob", async () => {
    const blob = new Blob(["fake-excel"], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        blob: () => Promise.resolve(blob),
      })
    );

    const files = [createMockFile("Ventes Shopify.csv")];
    const result = await downloadExcel(files);

    expect(result).toBeInstanceOf(Blob);
  });

  it("throws error with detail on HTTP error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: "Fichier invalide" }),
      })
    );

    const files = [createMockFile("bad.csv")];
    await expect(downloadExcel(files)).rejects.toThrow("Fichier invalide");
  });
});
