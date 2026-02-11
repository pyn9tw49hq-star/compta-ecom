import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { axe } from "vitest-axe";
import Home from "@/app/page";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  processFiles: vi.fn(),
  downloadExcel: vi.fn(),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({
    theme: "system",
    resolvedTheme: "light",
    setTheme: vi.fn(),
  }),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockProcessFiles = vi.mocked(api.processFiles);

function createMockFile(name: string, size = 1024): File {
  const content = new ArrayBuffer(size);
  return new File([content], name, { type: "text/csv" });
}

function addFilesViaInput(files: File[]) {
  const input = screen.getByTestId("file-input") as HTMLInputElement;
  Object.defineProperty(input, "files", {
    value: files,
    configurable: true,
  });
  fireEvent.change(input);
}

describe("Page Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Initial render tests (6.3) ---

  it("renders page title and help button", () => {
    render(<Home />);

    expect(screen.getByText(/MAPP E-COMMERCE/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /aide/i })
    ).toBeInTheDocument();
  });

  it("renders FileDropZone with drop zone", () => {
    render(<Home />);

    expect(screen.getByText(/Glissez-déposez/)).toBeInTheDocument();
  });

  it("renders ChannelDashboard with all channels", () => {
    render(<Home />);

    expect(screen.getByText("Shopify")).toBeInTheDocument();
    expect(screen.getByText("ManoMano")).toBeInTheDocument();
    expect(screen.getByText("Décathlon")).toBeInTheDocument();
    expect(screen.getByText("Leroy Merlin")).toBeInTheDocument();
  });

  it("renders ValidationBar with disabled button", () => {
    render(<Home />);

    const button = screen.getByRole("button", {
      name: /Générer les écritures/i,
    });
    expect(button).toBeDisabled();
  });

  it("does not render UnmatchedFilesPanel when no files", () => {
    render(<Home />);

    expect(
      screen.queryByText(/fichier non reconnu/)
    ).not.toBeInTheDocument();
  });

  // --- HelpDrawer integration (6.4) ---

  it("opens HelpDrawer when clicking Aide button", () => {
    render(<Home />);

    fireEvent.click(screen.getByRole("button", { name: /aide/i }));

    expect(
      screen.getByText("Comment nommer vos fichiers")
    ).toBeInTheDocument();
  });

  it("opens HelpDrawer from UnmatchedFilesPanel link", () => {
    render(<Home />);

    act(() => {
      addFilesViaInput([createMockFile("random.csv")]);
    });

    fireEvent.click(screen.getByText("Voir les formats de noms attendus"));

    expect(
      screen.getByText("Comment nommer vos fichiers")
    ).toBeInTheDocument();
  });

  // --- Upload → classification (6.5) ---

  it("classifies uploaded files into ChannelDashboard", () => {
    render(<Home />);

    act(() => {
      addFilesViaInput([createMockFile("Ventes Shopify Janvier.csv")]);
    });

    expect(screen.getByText(/1 \/ 3 obligatoires/)).toBeInTheDocument();
    expect(screen.getByText(/1 fichier déposé/)).toBeInTheDocument();
  });

  it("shows unmatched files in UnmatchedFilesPanel", () => {
    render(<Home />);

    act(() => {
      addFilesViaInput([createMockFile("random.csv")]);
    });

    expect(screen.getByText("1 fichier non reconnu")).toBeInTheDocument();
  });

  it("shows suggestion for unmatched shopify file", () => {
    render(<Home />);

    act(() => {
      addFilesViaInput([createMockFile("export_shopify.csv")]);
    });

    expect(screen.getByText(/Suggestion/)).toBeInTheDocument();
  });

  // --- File removal (6.6) ---

  it("removes file from ChannelDashboard", () => {
    render(<Home />);

    act(() => {
      addFilesViaInput([createMockFile("Ventes Shopify.csv")]);
    });

    // File visible in expanded Shopify card
    expect(screen.getByText("Ventes Shopify.csv")).toBeInTheDocument();
    expect(screen.getByText(/1 fichier déposé/)).toBeInTheDocument();

    // Click remove button in FileSlot
    fireEvent.click(
      screen.getByRole("button", { name: /Retirer Ventes Shopify\.csv/i })
    );

    // File removed, counter gone
    expect(
      screen.queryByText("Ventes Shopify.csv")
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/fichier déposé/)).not.toBeInTheDocument();
  });

  it("removes file from UnmatchedFilesPanel", () => {
    render(<Home />);

    act(() => {
      addFilesViaInput([createMockFile("random.csv")]);
    });

    expect(screen.getByText("1 fichier non reconnu")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Retirer random\.csv/i })
    );

    expect(
      screen.queryByText(/fichier non reconnu/)
    ).not.toBeInTheDocument();
  });

  // --- Full flow (6.7) ---

  it("full flow: upload → validate → generate → results", async () => {
    const mockResponse = {
      entries: [
        {
          date: "2026-01-15",
          journal: "VE",
          compte: "411000",
          libelle: "Vente Shopify #1001",
          debit: 100,
          credit: 0,
          piece: "1001",
          lettrage: "SHP1001",
          canal: "shopify",
          type_ecriture: "vente",
        },
      ],
      anomalies: [],
      summary: {
        transactions_par_canal: { shopify: 1 },
        ecritures_par_type: { vente: 1 },
        totaux: { debit: 100, credit: 100 },
      },
      transactions: [
        {
          reference: "1001",
          channel: "shopify",
          date: "2026-01-15",
          type: "sale" as const,
          amount_ht: 83.33,
          amount_tva: 16.67,
          amount_ttc: 100,
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
    mockProcessFiles.mockResolvedValueOnce(mockResponse);

    render(<Home />);

    // Upload 3 Shopify files
    act(() => {
      addFilesViaInput([
        createMockFile("Ventes Shopify.csv"),
        createMockFile("Transactions Shopify.csv"),
        createMockFile("Détails versements.csv"),
      ]);
    });

    // ValidationBar shows complete
    expect(screen.getByText(/Shopify sera traité/)).toBeInTheDocument();

    // Button is active
    const button = screen.getByRole("button", {
      name: /Générer les écritures/i,
    });
    expect(button).not.toBeDisabled();

    // Click generate
    fireEvent.click(button);

    // Wait for results
    await waitFor(() => {
      expect(screen.getByText("Écritures")).toBeInTheDocument();
    });

    expect(screen.getByText("Anomalies")).toBeInTheDocument();
    expect(screen.getByText("Résumé")).toBeInTheDocument();
  });

  // --- Error backend (6.8) ---

  it("displays error alert on backend failure", async () => {
    mockProcessFiles.mockRejectedValueOnce(
      new Error("Erreur de traitement")
    );

    render(<Home />);

    // Upload a complete channel (Decathlon — 1 required file)
    act(() => {
      addFilesViaInput([createMockFile("Decathlon mars.csv")]);
    });

    fireEvent.click(
      screen.getByRole("button", { name: /Générer les écritures/i })
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Erreur de traitement"
      );
    });
  });

  // --- Result tabs (6.9) ---

  it("result tabs render correctly after processing", async () => {
    const mockResponse = {
      entries: [
        {
          date: "2026-02-15",
          journal: "VE",
          compte: "411000",
          libelle: "Vente",
          debit: 50,
          credit: 0,
          piece: "1",
          lettrage: "L1",
          canal: "decathlon",
          type_ecriture: "vente",
        },
      ],
      anomalies: [
        {
          type: "vat_mismatch",
          severity: "warning" as const,
          canal: "decathlon",
          reference: "REF1",
          detail: "TVA mismatch",
        },
      ],
      summary: {
        transactions_par_canal: { decathlon: 1 },
        ecritures_par_type: { vente: 1 },
        totaux: { debit: 50, credit: 50 },
      },
      transactions: [
        {
          reference: "REF1",
          channel: "decathlon",
          date: "2026-02-15",
          type: "sale" as const,
          amount_ht: 41.67,
          amount_tva: 8.33,
          amount_ttc: 50,
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
    mockProcessFiles.mockResolvedValueOnce(mockResponse);

    render(<Home />);

    act(() => {
      addFilesViaInput([createMockFile("Decathlon mars.csv")]);
    });

    fireEvent.click(
      screen.getByRole("button", { name: /Générer les écritures/i })
    );

    await waitFor(() => {
      expect(screen.getByText("Écritures")).toBeInTheDocument();
    });

    // All tabs present with anomaly count
    expect(screen.getByText(/Anomalies \(1\)/)).toBeInTheDocument();
    expect(screen.getByText("Résumé")).toBeInTheDocument();
  });

  // --- Accessibility (6.10) ---

  it("has no axe violations on empty page", async () => {
    const { container } = render(<Home />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("has no axe violations with uploaded files", async () => {
    const { container } = render(<Home />);

    act(() => {
      addFilesViaInput([
        createMockFile("Ventes Shopify.csv"),
        createMockFile("random.csv"),
      ]);
    });

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  // --- Dark mode tests (7.1) ---

  it("renders ThemeToggle in header", () => {
    render(<Home />);

    expect(
      screen.getByRole("button", { name: /Changer le thème/i })
    ).toBeInTheDocument();
  });

  it("has no axe violations in dark mode", async () => {
    const { container } = render(
      <div className="dark">
        <Home />
      </div>
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
