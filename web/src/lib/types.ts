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
  repartition_geo_globale: Record<string, { count: number; ca_ttc: number }>;
  repartition_geo_par_canal: Record<string, Record<string, { count: number; ca_ttc: number }>>;
}

export interface ProcessResponse {
  entries: Entry[];
  anomalies: Anomaly[];
  summary: Summary;
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
