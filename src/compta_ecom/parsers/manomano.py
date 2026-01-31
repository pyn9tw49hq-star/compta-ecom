"""Parser pour les fichiers CSV ManoMano (CA et Versements)."""

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

CA_REQUIRED_COLUMNS = [
    "reference",
    "type",
    "createdAt",
    "amountVatIncl",
    "commissionVatIncl",
    "commissionVatExcl",
    "vatOnCommission",
    "netAmount",
    "productPriceVatExcl",
    "vatOnProduct",
    "shippingPriceVatExcl",
    "vatOnShipping",
]

PAYOUT_REQUIRED_COLUMNS = [
    "REFERENCE",
    "TYPE",
    "PAYOUT_REFERENCE",
    "PAYOUT_DATE",
    "AMOUNT",
]

DATE_FORMAT_CA = "%Y-%m-%d"
DATE_FORMAT_PAYOUT = "%Y-%m-%d"

KNOWN_PAYOUT_TYPES = {"ORDER", "REFUND", "ADJUSTMENT", "ECO_CONTRIBUTION", "SUBSCRIPTION", "REFUND_PENALTY"}
SPECIAL_TYPES = {"ADJUSTMENT", "ECO_CONTRIBUTION", "SUBSCRIPTION", "REFUND_PENALTY"}

CA_AMOUNT_COLUMNS = [
    "amountVatIncl",
    "commissionVatIncl",
    "commissionVatExcl",
    "vatOnCommission",
    "netAmount",
    "productPriceVatExcl",
    "vatOnProduct",
    "shippingPriceVatExcl",
    "vatOnShipping",
]


class ManoManoParser(BaseParser):
    """Parser pour les fichiers CSV ManoMano."""

    def _parse_ca(
        self, ca_path: Path, config: AppConfig
    ) -> tuple[list[dict[str, Any]], list[Anomaly]]:
        """Parse le fichier CA ManoMano.

        Retourne des dicts intermédiaires (pas des NormalizedTransaction) car
        les dataclasses frozen sont construites dans parse() après enrichissement
        payout (matching multi-fichiers). Clés du dict retourné :

        - reference: str
        - type: str ("sale" ou "refund")
        - date: datetime.date | None (createdAt parsé, None si vide)
        - amount_ht: float (abs(productPriceVatExcl), arrondi)
        - amount_tva: float (abs(vatOnProduct), arrondi)
        - amount_ttc: float (abs(amountVatIncl), arrondi)
        - shipping_ht: float (abs(shippingPriceVatExcl), arrondi)
        - shipping_tva: float (abs(vatOnShipping), arrondi)
        - commission_ttc: float (commissionVatIncl signé, arrondi)
        - commission_ht: float (commissionVatExcl signé, arrondi)
        - net_amount: float (netAmount signé, arrondi)
        - country_code: str
        - tva_rate: float
        """
        channel_config = config.channels["manomano"]
        df = pd.read_csv(ca_path, sep=channel_config.separator, encoding=channel_config.encoding)
        self.validate_columns(df, CA_REQUIRED_COLUMNS)

        country_code = channel_config.default_country_code
        if country_code is None:
            raise ParseError("default_country_code requis pour le canal manomano")

        tva_rate_raw: Any = config.vat_table[country_code]["rate"]
        tva_rate = float(tva_rate_raw)

        for col in CA_AMOUNT_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["createdAt"] = pd.to_datetime(df["createdAt"], format=DATE_FORMAT_CA, errors="coerce")

        rows: list[dict[str, Any]] = []
        anomalies: list[Anomaly] = []

        for idx, row in df.iterrows():
            ref = str(row["reference"])

            # Check for NaN in amount columns
            has_nan = False
            for col in CA_AMOUNT_COLUMNS:
                if pd.isna(row[col]):
                    anomalies.append(Anomaly(
                        type="parse_warning",
                        severity="warning",
                        reference=ref,
                        channel="manomano",
                        detail=f"Valeur non-numérique dans la colonne {col}",
                        expected_value=None,
                        actual_value=None,
                    ))
                    has_nan = True
                    break
            if has_nan:
                logger.warning("Ligne ignorée (valeur non-numérique) : %s", ref)
                continue

            raw_type = str(row["type"])
            if raw_type == "ORDER":
                tx_type = "sale"
            elif raw_type == "REFUND":
                tx_type = "refund"
            else:
                anomalies.append(Anomaly(
                    type="unknown_transaction_type",
                    severity="warning",
                    reference=ref,
                    channel="manomano",
                    detail=f"Type de transaction inconnu : {raw_type}",
                    expected_value="ORDER ou REFUND",
                    actual_value=raw_type,
                ))
                logger.warning("Ligne ignorée (type inconnu) : %s - %s", ref, raw_type)
                continue

            date_val = row["createdAt"]
            parsed_date: datetime.date | None = None
            if pd.notna(date_val):
                parsed_date = date_val.date()

            rows.append({
                "reference": ref,
                "type": tx_type,
                "date": parsed_date,
                "amount_ht": round(abs(float(row["productPriceVatExcl"])), 2),
                "amount_tva": round(abs(float(row["vatOnProduct"])), 2),
                "amount_ttc": round(abs(float(row["amountVatIncl"])), 2),
                "shipping_ht": round(abs(float(row["shippingPriceVatExcl"])), 2),
                "shipping_tva": round(abs(float(row["vatOnShipping"])), 2),
                "commission_ttc": round(float(row["commissionVatIncl"]), 2),
                "commission_ht": round(float(row["commissionVatExcl"]), 2),
                "net_amount": round(float(row["netAmount"]), 2),
                "country_code": country_code,
                "tva_rate": tva_rate,
            })

        return rows, anomalies

    def _parse_payout_lines(
        self, df: pd.DataFrame, config: AppConfig
    ) -> tuple[list[dict[str, Any]], dict[str, tuple[datetime.date, str]], list[Anomaly]]:
        """Parse les lignes du fichier Versements.

        Retourne :
        - special_rows_data : dicts pour les lignes spéciales
        - lookup_dict : {reference: (payout_date, payout_reference)} pour le matching
        - anomalies : anomalies collectées
        """
        self.validate_columns(df, PAYOUT_REQUIRED_COLUMNS)

        channel_config = config.channels["manomano"]
        country_code = channel_config.default_country_code
        if country_code is None:
            raise ParseError("default_country_code requis pour le canal manomano")

        df["AMOUNT"] = pd.to_numeric(df["AMOUNT"], errors="coerce")
        df["PAYOUT_DATE"] = pd.to_datetime(df["PAYOUT_DATE"], format=DATE_FORMAT_PAYOUT, errors="coerce")

        special_rows: list[dict[str, Any]] = []
        lookup_dict: dict[str, tuple[datetime.date, str]] = {}
        anomalies: list[Anomaly] = []

        for idx, row in df.iterrows():
            ref = str(row["REFERENCE"])
            raw_type = str(row["TYPE"])
            payout_ref = str(row["PAYOUT_REFERENCE"])

            if raw_type not in KNOWN_PAYOUT_TYPES:
                anomalies.append(Anomaly(
                    type="unknown_payout_type",
                    severity="warning",
                    reference=ref,
                    channel="manomano",
                    detail=f"Type de payout inconnu : {raw_type}",
                    expected_value=", ".join(sorted(KNOWN_PAYOUT_TYPES)),
                    actual_value=raw_type,
                ))
                logger.warning("Ligne Versement ignorée (type inconnu) : %s - %s", ref, raw_type)
                continue

            payout_date_val = row["PAYOUT_DATE"]
            if pd.isna(payout_date_val):
                anomalies.append(Anomaly(
                    type="invalid_date",
                    severity="warning",
                    reference=ref,
                    channel="manomano",
                    detail="PAYOUT_DATE invalide ou manquante",
                    expected_value=DATE_FORMAT_PAYOUT,
                    actual_value=None,
                ))
                logger.warning("Ligne Versement ignorée (date invalide) : %s", ref)
                continue

            payout_date: datetime.date = payout_date_val.date()

            if pd.isna(row["AMOUNT"]):
                anomalies.append(Anomaly(
                    type="parse_warning",
                    severity="warning",
                    reference=ref,
                    channel="manomano",
                    detail="Valeur non-numérique dans la colonne AMOUNT",
                    expected_value=None,
                    actual_value=None,
                ))
                logger.warning("Ligne Versement ignorée (AMOUNT non-numérique) : %s", ref)
                continue

            if raw_type in SPECIAL_TYPES:
                special_rows.append({
                    "reference": ref,
                    "special_type": raw_type,
                    "type": "sale",
                    "date": payout_date,
                    "net_amount": round(float(row["AMOUNT"]), 2),
                    "payout_date": payout_date,
                    "payout_reference": payout_ref,
                    "country_code": country_code,
                })
            else:
                # ORDER or REFUND
                lookup_dict[ref] = (payout_date, payout_ref)

        return special_rows, lookup_dict, anomalies

    def _aggregate_payout_summaries(
        self, df: pd.DataFrame
    ) -> tuple[list[PayoutSummary], list[Anomaly]]:
        """Agrège les lignes Versements par PAYOUT_REFERENCE en PayoutSummary."""
        df["AMOUNT"] = pd.to_numeric(df["AMOUNT"], errors="coerce")
        df["PAYOUT_DATE"] = pd.to_datetime(df["PAYOUT_DATE"], format=DATE_FORMAT_PAYOUT, errors="coerce")

        summaries: list[PayoutSummary] = []
        anomalies: list[Anomaly] = []

        for payout_ref, group in df.groupby("PAYOUT_REFERENCE"):
            payout_ref_str = str(payout_ref)
            first_date = group["PAYOUT_DATE"].iloc[0]

            if pd.isna(first_date):
                anomalies.append(Anomaly(
                    type="invalid_date",
                    severity="warning",
                    reference=payout_ref_str,
                    channel="manomano",
                    detail="PAYOUT_DATE invalide pour le payout",
                    expected_value=DATE_FORMAT_PAYOUT,
                    actual_value=None,
                ))
                logger.warning("Payout ignoré (date invalide) : %s", payout_ref_str)
                continue

            payout_date: datetime.date = first_date.date()

            total_amount = round(float(group["AMOUNT"].sum()), 2)

            order_refund_mask = group["TYPE"].isin({"ORDER", "REFUND"})
            transaction_references = group.loc[order_refund_mask, "REFERENCE"].astype(str).tolist()

            summaries.append(PayoutSummary(
                payout_date=payout_date,
                channel="manomano",
                total_amount=total_amount,
                charges=0.0,
                refunds=0.0,
                fees=0.0,
                transaction_references=transaction_references,
                psp_type=None,
                payout_reference=payout_ref_str,
            ))

        return summaries, anomalies

    def parse(self, files: dict[str, Path], config: AppConfig) -> ParseResult:
        """Parse les fichiers CSV ManoMano et retourne un ParseResult normalisé."""
        ca_path = files["ca"]
        payouts_path = files["payouts"]

        channel_config = config.channels["manomano"]

        # Parse CA
        ca_rows, ca_anomalies = self._parse_ca(ca_path, config)

        # Parse Versements
        payout_df = pd.read_csv(payouts_path, sep=channel_config.separator, encoding=channel_config.encoding)
        self.validate_columns(payout_df, PAYOUT_REQUIRED_COLUMNS)

        special_rows, lookup_dict, payout_anomalies = self._parse_payout_lines(payout_df, config)
        payout_summaries, summary_anomalies = self._aggregate_payout_summaries(payout_df)

        all_anomalies = ca_anomalies + payout_anomalies + summary_anomalies

        # Build NormalizedTransaction from CA rows with payout enrichment
        ca_transactions: list[NormalizedTransaction] = []
        matched_refs: set[str] = set()

        for row in ca_rows:
            ref = str(row["reference"])
            payout_date: datetime.date | None = None
            payout_reference: str | None = None

            if ref in lookup_dict:
                payout_date, payout_reference = lookup_dict[ref]
                matched_refs.add(ref)

            # Fallback date
            tx_date = row["date"]
            if tx_date is None:
                if payout_date is not None:
                    tx_date = payout_date
                else:
                    all_anomalies.append(Anomaly(
                        type="missing_date",
                        severity="warning",
                        reference=ref,
                        channel="manomano",
                        detail="Date absente dans CA et pas de correspondance Versement",
                        expected_value=None,
                        actual_value=None,
                    ))
                    logger.warning("Transaction ignorée (date absente) : %s", ref)
                    continue

            ca_transactions.append(NormalizedTransaction(
                reference=ref,
                channel="manomano",
                date=tx_date,
                type=str(row["type"]),
                amount_ht=float(row["amount_ht"]),
                amount_tva=float(row["amount_tva"]),
                amount_ttc=float(row["amount_ttc"]),
                shipping_ht=float(row["shipping_ht"]),
                shipping_tva=float(row["shipping_tva"]),
                tva_rate=float(row["tva_rate"]),
                country_code=str(row["country_code"]),
                commission_ttc=float(row["commission_ttc"]),
                commission_ht=float(row["commission_ht"]),
                net_amount=float(row["net_amount"]),
                payout_date=payout_date,
                payout_reference=payout_reference,
                payment_method=None,
                special_type=None,
            ))

        # Log unmatched payout ORDER/REFUND references
        for ref in lookup_dict:
            if ref not in matched_refs:
                logger.debug("Référence Versement ORDER/REFUND sans correspondance CA : %s", ref)

        # Build NormalizedTransaction from special payout lines
        special_transactions: list[NormalizedTransaction] = []
        for row in special_rows:
            special_transactions.append(NormalizedTransaction(
                reference=str(row["reference"]),
                channel="manomano",
                date=row["date"],
                type="sale",
                amount_ht=0.00,
                amount_tva=0.00,
                amount_ttc=0.00,
                shipping_ht=0.00,
                shipping_tva=0.00,
                tva_rate=0.0,
                country_code=str(row["country_code"]),
                commission_ttc=0.00,
                commission_ht=None,
                net_amount=float(row["net_amount"]),
                payout_date=row["payout_date"],
                payout_reference=str(row["payout_reference"]),
                payment_method=None,
                special_type=str(row["special_type"]),
            ))

        # Dicts intermédiaires : les NormalizedTransaction frozen sont construites dans parse() après enrichissement payout (matching multi-fichiers)

        return ParseResult(
            transactions=ca_transactions + special_transactions,
            payouts=payout_summaries,
            anomalies=all_anomalies,
            channel="manomano",
        )
