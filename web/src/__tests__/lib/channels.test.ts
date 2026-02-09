import { describe, it, expect } from "vitest";
import { detectChannel, getChannelMeta, CHANNEL_META, UNKNOWN_CHANNEL_META } from "@/lib/channels";

describe("detectChannel", () => {
  it("detects Shopify sales file", () => {
    expect(detectChannel("Ventes Shopify Janvier.csv")).toBe("shopify");
  });

  it("detects Shopify transactions file", () => {
    expect(detectChannel("Transactions Shopify 2026-01.csv")).toBe("shopify");
  });

  it("detects Shopify payout details file", () => {
    expect(detectChannel("Détails versements 2026-01.csv")).toBe("shopify");
  });

  it("detects ManoMano CA file", () => {
    expect(detectChannel("CA Manomano 2026-01.csv")).toBe("manomano");
  });

  it("detects ManoMano payout file", () => {
    expect(detectChannel("Detail versement Manomano mars.csv")).toBe("manomano");
  });

  it("detects Décathlon file", () => {
    expect(detectChannel("Decathlon export.csv")).toBe("decathlon");
  });

  it("detects Leroy Merlin file", () => {
    expect(detectChannel("Leroy Merlin mars.csv")).toBe("leroy_merlin");
  });

  it("returns null for unknown CSV file", () => {
    expect(detectChannel("random.csv")).toBeNull();
  });

  it("returns null for non-CSV file", () => {
    expect(detectChannel("data.xlsx")).toBeNull();
  });

  it("returns null for payout_details path-based file (SF-3 limitation)", () => {
    // The browser file.name only gives the filename, not the parent directory
    // So a file like "2026-01-payout.csv" from "Detail transactions par versements/"
    // cannot be matched — this is expected behavior
    expect(detectChannel("2026-01-payout.csv")).toBeNull();
  });

  it("is case-insensitive", () => {
    expect(detectChannel("ventes shopify test.csv")).toBe("shopify");
    expect(detectChannel("DECATHLON EXPORT.CSV")).toBe("decathlon");
  });
});

describe("getChannelMeta", () => {
  it("returns metadata for known channel", () => {
    const meta = getChannelMeta("shopify");
    expect(meta.label).toBe("Shopify");
    expect(meta).toBe(CHANNEL_META.shopify);
  });

  it("returns unknown metadata for null channel", () => {
    const meta = getChannelMeta(null);
    expect(meta.label).toBe("Canal inconnu");
    expect(meta).toBe(UNKNOWN_CHANNEL_META);
  });

  it("returns unknown metadata for unrecognized channel string", () => {
    const meta = getChannelMeta("amazon");
    expect(meta.label).toBe("Canal inconnu");
  });
});
