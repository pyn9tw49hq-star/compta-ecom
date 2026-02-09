import { describe, it, expect } from "vitest";
import { formatCurrency, formatDate } from "@/lib/format";

describe("formatCurrency", () => {
  it("formats amount with thousands separator and 2 decimals", () => {
    const result = formatCurrency(1234.5);
    // French locale uses narrow no-break space (\u202F) as thousands separator
    expect(result).toMatch(/1\s*234,50/);
  });

  it("formats zero as 0,00", () => {
    expect(formatCurrency(0)).toBe("0,00");
  });

  it("formats small amount without thousands separator", () => {
    expect(formatCurrency(42.1)).toBe("42,10");
  });

  it("formats negative amount", () => {
    const result = formatCurrency(-500.99);
    expect(result).toMatch(/-500,99/);
  });
});

describe("formatDate", () => {
  it("formats ISO date to French DD/MM/YYYY", () => {
    expect(formatDate("2026-01-15")).toBe("15/01/2026");
  });

  it("formats another date correctly", () => {
    expect(formatDate("2025-12-01")).toBe("01/12/2025");
  });
});
