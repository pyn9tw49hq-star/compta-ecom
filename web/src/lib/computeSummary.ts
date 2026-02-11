/**
 * Replicate the Python _build_summary() logic on the frontend
 * for period-filtered transactions.
 */
import type { Transaction, Summary, Entry } from "./types";

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/**
 * Compute a Summary from a filtered array of Transactions.
 * `entries` is needed for ecritures_par_type and totaux.
 * `countryMap` maps country_code to display name (extracted from the original summary).
 */
export function computeSummary(
  transactions: Transaction[],
  entries: Entry[],
  countryMap: Record<string, string>,
): Summary {
  // --- Transactions par canal (unique by ref+channel, skip special_type) ---
  const transactionsParCanal: Record<string, number> = {};
  for (const t of transactions) {
    transactionsParCanal[t.channel] = (transactionsParCanal[t.channel] ?? 0) + 1;
  }

  // --- Ecritures par type ---
  const ecrituresParType: Record<string, number> = {};
  for (const e of entries) {
    ecrituresParType[e.type_ecriture] = (ecrituresParType[e.type_ecriture] ?? 0) + 1;
  }

  // --- Totaux ---
  let totalDebit = 0;
  let totalCredit = 0;
  for (const e of entries) {
    totalDebit += e.debit;
    totalCredit += e.credit;
  }

  // --- KPIs by channel (skip special_type transactions) ---
  const caHt: Record<string, number> = {};
  const caTtc: Record<string, number> = {};
  const prodHt: Record<string, number> = {};
  const portHt: Record<string, number> = {};
  const refundHt: Record<string, number> = {};
  const refundTtc: Record<string, number> = {};
  const refundNb: Record<string, number> = {};
  const salesNb: Record<string, number> = {};
  const commHt: Record<string, number> = {};
  const commTtc: Record<string, number> = {};
  const tvaCol: Record<string, number> = {};

  for (const t of transactions) {
    if (t.special_type !== null) continue;
    const c = t.channel;

    if (!(c in caHt)) {
      caHt[c] = caTtc[c] = 0;
      prodHt[c] = portHt[c] = 0;
      refundHt[c] = refundTtc[c] = 0;
      refundNb[c] = salesNb[c] = 0;
      commHt[c] = commTtc[c] = 0;
      tvaCol[c] = 0;
    }

    if (t.type === "sale") {
      salesNb[c] += 1;
      caHt[c] += t.amount_ht + t.shipping_ht;
      prodHt[c] += t.amount_ht;
      portHt[c] += t.shipping_ht;
      caTtc[c] += t.amount_ttc;
      tvaCol[c] += t.amount_tva + t.shipping_tva;
    } else if (t.type === "refund") {
      refundNb[c] += 1;
      refundHt[c] += Math.abs(t.amount_ht + t.shipping_ht);
      refundTtc[c] += Math.abs(t.amount_ttc);
    }

    commTtc[c] += Math.abs(t.commission_ttc);
    if (t.commission_ht !== null) {
      commHt[c] += Math.abs(t.commission_ht);
    }
  }

  // Round
  const channels = Object.keys(caHt).sort();
  for (const c of channels) {
    caHt[c] = round2(caHt[c]);
    caTtc[c] = round2(caTtc[c]);
    prodHt[c] = round2(prodHt[c]);
    portHt[c] = round2(portHt[c]);
    refundHt[c] = round2(refundHt[c]);
    refundTtc[c] = round2(refundTtc[c]);
    commHt[c] = round2(commHt[c]);
    commTtc[c] = round2(commTtc[c]);
    tvaCol[c] = round2(tvaCol[c]);
  }

  // Build output dicts
  const caParCanal: Summary["ca_par_canal"] = {};
  const remboursementsParCanal: Summary["remboursements_par_canal"] = {};
  const tauxRemboursementParCanal: Summary["taux_remboursement_par_canal"] = {};
  const commissionsParCanal: Summary["commissions_par_canal"] = {};
  const netVendeurParCanal: Summary["net_vendeur_par_canal"] = {};
  const tvaCollecteeParCanal: Summary["tva_collectee_par_canal"] = {};
  const ventilationCaParCanal: Summary["ventilation_ca_par_canal"] = {};

  for (const c of channels) {
    caParCanal[c] = { ht: caHt[c], ttc: caTtc[c] };
    remboursementsParCanal[c] = { count: refundNb[c], ht: refundHt[c], ttc: refundTtc[c] };
    tauxRemboursementParCanal[c] = salesNb[c] > 0
      ? Math.round(refundNb[c] / salesNb[c] * 1000) / 10
      : 0;
    commissionsParCanal[c] = { ht: commHt[c], ttc: commTtc[c] };
    netVendeurParCanal[c] = round2(caTtc[c] - commTtc[c] - refundTtc[c]);
    tvaCollecteeParCanal[c] = tvaCol[c];
    ventilationCaParCanal[c] = { produits_ht: prodHt[c], port_ht: portHt[c], total_ht: caHt[c] };
  }

  // --- Geo breakdown (sales only, skip special_type) ---
  const resolveCountry = (code: string): string => countryMap[code] ?? code;

  const geoGCount: Record<string, number> = {};
  const geoGCaTtc: Record<string, number> = {};
  const geoGCaHt: Record<string, number> = {};
  const geoCCount: Record<string, Record<string, number>> = {};
  const geoCCaTtc: Record<string, Record<string, number>> = {};
  const geoCCaHt: Record<string, Record<string, number>> = {};
  const tvaPaysCanal: Record<string, Record<string, Record<number, number>>> = {};

  for (const t of transactions) {
    if (t.special_type !== null || t.type !== "sale") continue;
    const country = resolveCountry(t.country_code);
    const canal = t.channel;
    const txCaHt = t.amount_ht + t.shipping_ht;
    const txTva = t.amount_tva + t.shipping_tva;

    // Global
    geoGCount[country] = (geoGCount[country] ?? 0) + 1;
    geoGCaTtc[country] = (geoGCaTtc[country] ?? 0) + t.amount_ttc;
    geoGCaHt[country] = (geoGCaHt[country] ?? 0) + txCaHt;

    // Per channel
    if (!(canal in geoCCount)) {
      geoCCount[canal] = {};
      geoCCaTtc[canal] = {};
      geoCCaHt[canal] = {};
      tvaPaysCanal[canal] = {};
    }
    geoCCount[canal][country] = (geoCCount[canal][country] ?? 0) + 1;
    geoCCaTtc[canal][country] = (geoCCaTtc[canal][country] ?? 0) + t.amount_ttc;
    geoCCaHt[canal][country] = (geoCCaHt[canal][country] ?? 0) + txCaHt;

    // TVA per country per channel
    if (!(country in tvaPaysCanal[canal])) {
      tvaPaysCanal[canal][country] = {};
    }
    tvaPaysCanal[canal][country][t.tva_rate] =
      (tvaPaysCanal[canal][country][t.tva_rate] ?? 0) + txTva;
  }

  // Build geo output
  const sortedCountries = Object.keys(geoGCaTtc).sort(
    (a, b) => geoGCaTtc[b] - geoGCaTtc[a],
  );
  const repartitionGeoGlobale: Summary["repartition_geo_globale"] = {};
  for (const country of sortedCountries) {
    repartitionGeoGlobale[country] = {
      count: geoGCount[country],
      ca_ttc: round2(geoGCaTtc[country]),
      ca_ht: round2(geoGCaHt[country]),
    };
  }

  const repartitionGeoParCanal: Summary["repartition_geo_par_canal"] = {};
  for (const canal of Object.keys(geoCCount).sort()) {
    const countries = Object.keys(geoCCaTtc[canal]).sort(
      (a, b) => geoCCaTtc[canal][b] - geoCCaTtc[canal][a],
    );
    repartitionGeoParCanal[canal] = {};
    for (const country of countries) {
      repartitionGeoParCanal[canal][country] = {
        count: geoCCount[canal][country],
        ca_ttc: round2(geoCCaTtc[canal][country]),
        ca_ht: round2(geoCCaHt[canal][country]),
      };
    }
  }

  // TVA per country per channel
  const tvaParPaysParCanal: Summary["tva_par_pays_par_canal"] = {};
  for (const canal of Object.keys(tvaPaysCanal).sort()) {
    tvaParPaysParCanal[canal] = {};
    for (const country of Object.keys(tvaPaysCanal[canal]).sort()) {
      const rates = Object.keys(tvaPaysCanal[canal][country])
        .map(Number)
        .sort((a, b) => b - a);
      tvaParPaysParCanal[canal][country] = rates.map((rate) => ({
        taux: rate,
        montant: round2(tvaPaysCanal[canal][country][rate]),
      }));
    }
  }

  return {
    transactions_par_canal: transactionsParCanal,
    ecritures_par_type: ecrituresParType,
    totaux: { debit: round2(totalDebit), credit: round2(totalCredit) },
    ca_par_canal: caParCanal,
    remboursements_par_canal: remboursementsParCanal,
    taux_remboursement_par_canal: tauxRemboursementParCanal,
    commissions_par_canal: commissionsParCanal,
    net_vendeur_par_canal: netVendeurParCanal,
    tva_collectee_par_canal: tvaCollecteeParCanal,
    ventilation_ca_par_canal: ventilationCaParCanal,
    repartition_geo_globale: repartitionGeoGlobale,
    repartition_geo_par_canal: repartitionGeoParCanal,
    tva_par_pays_par_canal: tvaParPaysParCanal,
  };
}

