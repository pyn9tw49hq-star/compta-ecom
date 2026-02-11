import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { axe } from "vitest-axe";
import DownloadButtons from "@/components/DownloadButtons";
import type { Entry, Anomaly } from "@/lib/types";

// --- Mock downloadExcel ---

const mockDownloadExcel = vi.fn<(...args: unknown[]) => Promise<Blob>>();

vi.mock("@/lib/api", () => ({
  downloadExcel: (...args: unknown[]) => mockDownloadExcel(...args),
}));

// --- Mock URL.createObjectURL / revokeObjectURL ---

const createdBlobs: Blob[] = [];
const mockCreateObjectURL = vi.fn((blob: Blob) => {
  createdBlobs.push(blob);
  return "blob:mock-url";
});
const mockRevokeObjectURL = vi.fn();

beforeEach(() => {
  vi.restoreAllMocks();
  mockDownloadExcel.mockReset();
  mockDownloadExcel.mockResolvedValue(new Blob(["xlsx-data"]));
  mockCreateObjectURL.mockClear();
  mockRevokeObjectURL.mockClear();
  createdBlobs.length = 0;
  global.URL.createObjectURL = mockCreateObjectURL;
  global.URL.revokeObjectURL = mockRevokeObjectURL;
});

// --- Mock data ---

const MOCK_FILES: File[] = [
  new File(["csv-content"], "shopify_orders.csv", { type: "text/csv" }),
];

const MOCK_ENTRIES: Entry[] = [
  {
    date: "2024-01-15",
    journal: "VE",
    compte: "411000",
    libelle: "Vente Shopify #1001",
    debit: 100.0,
    credit: 0,
    piece: "#1001",
    lettrage: "L001",
    canal: "shopify",
    type_ecriture: "sale",
  },
  {
    date: "2024-01-15",
    journal: "VE",
    compte: "707000",
    libelle: "Vente Shopify #1001",
    debit: 0,
    credit: 83.33,
    piece: "#1001",
    lettrage: "L001",
    canal: "shopify",
    type_ecriture: "sale",
  },
  {
    date: "2024-01-16",
    journal: "RE",
    compte: "511000",
    libelle: "Règlement #1002",
    debit: 50.0,
    credit: 0,
    piece: "#1002",
    lettrage: "L002",
    canal: "manomano",
    type_ecriture: "settlement",
  },
];

const MOCK_ANOMALIES: Anomaly[] = [
  {
    type: "tva_mismatch",
    severity: "warning",
    canal: "shopify",
    reference: "#1001",
    detail: "TVA 20% attendue, 10% trouvée",
  },
  {
    type: "orphan_sale",
    severity: "error",
    canal: "manomano",
    reference: "#2001",
    detail: "Vente sans règlement",
  },
];

/** Read blob text via FileReader (jsdom compatible). */
function getBlobText(blobIndex: number): Promise<string> {
  const blob = createdBlobs[blobIndex];
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsText(blob);
  });
}

/** Check blob starts with UTF-8 BOM (EF BB BF). */
function blobHasBom(blobIndex: number): Promise<boolean> {
  const blob = createdBlobs[blobIndex];
  return new Promise<boolean>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const bytes = new Uint8Array(reader.result as ArrayBuffer);
      resolve(bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf);
    };
    reader.onerror = reject;
    reader.readAsArrayBuffer(blob);
  });
}

describe("DownloadButtons", () => {
  describe("Rendering (AC1, Task 5.4)", () => {
    it("renders both download buttons", () => {
      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      expect(
        screen.getByRole("button", { name: /Télécharger Excel/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Télécharger CSV/i }),
      ).toBeInTheDocument();
    });

    it("buttons are enabled on mount", () => {
      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      expect(
        screen.getByRole("button", { name: /Télécharger Excel/i }),
      ).toBeEnabled();
      expect(
        screen.getByRole("button", { name: /Télécharger CSV/i }),
      ).toBeEnabled();
    });

    it("CSV button contains '(2 fichiers)' text (UX)", () => {
      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      expect(screen.getByText("(2 fichiers)")).toBeInTheDocument();
    });
  });

  describe("Excel download (AC2, AC4, Task 5.5)", () => {
    it("calls downloadExcel with files and triggers download", async () => {
      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger Excel/i }),
        );
      });

      expect(mockDownloadExcel).toHaveBeenCalledWith(MOCK_FILES, undefined);
      expect(mockCreateObjectURL).toHaveBeenCalled();
    });

    it("download link has .xlsx filename with date", async () => {
      const clickedLinks: HTMLAnchorElement[] = [];
      const originalCreateElement = document.createElement.bind(document);
      vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
        const el = originalCreateElement(tag);
        if (tag === "a") {
          vi.spyOn(el as HTMLAnchorElement, "click").mockImplementation(
            () => {},
          );
          clickedLinks.push(el as HTMLAnchorElement);
        }
        return el;
      });

      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger Excel/i }),
        );
      });

      expect(clickedLinks.length).toBeGreaterThanOrEqual(1);
      const link = clickedLinks[0];
      expect(link.download).toMatch(/^ecritures-\d{4}-\d{2}-\d{2}\.xlsx$/);
    });
  });

  describe("CSV download (AC3, AC4, Task 5.6)", () => {
    it("creates two blobs for entries and anomalies CSV", async () => {
      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger CSV/i }),
        );
        await new Promise((r) => setTimeout(r, 600));
      });

      // Two createObjectURL calls (entries + anomalies)
      expect(mockCreateObjectURL).toHaveBeenCalledTimes(2);
    });

    it("entries CSV has correct headers and BOM", async () => {
      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger CSV/i }),
        );
        await new Promise((r) => setTimeout(r, 600));
      });

      // BOM (UTF-8: EF BB BF)
      expect(await blobHasBom(0)).toBe(true);

      const csvText = await getBlobText(0);
      // Headers
      expect(csvText).toContain(
        "date,journal,account,label,debit,credit,piece_number,lettrage,channel,entry_type",
      );
      // Data mapped correctly (compte → account column, canal → channel column)
      expect(csvText).toContain("411000");
      expect(csvText).toContain("shopify");
      expect(csvText).toContain("sale");
    });

    it("anomalies CSV has correct headers with canal→channel mapping (S1)", async () => {
      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger CSV/i }),
        );
        await new Promise((r) => setTimeout(r, 600));
      });

      // BOM (UTF-8: EF BB BF)
      expect(await blobHasBom(1)).toBe(true);

      const csvText = await getBlobText(1);
      // Headers use English names
      expect(csvText).toContain("type,severity,reference,channel,detail");
      // Data present with canal value mapped under channel column
      expect(csvText).toContain("tva_mismatch");
      expect(csvText).toContain("shopify");
      expect(csvText).toContain("manomano");
    });
  });

  describe("Disabled state during download (AC5, Task 5.7)", () => {
    it("disables both buttons during Excel download with dynamic text", async () => {
      let resolveDownload!: (blob: Blob) => void;
      mockDownloadExcel.mockImplementation(
        () =>
          new Promise<Blob>((resolve) => {
            resolveDownload = resolve;
          }),
      );

      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      // Click Excel — don't resolve the promise yet
      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger Excel/i }),
        );
      });

      // Both buttons disabled
      const buttons = screen.getAllByRole("button");
      for (const btn of buttons) {
        expect(btn).toBeDisabled();
      }

      // Dynamic text
      expect(
        screen.getByText(/Préparation du fichier/),
      ).toBeInTheDocument();

      // aria-busy on Excel button
      expect(
        screen.getByRole("button", { name: /Préparation du fichier/ }),
      ).toHaveAttribute("aria-busy", "true");

      // Resolve download
      await act(async () => {
        resolveDownload(new Blob(["data"]));
      });

      // Buttons re-enabled with original text
      expect(
        screen.getByRole("button", { name: /Télécharger Excel/i }),
      ).toBeEnabled();
      expect(
        screen.getByRole("button", { name: /Télécharger CSV/i }),
      ).toBeEnabled();
    });

    it("disables both buttons during CSV download with dynamic text (S2)", async () => {
      // Use fake timers to pause the CSV handler at the setTimeout(0) await
      vi.useFakeTimers();

      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      // Click CSV — handler will pause at await setTimeout(0)
      // Use fireEvent (not act-wrapped) to avoid automatic timer flushing
      fireEvent.click(
        screen.getByRole("button", { name: /Télécharger CSV/i }),
      );

      // Allow microtasks to flush so React state update (setDownloadingCsv(true)) is applied
      await act(async () => {});

      // Both buttons should be disabled during CSV generation
      const buttons = screen.getAllByRole("button");
      for (const btn of buttons) {
        expect(btn).toBeDisabled();
      }

      // Dynamic text for CSV
      expect(screen.getByText(/Génération en cours/)).toBeInTheDocument();

      // Advance timers and let the handler finish
      await act(async () => {
        vi.runAllTimers();
      });

      vi.useRealTimers();

      // Buttons re-enabled
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /Télécharger CSV/i }),
        ).toBeEnabled();
      });
    });
  });

  describe("Error handling (Task 5.8)", () => {
    it("displays error message when Excel download fails", async () => {
      mockDownloadExcel.mockRejectedValue(new Error("Erreur serveur (500)"));

      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger Excel/i }),
        );
      });

      const alert = screen.getByRole("alert");
      expect(alert).toBeInTheDocument();
    });

    it("error message has role='alert'", async () => {
      mockDownloadExcel.mockRejectedValue(new Error("network error"));

      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger Excel/i }),
        );
      });

      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    it("error message suggests CSV fallback in user-friendly language (UX)", async () => {
      mockDownloadExcel.mockRejectedValue(
        new Error("Erreur serveur (500)"),
      );

      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: /Télécharger Excel/i }),
        );
      });

      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain("téléchargement CSV");
      expect(alert.textContent).toContain("échoué");
      // No technical jargon like stack traces
      expect(alert.textContent).not.toMatch(/Error:|at\s/);
    });
  });

  describe("Accessibility (Task 5.9, 5.10)", () => {
    it("container has aria-live='polite'", () => {
      render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      const container = screen
        .getByRole("button", { name: /Télécharger Excel/i })
        .closest("[aria-live]");
      expect(container).toHaveAttribute("aria-live", "polite");
    });

    it("has no axe violations", async () => {
      const { container } = render(
        <DownloadButtons
          files={MOCK_FILES}
          entries={MOCK_ENTRIES}
          anomalies={MOCK_ANOMALIES}
        />,
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});
