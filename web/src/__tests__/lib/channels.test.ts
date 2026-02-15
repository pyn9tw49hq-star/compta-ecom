import { describe, it, expect } from "vitest";
import {
  detectChannel,
  getChannelMeta,
  CHANNEL_META,
  UNKNOWN_CHANNEL_META,
  CHANNEL_CONFIGS,
  CHANNEL_KEYWORDS,
  matchFileToSlot,
  suggestRename,
} from "@/lib/channels";

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

  it("detects Shopify returns file", () => {
    expect(detectChannel("Total des retours par commande (1).csv")).toBe("shopify");
  });

  it("detects Shopify payout_details file", () => {
    expect(detectChannel("Detail transactions par versements 1.csv")).toBe("shopify");
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

describe("CHANNEL_CONFIGS", () => {
  it("has exactly 4 channels", () => {
    expect(CHANNEL_CONFIGS).toHaveLength(4);
  });

  it("Shopify has 5 files (3 required + 2 optional)", () => {
    const shopify = CHANNEL_CONFIGS.find((c) => c.key === "shopify")!;
    expect(shopify.files).toHaveLength(5);
    expect(shopify.files.filter((f) => f.required)).toHaveLength(3);
    expect(shopify.files.filter((f) => !f.required)).toHaveLength(2);
  });

  it("ManoMano has 3 required files", () => {
    const manomano = CHANNEL_CONFIGS.find((c) => c.key === "manomano")!;
    expect(manomano.files).toHaveLength(3);
    expect(manomano.files.every((f) => f.required)).toBe(true);
  });

  it("Décathlon has 1 required file", () => {
    const decathlon = CHANNEL_CONFIGS.find((c) => c.key === "decathlon")!;
    expect(decathlon.files).toHaveLength(1);
    expect(decathlon.files[0].required).toBe(true);
  });

  it("Leroy Merlin has 1 required file", () => {
    const lm = CHANNEL_CONFIGS.find((c) => c.key === "leroy_merlin")!;
    expect(lm.files).toHaveLength(1);
    expect(lm.files[0].required).toBe(true);
  });

  it("has 8 required + 2 optional = 10 total file slots", () => {
    const allFiles = CHANNEL_CONFIGS.flatMap((c) => c.files);
    expect(allFiles).toHaveLength(10);
    expect(allFiles.filter((f) => f.required)).toHaveLength(8);
    expect(allFiles.filter((f) => !f.required)).toHaveLength(2);
  });

  it("payout_details slot has regex defined, required false, multi true", () => {
    const shopify = CHANNEL_CONFIGS.find((c) => c.key === "shopify")!;
    const pd = shopify.files.find((f) => f.key === "payout_details")!;
    expect(pd.regex).toBeInstanceOf(RegExp);
    expect(pd.required).toBe(false);
    expect(pd.multi).toBe(true);
  });

  it("Shopify has fileGroups with 2 groups", () => {
    const shopify = CHANNEL_CONFIGS.find((c) => c.key === "shopify")!;
    expect(shopify.fileGroups).toBeDefined();
    expect(shopify.fileGroups).toHaveLength(2);
    expect(shopify.fileGroups![0]).toEqual({
      label: "Mode complet",
      slots: ["sales", "transactions", "payouts"],
    });
    expect(shopify.fileGroups![1]).toEqual({
      label: "Mode avoirs",
      slots: ["returns"],
    });
  });

  it("other channels have no fileGroups", () => {
    for (const config of CHANNEL_CONFIGS) {
      if (config.key !== "shopify") {
        expect(config.fileGroups).toBeUndefined();
      }
    }
  });

  it("each channel has a valid meta reference", () => {
    for (const config of CHANNEL_CONFIGS) {
      expect(config.meta).toBe(CHANNEL_META[config.key]);
    }
  });

  it("CHANNEL_KEYWORDS has entries for all 4 channels", () => {
    const channelKeys = CHANNEL_CONFIGS.map((c) => c.key);
    for (const key of channelKeys) {
      expect(CHANNEL_KEYWORDS[key]).toBeDefined();
      expect(CHANNEL_KEYWORDS[key].length).toBeGreaterThan(0);
    }
  });
});

describe("matchFileToSlot", () => {
  it("matches Shopify sales file", () => {
    expect(matchFileToSlot("Ventes Shopify Janvier 2026.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "shopify", slotKey: "sales" });
  });

  it("matches Shopify transactions file", () => {
    expect(matchFileToSlot("Transactions Shopify 2026-01.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "shopify", slotKey: "transactions" });
  });

  it("matches Shopify payouts file (accented)", () => {
    expect(matchFileToSlot("Détails versements 2026-01.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "shopify", slotKey: "payouts" });
  });

  it("matches Shopify payouts file (non-accented variant)", () => {
    expect(matchFileToSlot("Details versements Fev.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "shopify", slotKey: "payouts" });
  });

  it("matches ManoMano CA file", () => {
    expect(matchFileToSlot("CA Manomano 01-2026.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "manomano", slotKey: "ca" });
  });

  it("matches ManoMano payouts file", () => {
    expect(matchFileToSlot("Detail versement Manomano mars.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "manomano", slotKey: "payouts" });
  });

  it("matches Décathlon file", () => {
    expect(matchFileToSlot("Decathlon export.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "decathlon", slotKey: "data" });
  });

  it("matches Leroy Merlin file", () => {
    expect(matchFileToSlot("Leroy Merlin mars.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "leroy_merlin", slotKey: "data" });
  });

  it("returns null for unknown file", () => {
    expect(matchFileToSlot("random.csv", CHANNEL_CONFIGS)).toBeNull();
  });

  it("matches Shopify returns file", () => {
    expect(matchFileToSlot("Total des retours par commande (1).csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "shopify", slotKey: "returns" });
  });

  it("matches Shopify payout_details file", () => {
    expect(matchFileToSlot("Detail transactions par versements 1.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "shopify", slotKey: "payout_details" });
  });

  it("matches Shopify payout_details file (variant)", () => {
    expect(matchFileToSlot("Detail transactions par versements 5.csv", CHANNEL_CONFIGS))
      .toEqual({ channel: "shopify", slotKey: "payout_details" });
  });
});

describe("suggestRename", () => {
  const shopifyPayoutsSlot = CHANNEL_CONFIGS
    .find((c) => c.key === "shopify")!
    .files.find((f) => f.key === "payouts")!;
  const shopifySalesSlot = CHANNEL_CONFIGS
    .find((c) => c.key === "shopify")!
    .files.find((f) => f.key === "sales")!;
  const manomanoCaSlot = CHANNEL_CONFIGS
    .find((c) => c.key === "manomano")!
    .files.find((f) => f.key === "ca")!;

  it("suggests rename for file with shopify keyword and missing payouts slot", () => {
    const missing = [{ channel: "shopify", slot: shopifyPayoutsSlot }];
    expect(suggestRename("export_shopify_payouts.csv", missing))
      .toBe(shopifyPayoutsSlot.patternHuman);
  });

  it("suggests rename for file with shopify keyword and missing sales slot", () => {
    const missing = [{ channel: "shopify", slot: shopifySalesSlot }];
    expect(suggestRename("VENTE SHOPIFY.csv", missing))
      .toBe(shopifySalesSlot.patternHuman);
  });

  it("suggests rename for file with manomano keyword and missing ca slot", () => {
    const missing = [{ channel: "manomano", slot: manomanoCaSlot }];
    expect(suggestRename("CA_Manomano_01-2025.csv", missing))
      .toBe(manomanoCaSlot.patternHuman);
  });

  it("returns null for file without any channel keyword", () => {
    const missing = [{ channel: "shopify", slot: shopifySalesSlot }];
    expect(suggestRename("données.csv", missing)).toBeNull();
  });

  it("returns null when channel has no missing slot", () => {
    expect(suggestRename("export_shopify.csv", [])).toBeNull();
  });
});
