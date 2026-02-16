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
    ca_par_canal: { shopify: { ht: 99.17, ttc: 119.0 } },
    remboursements_par_canal: { shopify: { count: 0, ht: 0, ttc: 0 } },
    taux_remboursement_par_canal: { shopify: 0 },
    commissions_par_canal: { shopify: { ht: 0, ttc: 0 } },
    net_vendeur_par_canal: { shopify: 119.0 },
    tva_collectee_par_canal: { shopify: 19.83 },
    ventilation_ca_par_canal: { shopify: { produits_ht: 99.17, port_ht: 0, total_ht: 99.17 } },
    repartition_geo_globale: { France: { count: 1, ca_ttc: 119.0, ca_ht: 99.17 } },
    repartition_geo_par_canal: { shopify: { France: { count: 1, ca_ttc: 119.0, ca_ht: 99.17 } } },
    tva_par_pays_par_canal: { shopify: { France: [{ taux: 20, montant: 19.83 }] } },
  },
  transactions: [
    {
      reference: "#1118",
      channel: "shopify",
      date: "2026-01-15",
      type: "sale",
      amount_ht: 99.17,
      amount_tva: 19.83,
      amount_ttc: 119.0,
      shipping_ht: 0,
      shipping_tva: 0,
      tva_rate: 20,
      country_code: "FR",
      commission_ttc: 0,
      commission_ht: 0,
      special_type: null,
    },
  ],
  country_names: { FR: "France" },
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

  it("appends date_from and date_to when dateRange is provided", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_RESPONSE),
    });
    vi.stubGlobal("fetch", mockFetch);

    const files = [createMockFile("Ventes Shopify.csv")];
    const dateRange = {
      from: new Date("2026-01-01T12:00:00Z"),
      to: new Date("2026-01-31T12:00:00Z"),
    };
    await processFiles(files, undefined, dateRange);

    const formData = mockFetch.mock.calls[0][1].body as FormData;
    expect(formData.get("date_from")).toBe("2026-01-01");
    expect(formData.get("date_to")).toBe("2026-01-31");
  });

  it("does not append date params when dateRange is undefined", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_RESPONSE),
    });
    vi.stubGlobal("fetch", mockFetch);

    const files = [createMockFile("Ventes Shopify.csv")];
    await processFiles(files);

    const formData = mockFetch.mock.calls[0][1].body as FormData;
    expect(formData.get("date_from")).toBeNull();
    expect(formData.get("date_to")).toBeNull();
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

  it("appends date_from and date_to when dateRange is provided", async () => {
    const blob = new Blob(["fake-excel"]);
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(blob),
    });
    vi.stubGlobal("fetch", mockFetch);

    const files = [createMockFile("Ventes Shopify.csv")];
    const dateRange = {
      from: new Date("2026-02-01T12:00:00Z"),
      to: new Date("2026-02-28T12:00:00Z"),
    };
    await downloadExcel(files, undefined, dateRange);

    const formData = mockFetch.mock.calls[0][1].body as FormData;
    expect(formData.get("date_from")).toBe("2026-02-01");
    expect(formData.get("date_to")).toBe("2026-02-28");
  });
});
