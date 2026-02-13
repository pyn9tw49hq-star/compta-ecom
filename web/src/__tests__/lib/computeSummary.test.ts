import { describe, it, expect } from "vitest";
import { computeSummary } from "@/lib/computeSummary";
import type { Transaction, Entry } from "@/lib/types";

function makeTx(overrides: Partial<Transaction> = {}): Transaction {
  return {
    reference: "#1001",
    channel: "shopify",
    date: "2026-01-15",
    type: "sale",
    amount_ht: 100,
    amount_tva: 20,
    amount_ttc: 120,
    shipping_ht: 0,
    shipping_tva: 0,
    tva_rate: 20,
    country_code: "250",
    commission_ttc: 5,
    commission_ht: 0,
    special_type: null,
    ...overrides,
  };
}

function makeEntry(overrides: Partial<Entry> = {}): Entry {
  return {
    date: "2026-01-15",
    journal: "VE",
    compte: "411SHOPIFY",
    libelle: "Vente #1001",
    debit: 0,
    credit: 120,
    piece: "#1001",
    lettrage: "1001",
    canal: "shopify",
    type_ecriture: "refund",
    ...overrides,
  };
}

describe("computeSummary — returns_avoir transactions", () => {
  it("includes returns_avoir in refund KPIs", () => {
    const txs: Transaction[] = [
      makeTx({
        reference: "#1085",
        type: "refund",
        special_type: "returns_avoir",
        amount_ht: 0,
        amount_tva: 0,
        amount_ttc: 8,
        shipping_ht: 6.67,
        shipping_tva: 1.33,
        commission_ttc: 0,
        commission_ht: 0,
      }),
      makeTx({
        reference: "#1113",
        type: "refund",
        special_type: "returns_avoir",
        amount_ht: 12.9,
        amount_tva: 8,
        amount_ttc: 20.9,
        shipping_ht: 0,
        shipping_tva: 0,
        commission_ttc: 0,
        commission_ht: 0,
      }),
    ];

    const entries: Entry[] = [
      makeEntry({ debit: 0, credit: 8 }),
      makeEntry({ debit: 8, credit: 0 }),
      makeEntry({ debit: 0, credit: 20.9 }),
      makeEntry({ debit: 20.9, credit: 0 }),
    ];

    const summary = computeSummary(txs, entries, { "250": "France" });

    // Refund KPIs populated
    expect(summary.remboursements_par_canal.shopify).toBeDefined();
    expect(summary.remboursements_par_canal.shopify.count).toBe(2);
    expect(summary.remboursements_par_canal.shopify.ttc).toBe(28.9);
    expect(summary.remboursements_par_canal.shopify.ht).toBe(19.57);

    // No CA (only refunds)
    expect(summary.ca_par_canal.shopify.ttc).toBe(0);
    expect(summary.ca_par_canal.shopify.ht).toBe(0);

    // Net vendeur negative (0 CA - 0 comm - 28.9 refund)
    expect(summary.net_vendeur_par_canal.shopify).toBe(-28.9);
  });

  it("excludes other special_type from KPIs", () => {
    const txs: Transaction[] = [
      makeTx({
        type: "refund",
        special_type: "orphan_settlement",
        amount_ttc: 50,
      }),
    ];

    const summary = computeSummary(txs, [], {});

    // No channel should appear in financial KPIs
    expect(Object.keys(summary.ca_par_canal)).toHaveLength(0);
    expect(Object.keys(summary.remboursements_par_canal)).toHaveLength(0);
  });

  it("mixes normal sales and returns_avoir correctly", () => {
    const txs: Transaction[] = [
      makeTx({
        reference: "#2001",
        type: "sale",
        special_type: null,
        amount_ht: 100,
        amount_tva: 20,
        amount_ttc: 120,
        commission_ttc: 5,
        commission_ht: 0,
      }),
      makeTx({
        reference: "#2002",
        type: "refund",
        special_type: "returns_avoir",
        amount_ht: 30,
        amount_tva: 6,
        amount_ttc: 36,
        shipping_ht: 0,
        shipping_tva: 0,
        commission_ttc: 0,
        commission_ht: 0,
      }),
    ];

    const summary = computeSummary(txs, [], {});

    // CA from the sale
    expect(summary.ca_par_canal.shopify.ttc).toBe(120);

    // Refund from the avoir
    expect(summary.remboursements_par_canal.shopify.count).toBe(1);
    expect(summary.remboursements_par_canal.shopify.ttc).toBe(36);

    // Net vendeur = 120 - 5 (comm) - 36 (refund) = 79
    expect(summary.net_vendeur_par_canal.shopify).toBe(79);

    // Refund rate = 1 refund / 1 sale * 100 = 100%
    expect(summary.taux_remboursement_par_canal.shopify).toBe(100);
  });
});
