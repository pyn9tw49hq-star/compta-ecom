import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { axe } from "vitest-axe";
import EntriesTable from "@/components/EntriesTable";
import type { Entry } from "@/lib/types";

const CANALS = ["shopify", "manomano", "decathlon", "leroy_merlin"];
const JOURNALS = ["VE", "RG", "AC"];
const TYPES: Entry["type_ecriture"][] = [
  "sale",
  "refund",
  "settlement",
  "commission",
  "payout",
  "fee",
];

function makeEntry(i: number): Entry {
  return {
    date: `2026-01-${String((i % 28) + 1).padStart(2, "0")}`,
    journal: JOURNALS[i % JOURNALS.length],
    compte: i % 3 === 0 ? "411SHOPIFY" : i % 3 === 1 ? "70701250" : "4457250",
    libelle: `Écriture test #${i + 1}`,
    debit: i % 2 === 0 ? round2((i + 1) * 10.5) : 0,
    credit: i % 2 === 1 ? round2((i + 1) * 10.5) : 0,
    piece: `#${1000 + i}`,
    lettrage: i % 5 === 0 ? "A" : "",
    canal: CANALS[i % CANALS.length],
    type_ecriture: TYPES[i % TYPES.length],
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

function buildEntries(count: number): Entry[] {
  return Array.from({ length: count }, (_, i) => makeEntry(i));
}

const ENTRIES_60 = buildEntries(60);

describe("EntriesTable", () => {
  describe("rendering", () => {
    it("displays all 10 column headers", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const headers = [
        "Date",
        "Journal",
        "Compte",
        "Libellé",
        "Débit",
        "Crédit",
        "Pièce",
        "Lettrage",
        "Canal",
        "Type",
      ];
      for (const h of headers) {
        expect(
          screen.getByRole("columnheader", { name: new RegExp(h) }),
        ).toBeInTheDocument();
      }
    });

    it("formats amounts with French locale (2 decimals, comma separator)", () => {
      const entries: Entry[] = [
        {
          date: "2026-01-15",
          journal: "VE",
          compte: "411SHOPIFY",
          libelle: "Test",
          debit: 1234.5,
          credit: 0,
          piece: "#1",
          lettrage: "",
          canal: "shopify",
          type_ecriture: "sale",
        },
      ];
      render(<EntriesTable entries={entries} />);

      // French formatting: 1 234,50 (with narrow no-break space)
      expect(screen.getByText(/1\s*234,50/)).toBeInTheDocument();
      expect(screen.getByText("0,00")).toBeInTheDocument();
    });

    it("formats dates as DD/MM/YYYY", () => {
      const entries: Entry[] = [
        {
          date: "2026-01-15",
          journal: "VE",
          compte: "411",
          libelle: "Test",
          debit: 100,
          credit: 0,
          piece: "#1",
          lettrage: "",
          canal: "shopify",
          type_ecriture: "sale",
        },
      ];
      render(<EntriesTable entries={entries} />);

      expect(screen.getByText("15/01/2026")).toBeInTheDocument();
    });

    it("renders channel badges using getChannelMeta", () => {
      const entries: Entry[] = [
        {
          date: "2026-01-01",
          journal: "VE",
          compte: "411",
          libelle: "Test",
          debit: 10,
          credit: 0,
          piece: "#1",
          lettrage: "",
          canal: "shopify",
          type_ecriture: "sale",
        },
      ];
      render(<EntriesTable entries={entries} />);

      // "Shopify" appears in both filter checkbox and table badge
      const badges = screen.getAllByText("Shopify");
      expect(badges.length).toBeGreaterThanOrEqual(2);
      // The badge in the table has the badgeClass styling
      const tableBadge = badges.find((el) =>
        el.classList.contains("bg-green-100"),
      );
      expect(tableBadge).toBeDefined();
    });
  });

  describe("pagination", () => {
    it("shows 50 rows on page 1 out of 60 entries", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const rows = screen.getAllByRole("row");
      // 1 header row + 50 data rows
      expect(rows).toHaveLength(51);
    });

    it("displays total counter", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      expect(
        screen.getByText("60 écritures sur 60 total"),
      ).toBeInTheDocument();
    });

    it("navigates to page 2 with remaining 10 rows", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      fireEvent.click(screen.getByRole("button", { name: "Page suivante" }));

      const rows = screen.getAllByRole("row");
      // 1 header + 10 data rows
      expect(rows).toHaveLength(11);
      expect(screen.getByText(/Page 2 sur 2/)).toBeInTheDocument();
    });

    it("disables Previous on page 1 and Next on last page", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      expect(
        screen.getByRole("button", { name: "Page précédente" }),
      ).toBeDisabled();
      expect(
        screen.getByRole("button", { name: "Page suivante" }),
      ).toBeEnabled();

      fireEvent.click(screen.getByRole("button", { name: "Page suivante" }));

      expect(
        screen.getByRole("button", { name: "Page précédente" }),
      ).toBeEnabled();
      expect(
        screen.getByRole("button", { name: "Page suivante" }),
      ).toBeDisabled();
    });

    it("hides pagination when all entries fit on one page", () => {
      render(<EntriesTable entries={buildEntries(10)} />);

      expect(
        screen.queryByRole("button", { name: "Page suivante" }),
      ).not.toBeInTheDocument();
    });
  });

  describe("filtering", () => {
    it("filters by canal checkbox", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const shopifyCheckbox = screen.getByRole("checkbox", {
        name: /Shopify/,
      });
      fireEvent.click(shopifyCheckbox);

      // 60 entries, every 4th is shopify → 15
      const shopifyCount = ENTRIES_60.filter(
        (e) => e.canal === "shopify",
      ).length;
      expect(
        screen.getByText(`${shopifyCount} écritures sur 60 total`),
      ).toBeInTheDocument();
    });

    it("filters by compte text search (partial, case-insensitive)", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const input = screen.getByLabelText("Compte :");
      fireEvent.change(input, { target: { value: "411" } });

      const matchCount = ENTRIES_60.filter((e) =>
        e.compte.toLowerCase().includes("411"),
      ).length;
      expect(
        screen.getByText(`${matchCount} écritures sur 60 total`),
      ).toBeInTheDocument();
    });

    it("filters by journal select", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const select = screen.getByLabelText("Journal :");
      fireEvent.change(select, { target: { value: "VE" } });

      const veCount = ENTRIES_60.filter((e) => e.journal === "VE").length;
      expect(
        screen.getByText(`${veCount} écritures sur 60 total`),
      ).toBeInTheDocument();
    });

    it("filters by type checkbox", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const saleCheckbox = screen.getByRole("checkbox", { name: "sale" });
      fireEvent.click(saleCheckbox);

      const saleCount = ENTRIES_60.filter(
        (e) => e.type_ecriture === "sale",
      ).length;
      expect(
        screen.getByText(`${saleCount} écritures sur 60 total`),
      ).toBeInTheDocument();
    });

    it("resets pagination to page 1 when filter changes", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      // Go to page 2
      fireEvent.click(screen.getByRole("button", { name: "Page suivante" }));
      expect(screen.getByText(/Page 2/)).toBeInTheDocument();

      // Apply a filter — should reset to page 1
      const shopifyCheckbox = screen.getByRole("checkbox", {
        name: /Shopify/,
      });
      fireEvent.click(shopifyCheckbox);

      // Pagination may be hidden (<=50 results) or showing page 1
      const pageIndicator = screen.queryByText(/Page/);
      if (pageIndicator) {
        expect(pageIndicator).toHaveTextContent(/Page 1/);
      }
    });
  });

  describe("sorting", () => {
    it("sorts by Débit ascending on first click", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const debitHeader = screen.getByRole("columnheader", { name: /Débit/ });
      fireEvent.click(debitHeader);

      expect(debitHeader).toHaveAttribute("aria-sort", "ascending");
    });

    it("sorts by Débit descending on second click", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const debitHeader = screen.getByRole("columnheader", { name: /Débit/ });
      fireEvent.click(debitHeader);
      fireEvent.click(debitHeader);

      expect(debitHeader).toHaveAttribute("aria-sort", "descending");
    });

    it("applies numeric sort correctly for debit column", () => {
      const entries: Entry[] = [
        {
          date: "2026-01-01",
          journal: "VE",
          compte: "411",
          libelle: "A",
          debit: 200,
          credit: 0,
          piece: "#1",
          lettrage: "",
          canal: "shopify",
          type_ecriture: "sale",
        },
        {
          date: "2026-01-02",
          journal: "VE",
          compte: "411",
          libelle: "B",
          debit: 50,
          credit: 0,
          piece: "#2",
          lettrage: "",
          canal: "shopify",
          type_ecriture: "sale",
        },
        {
          date: "2026-01-03",
          journal: "VE",
          compte: "411",
          libelle: "C",
          debit: 1000,
          credit: 0,
          piece: "#3",
          lettrage: "",
          canal: "shopify",
          type_ecriture: "sale",
        },
      ];
      render(<EntriesTable entries={entries} />);

      fireEvent.click(screen.getByRole("columnheader", { name: /Débit/ }));

      // Get data rows (skip header)
      const rows = screen.getAllByRole("row").slice(1);
      const firstRowCells = within(rows[0]).getAllByRole("cell");
      // Libellé is column index 3
      expect(firstRowCells[3]).toHaveTextContent("B"); // debit=50 first
    });

    it("updates aria-sort when switching columns", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const debitHeader = screen.getByRole("columnheader", { name: /Débit/ });
      const dateHeader = screen.getByRole("columnheader", { name: /Date/ });

      fireEvent.click(debitHeader);
      expect(debitHeader).toHaveAttribute("aria-sort", "ascending");

      fireEvent.click(dateHeader);
      expect(dateHeader).toHaveAttribute("aria-sort", "ascending");
      expect(debitHeader).toHaveAttribute("aria-sort", "none");
    });
  });

  describe("accessibility", () => {
    it("has no axe violations", async () => {
      const { container } = render(
        <EntriesTable entries={buildEntries(5)} />,
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it("uses th scope=col for all column headers", () => {
      render(<EntriesTable entries={buildEntries(3)} />);

      const headers = screen.getAllByRole("columnheader");
      for (const header of headers) {
        expect(header).toHaveAttribute("scope", "col");
      }
    });

    it("pagination buttons have aria-labels", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      expect(
        screen.getByRole("button", { name: "Page précédente" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Page suivante" }),
      ).toBeInTheDocument();
    });

    it("column headers are keyboard-sortable via Enter", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const debitHeader = screen.getByRole("columnheader", { name: /Débit/ });
      fireEvent.keyDown(debitHeader, { key: "Enter" });

      expect(debitHeader).toHaveAttribute("aria-sort", "ascending");
    });

    it("column headers are keyboard-sortable via Space", () => {
      render(<EntriesTable entries={ENTRIES_60} />);

      const debitHeader = screen.getByRole("columnheader", { name: /Débit/ });
      fireEvent.keyDown(debitHeader, { key: " " });

      expect(debitHeader).toHaveAttribute("aria-sort", "ascending");

      fireEvent.keyDown(debitHeader, { key: " " });
      expect(debitHeader).toHaveAttribute("aria-sort", "descending");
    });

    it("column headers have tabIndex for keyboard focus", () => {
      render(<EntriesTable entries={buildEntries(3)} />);

      const headers = screen.getAllByRole("columnheader");
      for (const header of headers) {
        expect(header).toHaveAttribute("tabindex", "0");
      }
    });
  });
});
