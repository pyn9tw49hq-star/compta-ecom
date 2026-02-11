import type { ChannelMeta } from "./channels";

export interface Entry {
  date: string;
  journal: string;
  compte: string;
  libelle: string;
  debit: number;
  credit: number;
  piece: string;
  lettrage: string;
  canal: string;
  type_ecriture: string;
}

export interface Anomaly {
  type: string;
  severity: "error" | "warning" | "info";
  canal: string;
  reference: string;
  detail: string;
}

export interface Summary {
  transactions_par_canal: Record<string, number>;
  ecritures_par_type: Record<string, number>;
  totaux: { debit: number; credit: number };
  ca_par_canal: Record<string, { ht: number; ttc: number }>;
  remboursements_par_canal: Record<string, { count: number; ht: number; ttc: number }>;
  taux_remboursement_par_canal: Record<string, number>;
  commissions_par_canal: Record<string, { ht: number; ttc: number }>;
  net_vendeur_par_canal: Record<string, number>;
  tva_collectee_par_canal: Record<string, number>;
  ventilation_ca_par_canal: Record<string, { produits_ht: number; port_ht: number; total_ht: number }>;
  repartition_geo_globale: Record<string, { count: number; ca_ttc: number; ca_ht: number }>;
  repartition_geo_par_canal: Record<string, Record<string, { count: number; ca_ttc: number; ca_ht: number }>>;
  tva_par_pays_par_canal: Record<string, Record<string, { taux: number; montant: number }[]>>;
}

export interface Transaction {
  reference: string;
  channel: string;
  date: string; // YYYY-MM-DD
  type: "sale" | "refund";
  amount_ht: number;
  amount_tva: number;
  amount_ttc: number;
  shipping_ht: number;
  shipping_tva: number;
  tva_rate: number;
  country_code: string;
  commission_ttc: number;
  commission_ht: number | null;
  special_type: string | null;
}

export interface ProcessResponse {
  entries: Entry[];
  anomalies: Anomaly[];
  summary: Summary;
  transactions: Transaction[];
  country_names: Record<string, string>;
}

export interface UploadedFile {
  file: File;
  channel: string | null;
}

export interface FileSlotConfig {
  key: string;
  pattern: string;
  patternHuman: string;
  required: boolean;
  regex: RegExp | null;
}

export interface ChannelConfig {
  key: string;
  meta: ChannelMeta;
  files: FileSlotConfig[];
}

export interface FileMatchResult {
  file: File;
  channel: string | null;
  slotKey: string | null;
  suggestion: string | null;
}

export interface ChannelStatus {
  channelKey: string;
  label: string;
  requiredCount: number;
  uploadedRequiredCount: number;
  isComplete: boolean;
}
