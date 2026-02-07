"""Parser mutualisé pour les fichiers CSV Mirakl (Décathlon & Leroy Merlin)."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import Anomaly, NormalizedTransaction, ParseError, ParseResult, PayoutSummary
from compta_ecom.parsers.base import BaseParser

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Numéro de commande",
    "Type",
    "Date de commande",
    "Date du cycle de paiement",
    "Montant",
]

KNOWN_LINE_TYPES = {"Montant", "Frais de port", "Commission", "Taxe sur la commission", "Paiement", "Abonnement"}
ORDER_LINE_TYPES = {"Montant", "Frais de port", "Commission", "Taxe sur la commission"}

DATE_FORMAT = "%Y-%m-%d"

# Aliases : colonne attendue → alternatives dans les exports réels
COLUMN_ALIASES: dict[str, list[str]] = {
    "Date de commande": ["Date de création", "Date de transaction"],
}

# Normalisation des Type : valeur réelle → valeur attendue par le parser
TYPE_ALIASES: dict[str, str] = {
    "Montant de commande": "Montant",
    "Taxe sur commission": "Taxe sur la commission",
    "Frais d'abonnement": "Abonnement",
    # Remboursements — traités comme leurs équivalents avec montants négatifs
    "Remboursement de montant de commande": "Montant",
    "Remboursement de frais de port": "Frais de port",
    "Remboursement de commission": "Commission",
    "Remboursement de taxe sur commission": "Taxe sur la commission",
    # Lignes de taxe Leroy Merlin — ignorées car la TVA est recalculée
    "Taxe sur commande": "Taxe sur commande",
    "Taxe sur frais de port": "Taxe sur frais de port",
    "Taxe sur abonnement": "Taxe sur abonnement",
}

# Types de taxe explicite (Leroy Merlin) — ignorées si le parser calcule la TVA
TAX_LINE_TYPES = {"Taxe sur commande", "Taxe sur frais de port", "Taxe sur abonnement"}

# Mapping nom de pays (Canal de diffusion) → code alpha2
COUNTRY_NAME_TO_ALPHA2: dict[str, str] = {
    "France": "FR",
    "Belgique": "BE",
    "Belgium": "BE",
    "Italie": "IT",
    "Italy": "IT",
    "Espagne": "ES",
    "Spain": "ES",
    "Allemagne": "DE",
    "Germany": "DE",
    "Pays-Bas": "NL",
    "Netherlands": "NL",
    "Portugal": "PT",
    "Autriche": "AT",
    "Austria": "AT",
    "Pologne": "PL",
    "Poland": "PL",
    "Suède": "SE",
    "Sweden": "SE",
    "Danemark": "DK",
    "Denmark": "DK",
    "Finlande": "FI",
    "Finland": "FI",
    "Irlande": "IE",
    "Ireland": "IE",
    "Grèce": "GR",
    "Greece": "GR",
    "Hongrie": "HU",
    "Hungary": "HU",
    "Tchéquie": "CZ",
    "Czech Republic": "CZ",
    "Roumanie": "RO",
    "Romania": "RO",
    "Bulgarie": "BG",
    "Bulgaria": "BG",
    "Croatie": "HR",
    "Croatia": "HR",
    "Slovaquie": "SK",
    "Slovakia": "SK",
    "Slovénie": "SI",
    "Slovenia": "SI",
    "Lituanie": "LT",
    "Lithuania": "LT",
    "Lettonie": "LV",
    "Latvia": "LV",
    "Estonie": "EE",
    "Estonia": "EE",
    "Luxembourg": "LU",
    "Malte": "MT",
    "Malta": "MT",
    "Chypre": "CY",
    "Cyprus": "CY",
}


class MiraklParser(BaseParser):
    """Parser mutualisé pour les CSV Mirakl (Décathlon, Leroy Merlin)."""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def _read_and_validate(
        self, data_path: Path, config: AppConfig
    ) -> tuple[pd.DataFrame, list[Anomaly]]:
        """Lit le CSV, valide les colonnes, convertit les numériques, parse les dates."""
        channel_config = config.channels[self.channel]
        df = pd.read_csv(data_path, sep=channel_config.separator, encoding=channel_config.encoding)

        # Nettoyer les noms de colonnes (supprimer les espaces en début/fin)
        df.columns = df.columns.str.strip()

        df = self.apply_column_aliases(df, COLUMN_ALIASES)

        # Normaliser les valeurs Type via les alias (seulement si la colonne existe)
        if "Type" in df.columns:
            df["Type"] = df["Type"].map(lambda t: TYPE_ALIASES.get(str(t).strip(), str(t).strip()))

        self.validate_columns(df, REQUIRED_COLUMNS)

        anomalies: list[Anomaly] = []

        # Filtrer les lignes de taxe explicite (Leroy Merlin) — la TVA est
        # recalculée par le parser, ces lignes ne doivent pas être agrégées.
        tax_mask = df["Type"].isin(TAX_LINE_TYPES)
        if tax_mask.any():
            logger.info("Canal %s : %d lignes de taxe explicite ignorées", self.channel, int(tax_mask.sum()))
        df = df[~tax_mask].copy()

        # Convert Montant to numeric
        original_montant = df["Montant"].copy()
        df["Montant"] = pd.to_numeric(df["Montant"], errors="coerce")
        nan_mask = df["Montant"].isna() & original_montant.notna()
        for idx in df.index[nan_mask]:
            ref = str(df.at[idx, "Numéro de commande"])
            anomalies.append(Anomaly(
                type="parse_warning",
                severity="warning",
                reference=ref,
                channel=self.channel,
                detail=f"Valeur non-numérique dans la colonne Montant : {original_montant.at[idx]!r}",
                expected_value=None,
                actual_value=str(original_montant.at[idx]),
            ))
            logger.warning("Ligne ignorée (Montant non-numérique) : %s", ref)

        # Drop rows with NaN Montant
        df = df[df["Montant"].notna()].copy()

        # Parse dates — accepter à la fois %Y-%m-%d et %d/%m/%Y - %H:%M:%S
        df["Date de commande"] = pd.to_datetime(df["Date de commande"], format="mixed", dayfirst=True, errors="coerce")
        df["Date du cycle de paiement"] = pd.to_datetime(
            df["Date du cycle de paiement"], format="mixed", dayfirst=True, errors="coerce"
        )

        return df, anomalies

    def _aggregate_orders(
        self,
        df: pd.DataFrame,
        default_tva_rate: float,
        default_country_code: str,
        vat_table: dict[str, dict[str, object]],
        alpha2_to_numeric: dict[str, str],
        amounts_are_ttc: bool = False,
    ) -> tuple[list[dict[str, Any]], list[Anomaly]]:
        """Agrège les lignes commande par Numéro de commande (et ID du remboursement si présent).

        Le DataFrame reçu est pré-filtré (ORDER_LINE_TYPES uniquement).

        Args:
            df: DataFrame des lignes de commande.
            default_tva_rate: Taux TVA par défaut si pays non trouvé.
            default_country_code: Code pays par défaut si non trouvé.
            vat_table: Table TVA {country_code: {"rate": float, ...}}.
            alpha2_to_numeric: Mapping {alpha2: country_code}.
            amounts_are_ttc: Si True, les montants CSV sont TTC (extraire HT).

        Retourne des dicts intermédiaires :
        - reference, type, date, amount_ht, amount_tva, amount_ttc,
          shipping_ht, shipping_tva, commission_ht, commission_ttc,
          net_amount, country_code, tva_rate
        """
        orders: list[dict[str, Any]] = []
        anomalies: list[Anomaly] = []

        # Vérifier si la colonne Canal de diffusion existe
        has_canal_diffusion = "Canal de diffusion" in df.columns

        # Vérifier si la colonne ID du remboursement existe
        has_refund_id = "ID du remboursement" in df.columns

        # Créer la clé de regroupement : inclure ID du remboursement si présent
        # pour séparer les ventes des remboursements sur la même commande
        if has_refund_id:
            # Grouper par (Numéro de commande, ID du remboursement)
            # fillna("") pour que les ventes (sans ID remboursement) soient groupées ensemble
            group_columns = ["Numéro de commande", "ID du remboursement"]
            df_copy = df.copy()
            df_copy["ID du remboursement"] = df_copy["ID du remboursement"].fillna("").astype(str)
            grouped = df_copy.groupby(group_columns)
        else:
            grouped = df.groupby("Numéro de commande")

        for group_key, group in grouped:
            # Extraire la référence depuis la clé de regroupement
            if has_refund_id and isinstance(group_key, tuple):
                order_ref, refund_id = group_key
                order_ref_clean = str(order_ref).strip()
                # Si ID remboursement présent, ajouter un suffixe à la référence
                if refund_id and str(refund_id).strip():
                    # Nettoyer l'ID remboursement (supprimer espaces et .0 si float converti en str)
                    refund_id_clean = str(refund_id).strip()
                    if refund_id_clean.endswith(".0"):
                        refund_id_clean = refund_id_clean[:-2]
                    ref_str = f"{order_ref_clean}-R{refund_id_clean}"
                else:
                    ref_str = order_ref_clean
            else:
                ref_str = str(group_key).strip()

            montant_sum = float(group.loc[group["Type"] == "Montant", "Montant"].sum())
            frais_port_sum = float(group.loc[group["Type"] == "Frais de port", "Montant"].sum())
            commission_sum = float(group.loc[group["Type"] == "Commission", "Montant"].sum())
            taxe_commission_sum = float(
                group.loc[group["Type"] == "Taxe sur la commission", "Montant"].sum()
            )

            # Determine sale/refund
            if montant_sum > 0:
                tx_type = "sale"
            elif montant_sum < 0:
                tx_type = "refund"
            elif frais_port_sum > 0:
                tx_type = "sale"
            elif frais_port_sum < 0:
                tx_type = "refund"
            else:
                anomalies.append(Anomaly(
                    type="zero_amount_order",
                    severity="warning",
                    reference=ref_str,
                    channel=self.channel,
                    detail="Somme Montant et Frais de port = 0",
                    expected_value=None,
                    actual_value=None,
                ))
                logger.warning("Commande ignorée (montant zéro) : %s", ref_str)
                continue

            # Date
            first_date = group["Date de commande"].iloc[0]
            if pd.isna(first_date):
                anomalies.append(Anomaly(
                    type="missing_date",
                    severity="warning",
                    reference=ref_str,
                    channel=self.channel,
                    detail="Date de commande manquante ou invalide",
                    expected_value=DATE_FORMAT,
                    actual_value=None,
                ))
                logger.warning("Commande ignorée (date manquante) : %s", ref_str)
                continue

            order_date: datetime.date = first_date.date()

            # Déterminer le pays et taux TVA depuis Canal de diffusion
            tva_rate = default_tva_rate
            country_code = default_country_code
            if has_canal_diffusion:
                canal_values = group["Canal de diffusion"].dropna()
                if not canal_values.empty:
                    country_name = str(canal_values.iloc[0]).strip()
                    alpha2 = COUNTRY_NAME_TO_ALPHA2.get(country_name)
                    if alpha2 and alpha2 in alpha2_to_numeric:
                        country_code = alpha2_to_numeric[alpha2]
                        if country_code in vat_table:
                            tva_rate = float(vat_table[country_code]["rate"])

            # Calcul des montants HT/TTC selon le mode
            if amounts_are_ttc:
                # Montants CSV = TTC → extraire HT
                amount_ttc_raw = round(abs(montant_sum), 2)
                shipping_ttc_raw = round(abs(frais_port_sum), 2)

                if tva_rate > 0:
                    divisor = 1 + tva_rate / 100
                    amount_ht = round(amount_ttc_raw / divisor, 2)
                    shipping_ht = round(shipping_ttc_raw / divisor, 2)
                else:
                    # Taux 0% : HT = TTC
                    amount_ht = amount_ttc_raw
                    shipping_ht = shipping_ttc_raw

                amount_tva = round(amount_ttc_raw - amount_ht, 2)
                shipping_tva = round(shipping_ttc_raw - shipping_ht, 2)
                amount_ttc = round(amount_ttc_raw + shipping_ttc_raw, 2)
            else:
                # Montants CSV = HT → calculer TVA et TTC
                amount_ht = round(abs(montant_sum), 2)
                shipping_ht = round(abs(frais_port_sum), 2)
                amount_tva = round(amount_ht * tva_rate / 100, 2)
                shipping_tva = round(shipping_ht * tva_rate / 100, 2)
                amount_ttc = round(amount_ht + shipping_ht + amount_tva + shipping_tva, 2)

            commission_ht = round(commission_sum, 2)
            taxe_commission = round(taxe_commission_sum, 2)
            commission_ttc = round(commission_ht + taxe_commission, 2)
            signed_ttc = amount_ttc if tx_type == "sale" else -amount_ttc
            net_amount = round(signed_ttc - commission_ttc, 2)

            # Extraire la Date du cycle de paiement depuis les lignes commande
            order_payout_date: datetime.date | None = None
            order_payout_reference: str | None = None
            if "Date du cycle de paiement" in group.columns:
                payout_dates = group["Date du cycle de paiement"].dropna()
                if not payout_dates.empty:
                    order_payout_date = payout_dates.iloc[0].date()
                    order_payout_reference = order_payout_date.strftime("%Y-%m-%d")

            orders.append({
                "reference": ref_str,
                "type": tx_type,
                "date": order_date,
                "amount_ht": amount_ht,
                "amount_tva": amount_tva,
                "amount_ttc": amount_ttc,
                "shipping_ht": shipping_ht,
                "shipping_tva": shipping_tva,
                "commission_ht": commission_ht,
                "commission_ttc": commission_ttc,
                "net_amount": net_amount,
                "country_code": country_code,
                "tva_rate": tva_rate,
                "payout_date": order_payout_date,
                "payout_reference": order_payout_reference,
            })

        return orders, anomalies

    def _build_payment_lookup(
        self, df: pd.DataFrame
    ) -> tuple[dict[str, tuple[datetime.date, str]], list[Anomaly]]:
        """Construit le dict de lookup {référence: (payout_date, payout_reference)}.

        Le DataFrame reçu est pré-filtré (Type="Paiement" uniquement).
        """
        lookup: dict[str, tuple[datetime.date, str]] = {}
        anomalies: list[Anomaly] = []

        for idx, row in df.iterrows():
            date_cycle = row["Date du cycle de paiement"]
            ref = row["Numéro de commande"]

            if pd.isna(date_cycle):
                anomalies.append(Anomaly(
                    type="invalid_date",
                    severity="warning",
                    reference=str(ref) if pd.notna(ref) else "",
                    channel=self.channel,
                    detail="Date du cycle de paiement invalide ou manquante",
                    expected_value=DATE_FORMAT,
                    actual_value=None,
                ))
                logger.warning("Ligne Paiement ignorée (date cycle invalide) : index %s", idx)
                continue

            payout_date: datetime.date = date_cycle.date()
            payout_reference = payout_date.strftime("%Y-%m-%d")

            if pd.notna(ref) and str(ref).strip():
                lookup[str(ref)] = (payout_date, payout_reference)

        return lookup, anomalies

    def _aggregate_payment_summaries(self, df: pd.DataFrame) -> list[PayoutSummary]:
        """Agrège les lignes Paiement par Date du cycle de paiement."""
        summaries: list[PayoutSummary] = []

        for date_cycle, group in df.groupby("Date du cycle de paiement"):
            if pd.isna(date_cycle):
                continue

            payout_date: datetime.date = pd.Timestamp(str(date_cycle)).date()
            payout_reference = payout_date.strftime("%Y-%m-%d")
            total_amount = round(float(group["Montant"].sum()), 2)

            refs: list[str] = []
            for _, row in group.iterrows():
                ref = row["Numéro de commande"]
                if pd.notna(ref) and str(ref).strip():
                    refs.append(str(ref))

            summaries.append(PayoutSummary(
                payout_date=payout_date,
                channel=self.channel,
                total_amount=total_amount,
                charges=0.0,
                refunds=0.0,
                fees=0.0,
                transaction_references=refs,
                psp_type=None,
                payout_reference=payout_reference,
            ))

        return summaries

    def _parse_subscriptions(
        self, df: pd.DataFrame, country_code: str
    ) -> tuple[list[dict[str, Any]], list[Anomaly]]:
        """Extrait les lignes Abonnement en dicts intermédiaires."""
        subs: list[dict[str, Any]] = []
        anomalies: list[Anomaly] = []

        for idx, row in df.iterrows():
            # Date du cycle de paiement : optionnelle (absente pour les abonnements "Payable")
            date_cycle = row["Date du cycle de paiement"]
            payout_date: datetime.date | None = None
            payout_reference: str | None = None
            if not pd.isna(date_cycle):
                payout_date = date_cycle.date()
                payout_reference = payout_date.strftime("%Y-%m-%d")

            # Date d'écriture = Date de commande (alias "Date de création"), colonne 1
            date_creation = row["Date de commande"]
            if pd.isna(date_creation):
                anomalies.append(Anomaly(
                    type="invalid_date",
                    severity="warning",
                    reference=str(row["Numéro de commande"]) if pd.notna(row["Numéro de commande"]) else "",
                    channel=self.channel,
                    detail="Date de commande invalide pour abonnement",
                    expected_value=DATE_FORMAT,
                    actual_value=None,
                ))
                continue

            creation_date: datetime.date = date_creation.date()

            ref_raw = row["Numéro de commande"]
            if pd.notna(ref_raw) and str(ref_raw).strip():
                reference = str(ref_raw)
            else:
                reference = f"ABO-{self.channel}-{creation_date:%Y%m%d}"

            subs.append({
                "reference": reference,
                "special_type": "SUBSCRIPTION",
                "type": "sale",
                "date": creation_date,
                "net_amount": round(float(row["Montant"]), 2),
                "payout_date": payout_date,
                "payout_reference": payout_reference,
                "country_code": country_code,
            })

        return subs, anomalies

    def parse(self, files: dict[str, Path | list[Path]], config: AppConfig) -> ParseResult:
        """Parse les fichiers CSV Mirakl et retourne un ParseResult normalisé."""
        # 1. Read and validate
        data_path = files["data"]
        assert isinstance(data_path, Path)
        df, anomalies = self._read_and_validate(data_path, config)

        if df.empty:
            return ParseResult(transactions=[], payouts=[], anomalies=anomalies, channel=self.channel)

        # 2. Resolve country_code
        country_code = config.channels[self.channel].default_country_code
        if country_code is None:
            raise ParseError(f"default_country_code requis pour le canal {self.channel}")

        # 3. Resolve tva_rate
        tva_rate_raw: Any = config.vat_table[country_code]["rate"]
        tva_rate = float(tva_rate_raw)

        # 4. Filter unknown line types
        unknown_mask = ~df["Type"].isin(KNOWN_LINE_TYPES)
        for idx in df.index[unknown_mask]:
            ref = str(df.at[idx, "Numéro de commande"])
            line_type = str(df.at[idx, "Type"])
            anomalies.append(Anomaly(
                type="unknown_line_type",
                severity="warning",
                reference=ref,
                channel=self.channel,
                detail=f"Type de ligne inconnu : {line_type}",
                expected_value=", ".join(sorted(KNOWN_LINE_TYPES)),
                actual_value=line_type,
            ))
            logger.warning("Ligne ignorée (type inconnu) : %s - %s", ref, line_type)
        df = df[~unknown_mask].copy()

        # 5. Dispatch into sub-DataFrames
        df_orders = df[df["Type"].isin(ORDER_LINE_TYPES)]
        df_payments = df[df["Type"] == "Paiement"]
        df_subscriptions = df[df["Type"] == "Abonnement"]

        # 6. Process each sub-DataFrame
        channel_config = config.channels[self.channel]
        order_dicts, order_anomalies = self._aggregate_orders(
            df_orders,
            default_tva_rate=tva_rate,
            default_country_code=country_code,
            vat_table=config.vat_table,
            alpha2_to_numeric=config.alpha2_to_numeric,
            amounts_are_ttc=channel_config.amounts_are_ttc,
        )
        anomalies.extend(order_anomalies)

        payment_lookup, payment_anomalies = self._build_payment_lookup(df_payments)
        anomalies.extend(payment_anomalies)

        payout_summaries = self._aggregate_payment_summaries(df_payments)

        sub_dicts, sub_anomalies = self._parse_subscriptions(df_subscriptions, country_code)
        anomalies.extend(sub_anomalies)

        # 7. Enrich order dicts with payout info and build NormalizedTransaction
        order_transactions: list[NormalizedTransaction] = []
        for od in order_dicts:
            ref = str(od["reference"])
            # Prefer payout info extracted from order lines, fallback to payment_lookup
            payout_date: datetime.date | None = od.get("payout_date")
            payout_reference: str | None = od.get("payout_reference")
            if payout_date is None and ref in payment_lookup:
                payout_date, payout_reference = payment_lookup[ref]

            order_transactions.append(NormalizedTransaction(
                reference=ref,
                channel=self.channel,
                date=od["date"],
                type=str(od["type"]),
                amount_ht=float(od["amount_ht"]),
                amount_tva=float(od["amount_tva"]),
                amount_ttc=float(od["amount_ttc"]),
                shipping_ht=float(od["shipping_ht"]),
                shipping_tva=float(od["shipping_tva"]),
                tva_rate=float(od["tva_rate"]),
                country_code=str(od["country_code"]),
                commission_ttc=float(od["commission_ttc"]),
                commission_ht=float(od["commission_ht"]),
                net_amount=float(od["net_amount"]),
                payout_date=payout_date,
                payout_reference=payout_reference,
                payment_method=None,
                special_type=None,
            ))

        # 8. Build NormalizedTransaction from subscription dicts
        sub_transactions: list[NormalizedTransaction] = []
        for sd in sub_dicts:
            sub_transactions.append(NormalizedTransaction(
                reference=str(sd["reference"]),
                channel=self.channel,
                date=sd["date"],
                type="sale",
                amount_ht=0.00,
                amount_tva=0.00,
                amount_ttc=0.00,
                shipping_ht=0.00,
                shipping_tva=0.00,
                tva_rate=0.0,
                country_code=str(sd["country_code"]),
                commission_ttc=0.00,
                commission_ht=None,
                net_amount=float(sd["net_amount"]),
                payout_date=sd["payout_date"],
                payout_reference=sd["payout_reference"],
                payment_method=None,
                special_type="SUBSCRIPTION",
            ))

        # 9. Build ParseResult
        return ParseResult(
            transactions=order_transactions + sub_transactions,
            payouts=payout_summaries,
            anomalies=anomalies,
            channel=self.channel,
        )
