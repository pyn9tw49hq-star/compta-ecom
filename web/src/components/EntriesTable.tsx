"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getChannelMeta } from "@/lib/channels";
import { formatCurrency, formatDate } from "@/lib/format";
import { useNewDesign } from "@/hooks/useNewDesign";
import { Search, ChevronDown } from "lucide-react";
import type { Entry } from "@/lib/types";

const PAGE_SIZE = 50;

const COLUMNS: { key: keyof Entry; label: string }[] = [
  { key: "date", label: "Date" },
  { key: "journal", label: "Journal" },
  { key: "compte", label: "Compte" },
  { key: "libelle", label: "Libellé" },
  { key: "debit", label: "Débit" },
  { key: "credit", label: "Crédit" },
  { key: "piece", label: "Pièce" },
  { key: "lettrage", label: "Lettrage" },
  { key: "canal", label: "Canal" },
  { key: "type_ecriture", label: "Type" },
];

/** V2 column widths mapped by column key */
const V2_COL_WIDTHS: Partial<Record<keyof Entry, string>> = {
  date: "w-[100px]",
  journal: "w-[80px]",
  compte: "w-[100px]",
  debit: "w-[100px]",
  credit: "w-[100px]",
  piece: "w-[120px]",
  lettrage: "w-[100px]",
  canal: "w-[100px]",
  type_ecriture: "w-[80px]",
};

const NUMERIC_COLUMNS = new Set<keyof Entry>(["debit", "credit"]);

const CANAL_COLORS: Record<string, string> = {
  shopify: "text-[#95BF47]",
  manomano: "text-[#00B2A9]",
  decathlon: "text-[#0055A0]",
  leroy_merlin: "text-[#2D8C3C]",
};

type SortDirection = "ascending" | "descending";

interface EntriesTableProps {
  entries: Entry[];
}

/**
 * Interactive accounting entries table with pagination, filtering, and sorting.
 */
export default function EntriesTable({ entries }: EntriesTableProps) {
  const isV2 = useNewDesign();

  const [selectedCanals, setSelectedCanals] = useState<Set<string>>(new Set());
  const [selectedJournals, setSelectedJournals] = useState<Set<string>>(new Set());
  const [selectedJournal, setSelectedJournal] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [searchCompte, setSearchCompte] = useState("");

  const [sortColumn, setSortColumn] = useState<keyof Entry | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("ascending");

  const [currentPage, setCurrentPage] = useState(1);

  // V2 popover open states
  const [canalOpen, setCanalOpen] = useState(false);
  const [journalOpen, setJournalOpen] = useState(false);
  const [typeOpen, setTypeOpen] = useState(false);
  const filterBarRef = useRef<HTMLDivElement>(null);

  // Close popovers on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (filterBarRef.current && !filterBarRef.current.contains(e.target as Node)) {
        setCanalOpen(false);
        setJournalOpen(false);
        setTypeOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const uniqueCanals = useMemo(
    () => Array.from(new Set(entries.map((e) => e.canal))).sort(),
    [entries],
  );
  const uniqueJournals = useMemo(
    () => Array.from(new Set(entries.map((e) => e.journal))).sort(),
    [entries],
  );
  const uniqueTypes = useMemo(
    () => Array.from(new Set(entries.map((e) => e.type_ecriture))).sort(),
    [entries],
  );

  const filteredEntries = useMemo(() => {
    let result = entries;
    if (selectedCanals.size > 0) {
      result = result.filter((e) => selectedCanals.has(e.canal));
    }
    if (selectedJournals.size > 0) {
      result = result.filter((e) => selectedJournals.has(e.journal));
    } else if (selectedJournal) {
      result = result.filter((e) => e.journal === selectedJournal);
    }
    if (selectedTypes.size > 0) {
      result = result.filter((e) => selectedTypes.has(e.type_ecriture));
    }
    if (searchCompte) {
      const lower = searchCompte.toLowerCase();
      result = result.filter((e) => e.compte.toLowerCase().includes(lower));
    }
    return result;
  }, [entries, selectedCanals, selectedJournals, selectedJournal, selectedTypes, searchCompte]);

  const sortedEntries = useMemo(() => {
    if (!sortColumn) return filteredEntries;
    const col = sortColumn;
    const dir = sortDirection === "ascending" ? 1 : -1;
    return filteredEntries.slice().sort((a, b) => {
      if (NUMERIC_COLUMNS.has(col)) {
        return dir * ((a[col] as number) - (b[col] as number));
      }
      return dir * String(a[col]).localeCompare(String(b[col]), "fr");
    });
  }, [filteredEntries, sortColumn, sortDirection]);

  const totalPages = Math.ceil(sortedEntries.length / PAGE_SIZE);
  const paginatedEntries = sortedEntries.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  const handleSort = (column: keyof Entry) => {
    if (sortColumn === column) {
      setSortDirection((d) =>
        d === "ascending" ? "descending" : "ascending",
      );
    } else {
      setSortColumn(column);
      setSortDirection("ascending");
    }
  };

  const toggleCanal = (canal: string) => {
    setSelectedCanals((prev) => {
      const next = new Set(prev);
      if (next.has(canal)) next.delete(canal);
      else next.add(canal);
      return next;
    });
    setCurrentPage(1);
  };

  const toggleType = (type: string) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
    setCurrentPage(1);
  };


  const renderCellValue = (entry: Entry, key: keyof Entry) => {
    const value = entry[key];
    switch (key) {
      case "date":
        return formatDate(value as string);
      case "debit":
      case "credit":
        return formatCurrency(value as number);
      case "canal": {
        const meta = getChannelMeta(value as string);
        if (isV2) {
          return <span className="font-medium">{meta.label}</span>;
        }
        return (
          <Badge variant="outline" className={meta.badgeClass}>
            {meta.label}
          </Badge>
        );
      }
      default:
        return String(value);
    }
  };

  /** V2 cell class based on column key */
  const v2CellClass = (key: keyof Entry): string => {
    const width = V2_COL_WIDTHS[key] ?? "";
    if (NUMERIC_COLUMNS.has(key)) return `px-4 py-3 text-right font-mono tabular-nums ${width}`;
    if (key === "compte") return `px-4 py-3 text-primary font-mono tabular-nums ${width}`;
    if (key === "libelle") return "px-4 py-3 min-w-0";
    return `px-4 py-3 ${width}`;
  };

  return (
    <div>
      {/* ── Filter bar ── */}
      {isV2 ? (
        <div className="flex items-center gap-3 mb-6" ref={filterBarRef}>
          {/* Canal popover */}
          <div className="relative">
            <button
              onClick={() => { setCanalOpen(!canalOpen); setJournalOpen(false); setTypeOpen(false); }}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
            >
              <span className="text-muted-foreground">Canal:</span>
              <span className="font-medium">{selectedCanals.size === 0 ? "Tous" : `${selectedCanals.size} sélectionné(s)`}</span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </button>
            {canalOpen && (
              <div className="absolute top-full left-0 mt-1 w-56 rounded-lg border border-border bg-card shadow-lg z-50 py-1">
                {uniqueCanals.map((canal) => (
                  <label key={canal} className="flex items-center gap-3 px-3 py-2 hover:bg-muted/50 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={selectedCanals.has(canal)}
                      onChange={() => {
                        const next = new Set(selectedCanals);
                        if (next.has(canal)) next.delete(canal);
                        else next.add(canal);
                        setSelectedCanals(next);
                        setCurrentPage(1);
                      }}
                      className="rounded border-border text-primary focus:ring-primary"
                    />
                    <span>{getChannelMeta(canal).label}</span>
                  </label>
                ))}
                {selectedCanals.size > 0 && (
                  <button
                    onClick={() => { setSelectedCanals(new Set()); setCurrentPage(1); }}
                    className="w-full text-left px-3 py-2 text-xs text-primary hover:bg-muted/50 border-t border-border mt-1"
                  >
                    Effacer la sélection
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Journal popover */}
          <div className="relative">
            <button
              onClick={() => { setJournalOpen(!journalOpen); setCanalOpen(false); setTypeOpen(false); }}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
            >
              <span className="text-muted-foreground">Journal:</span>
              <span className="font-medium">{selectedJournals.size === 0 ? "Tous" : `${selectedJournals.size} sélectionné(s)`}</span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </button>
            {journalOpen && (
              <div className="absolute top-full left-0 mt-1 w-56 rounded-lg border border-border bg-card shadow-lg z-50 py-1">
                {uniqueJournals.map((j) => (
                  <label key={j} className="flex items-center gap-3 px-3 py-2 hover:bg-muted/50 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={selectedJournals.has(j)}
                      onChange={() => {
                        const next = new Set(selectedJournals);
                        if (next.has(j)) next.delete(j);
                        else next.add(j);
                        setSelectedJournals(next);
                        setCurrentPage(1);
                      }}
                      className="rounded border-border text-primary focus:ring-primary"
                    />
                    <span>{j}</span>
                  </label>
                ))}
                {selectedJournals.size > 0 && (
                  <button
                    onClick={() => { setSelectedJournals(new Set()); setCurrentPage(1); }}
                    className="w-full text-left px-3 py-2 text-xs text-primary hover:bg-muted/50 border-t border-border mt-1"
                  >
                    Effacer la sélection
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Type popover */}
          <div className="relative">
            <button
              onClick={() => { setTypeOpen(!typeOpen); setCanalOpen(false); setJournalOpen(false); }}
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/50 transition-colors"
            >
              <span className="text-muted-foreground">Type:</span>
              <span className="font-medium">{selectedTypes.size === 0 ? "Tous" : `${selectedTypes.size} sélectionné(s)`}</span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </button>
            {typeOpen && (
              <div className="absolute top-full left-0 mt-1 w-56 rounded-lg border border-border bg-card shadow-lg z-50 py-1">
                {uniqueTypes.map((type) => (
                  <label key={type} className="flex items-center gap-3 px-3 py-2 hover:bg-muted/50 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={selectedTypes.has(type)}
                      onChange={() => {
                        const next = new Set(selectedTypes);
                        if (next.has(type)) next.delete(type);
                        else next.add(type);
                        setSelectedTypes(next);
                        setCurrentPage(1);
                      }}
                      className="rounded border-border text-primary focus:ring-primary"
                    />
                    <span>{type}</span>
                  </label>
                ))}
                {selectedTypes.size > 0 && (
                  <button
                    onClick={() => { setSelectedTypes(new Set()); setCurrentPage(1); }}
                    className="w-full text-left px-3 py-2 text-xs text-primary hover:bg-muted/50 border-t border-border mt-1"
                  >
                    Effacer la sélection
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Search input with icon */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={searchCompte}
              onChange={(e) => {
                setSearchCompte(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Rechercher un compte..."
              className="w-full rounded-lg border border-border bg-card pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground"
            />
          </div>
        </div>
      ) : (
        <div className="mb-4 space-y-3">
          <div>
            <span className="text-sm font-medium mr-2">Canal :</span>
            {uniqueCanals.map((canal) => (
              <label
                key={canal}
                className="inline-flex items-center mr-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selectedCanals.has(canal)}
                  onChange={() => toggleCanal(canal)}
                  className="mr-1"
                />
                {getChannelMeta(canal).label}
              </label>
            ))}
          </div>

          <div>
            <label
              className="text-sm font-medium mr-2"
              htmlFor="filter-journal"
            >
              Journal :
            </label>
            <select
              id="filter-journal"
              value={selectedJournal}
              onChange={(e) => {
                setSelectedJournal(e.target.value);
                setCurrentPage(1);
              }}
              className="rounded-md border border-input bg-transparent px-2 py-1 text-sm"
            >
              <option value="">Tous</option>
              {uniqueJournals.map((j) => (
                <option key={j} value={j}>
                  {j}
                </option>
              ))}
            </select>
          </div>

          <div>
            <span className="text-sm font-medium mr-2">Type :</span>
            {uniqueTypes.map((type) => (
              <label
                key={type}
                className="inline-flex items-center mr-3 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selectedTypes.has(type)}
                  onChange={() => toggleType(type)}
                  className="mr-1"
                />
                {type}
              </label>
            ))}
          </div>

          <div>
            <label
              className="text-sm font-medium mr-2"
              htmlFor="filter-compte"
            >
              Compte :
            </label>
            <input
              id="filter-compte"
              type="text"
              value={searchCompte}
              onChange={(e) => {
                setSearchCompte(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Recherche..."
              className="rounded-md border border-input bg-transparent px-2 py-1 text-sm"
            />
          </div>
        </div>
      )}

      {/* ── Entry count (V1 only — V2 shows it in pagination footer) ── */}
      {!isV2 && (
        <p className="text-sm text-muted-foreground mb-2">
          {filteredEntries.length} écritures sur {entries.length} total
        </p>
      )}

      {/* ── Table ── */}
      <div className={isV2 ? "rounded-xl border border-border bg-card overflow-hidden" : "overflow-x-auto"}>
        <table className={isV2 ? "w-full text-[13px]" : "w-full text-sm"}>
          <thead>
            <tr className={isV2 ? "" : "border-b"}>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={
                    sortColumn === col.key ? sortDirection : "none"
                  }
                  tabIndex={0}
                  className={
                    isV2
                      ? `bg-muted text-xs font-semibold uppercase tracking-wide text-muted-foreground px-4 py-3 text-left cursor-pointer select-none hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 ${V2_COL_WIDTHS[col.key] ?? ""} ${NUMERIC_COLUMNS.has(col.key) ? "text-right" : ""}`
                      : "px-2 py-2 text-left font-medium cursor-pointer select-none hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
                  }
                  onClick={() => handleSort(col.key)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleSort(col.key);
                    }
                  }}
                >
                  {col.label}
                  {sortColumn === col.key && (
                    <span className="ml-1" aria-hidden="true">
                      {sortDirection === "ascending" ? "\u2191" : "\u2193"}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedEntries.map((entry, i) => (
              <tr
                key={i}
                className={
                  isV2
                    ? i % 2 === 0
                      ? "bg-card hover:bg-muted/30"
                      : "bg-muted/50 hover:bg-muted/70"
                    : "border-b hover:bg-muted/30"
                }
              >
                {COLUMNS.map((col) => (
                  <td
                    key={col.key}
                    className={
                      isV2
                        ? `${v2CellClass(col.key)}${col.key === "canal" ? ` ${CANAL_COLORS[entry.canal.toLowerCase()] || "text-foreground"}` : ""}`
                        : `px-2 py-1.5 ${NUMERIC_COLUMNS.has(col.key) ? "text-right tabular-nums" : ""}`
                    }
                  >
                    {renderCellValue(entry, col.key)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ── */}
      {isV2 ? (
        totalPages > 1 ? (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span className="text-sm text-muted-foreground">
              {filteredEntries.length.toLocaleString("fr-FR")} écritures sur{" "}
              {entries.length.toLocaleString("fr-FR")} total
            </span>
            <span className="text-sm text-muted-foreground">
              Page {currentPage} sur {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                aria-label="Page précédente"
              >
                &larr; Précédent
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setCurrentPage((p) => Math.min(totalPages, p + 1))
                }
                disabled={currentPage === totalPages}
                aria-label="Page suivante"
              >
                Suivant &rarr;
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center px-4 py-3 border-t border-border">
            <span className="text-sm text-muted-foreground">
              {filteredEntries.length.toLocaleString("fr-FR")} écritures sur{" "}
              {entries.length.toLocaleString("fr-FR")} total
            </span>
          </div>
        )
      ) : (
        totalPages > 1 && (
          <div className="mt-3 flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              aria-label="Page précédente"
            >
              Précédent
            </Button>
            <span className="text-sm">
              Page {currentPage} sur {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setCurrentPage((p) => Math.min(totalPages, p + 1))
              }
              disabled={currentPage === totalPages}
              aria-label="Page suivante"
            >
              Suivant
            </Button>
          </div>
        )
      )}
    </div>
  );
}
