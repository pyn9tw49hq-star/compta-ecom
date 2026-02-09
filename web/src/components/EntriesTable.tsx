"use client";

import { useState, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getChannelMeta } from "@/lib/channels";
import { formatCurrency, formatDate } from "@/lib/format";
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

const NUMERIC_COLUMNS = new Set<keyof Entry>(["debit", "credit"]);

type SortDirection = "ascending" | "descending";

interface EntriesTableProps {
  entries: Entry[];
}

/**
 * Interactive accounting entries table with pagination, filtering, and sorting.
 */
export default function EntriesTable({ entries }: EntriesTableProps) {
  const [selectedCanals, setSelectedCanals] = useState<Set<string>>(new Set());
  const [selectedJournal, setSelectedJournal] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [searchCompte, setSearchCompte] = useState("");

  const [sortColumn, setSortColumn] = useState<keyof Entry | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("ascending");

  const [currentPage, setCurrentPage] = useState(1);

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
    if (selectedJournal) {
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
  }, [entries, selectedCanals, selectedJournal, selectedTypes, searchCompte]);

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

  return (
    <div>
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

      <p className="text-sm text-muted-foreground mb-2">
        {filteredEntries.length} écritures sur {entries.length} total
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={
                    sortColumn === col.key ? sortDirection : "none"
                  }
                  tabIndex={0}
                  className="px-2 py-2 text-left font-medium cursor-pointer select-none hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
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
                      {sortDirection === "ascending" ? "↑" : "↓"}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedEntries.map((entry, i) => (
              <tr key={i} className="border-b hover:bg-muted/30">
                {COLUMNS.map((col) => (
                  <td
                    key={col.key}
                    className={`px-2 py-1.5 ${NUMERIC_COLUMNS.has(col.key) ? "text-right tabular-nums" : ""}`}
                  >
                    {renderCellValue(entry, col.key)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
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
      )}
    </div>
  );
}
