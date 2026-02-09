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
