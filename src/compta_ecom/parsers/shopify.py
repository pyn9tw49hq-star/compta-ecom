"""Parser pour les fichiers CSV Shopify (Ventes, Transactions, Versements PSP)."""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import Anomaly, NormalizedTransaction, ParseResult, PayoutSummary
from compta_ecom.parsers.base import BaseParser

logger = logging.getLogger(__name__)

REQUIRED_SALES_COLUMNS = [
    "Name",
    "Created at",
    "Subtotal",
    "Shipping",
    "Taxes",
    "Total",
    "Tax 1 Name",
    "Tax 1 Value",
    "Payment Method",
    "Shipping Country",
]

REQUIRED_TRANSACTIONS_COLUMNS = [
    "Order",
    "Type",
    "Payment Method Name",
    "Amount",
    "Fee",
    "Net",
    "Payout Date",
    "Payout ID",
]

REQUIRED_PAYOUTS_COLUMNS = [
    "Payout Date",
    "Charges",
    "Refunds",
    "Fees",
    "Total",
]


def _is_notna(value: object) -> bool:
    """Vérifie qu'une valeur scalaire n'est pas NaN/None (compatible mypy --strict)."""
    return bool(pd.notna(pd.Series([value])).iloc[0])


def _extract_vat_rate(tax_name: object) -> float:
    """Extraire le taux TVA depuis Tax 1 Name. Ex: 'FR TVA 20%' -> 20.0."""
    if not tax_name or not isinstance(tax_name, str):
        return 0.0
    match = re.search(r"(\d+(?:\.\d+)?)%", tax_name)
    return float(match.group(1)) if match else 0.0


class ShopifyParser(BaseParser):
    """Parser Shopify — 3 fichiers CSV (Ventes, Transactions, Versements PSP)."""

    def parse(self, files: dict[str, Path], config: AppConfig) -> ParseResult:
        """Orchestre le parsing des 3 fichiers et le matching."""
        anomalies: list[Anomaly] = []

        # 1. Ventes (obligatoire)
        sales_data, sales_anomalies = self._parse_sales(files["sales"], config)
        anomalies.extend(sales_anomalies)

        # 2. Transactions (optionnel — mode dégradé si absent)
        if "transactions" in files:
            tx_data, tx_anomalies = self._parse_transactions(files["transactions"], config)
            anomalies.extend(tx_anomalies)
        else:
            logger.warning("Fichier Transactions absent — mode dégradé")
            tx_data = {}

        # 3. Matching + construction NormalizedTransaction
        transactions, match_anomalies = self._match_and_build(sales_data, tx_data, config)
        anomalies.extend(match_anomalies)

        # 4. Versements PSP (optionnel)
        if "payouts" in files:
            payouts = self._parse_payouts(files["payouts"], tx_data, config)
        else:
            logger.warning("Fichier Versements absent — pas de PayoutSummary")
            payouts = []

        logger.info(
            "Shopify : %d transactions parsées, %d anomalies",
            len(transactions),
            len(anomalies),
        )

        return ParseResult(
            transactions=transactions,
            payouts=payouts,
            anomalies=anomalies,
            channel="shopify",
        )

    def _parse_sales(
        self, sales_path: Path, config: AppConfig
    ) -> tuple[dict[str, dict[str, Any]], list[Anomaly]]:
        """Lecture et agrégation du fichier Ventes (logique Story 1.2)."""
        channel_config = config.channels["shopify"]

        df = pd.read_csv(
            sales_path,
            sep=channel_config.separator,
            encoding=channel_config.encoding,
        )
        self.validate_columns(df, REQUIRED_SALES_COLUMNS)

        anomalies: list[Anomaly] = []
        sales_data: dict[str, dict[str, Any]] = {}

        aggregated, agg_anomalies = self._aggregate(df)
        anomalies.extend(agg_anomalies)

        for _, row in aggregated.iterrows():
            sale, row_anomalies = self._extract_sale_data(row, config)
            anomalies.extend(row_anomalies)
            if sale is not None:
                sales_data[str(sale["reference"])] = sale

        return sales_data, anomalies

    def _aggregate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[Anomaly]]:
        """Agrège les commandes multi-lignes par Name."""
        anomalies: list[Anomaly] = []

        sum_cols = ["Subtotal", "Shipping", "Taxes", "Total"]
        first_cols = ["Created at", "Shipping Country", "Tax 1 Name", "Payment Method"]

        grouped = df.groupby("Name", sort=False)

        # Détection pays divergent
        country_counts = grouped["Shipping Country"].nunique()
        divergent = country_counts[country_counts > 1].index
        for name in divergent:
            anomalies.append(
                Anomaly(
                    type="parse_warning",
                    severity="warning",
                    reference=str(name),
                    channel="shopify",
                    detail="Pays de livraison divergent entre les lignes de la commande",
                    expected_value=None,
                    actual_value=None,
                )
            )

        sums = grouped[sum_cols].sum()
        first = grouped[first_cols].first()
        aggregated = pd.concat([first, sums], axis=1).reset_index()

        return aggregated, anomalies

    def _extract_sale_data(
        self, row: Any, config: AppConfig
    ) -> tuple[dict[str, Any] | None, list[Anomaly]]:
        """Extrait les données de vente d'une ligne agrégée en dict."""
        anomalies: list[Anomaly] = []
        reference = str(row["Name"])

        try:
            subtotal = float(row["Subtotal"])
            shipping = float(row["Shipping"])
            taxes = float(row["Taxes"])
            total = float(row["Total"])
        except (ValueError, TypeError):
            anomalies.append(
                Anomaly(
                    type="parse_warning",
                    severity="warning",
                    reference=reference,
                    channel="shopify",
                    detail="Valeur numérique non parsable — ligne ignorée",
                    expected_value=None,
                    actual_value=None,
                )
            )
            return None, anomalies

        # Conversion pays
        country_raw: object = row["Shipping Country"]
        alpha2_code = str(country_raw) if _is_notna(country_raw) else ""
        numeric_code = config.alpha2_to_numeric.get(alpha2_code)
        if numeric_code is None:
            anomalies.append(
                Anomaly(
                    type="unknown_country",
                    severity="warning",
                    reference=reference,
                    channel="shopify",
                    detail=f"Code alpha-2 inconnu : {alpha2_code}",
                    expected_value=None,
                    actual_value=alpha2_code,
                )
            )
            country_code = "000"
        else:
            country_code = numeric_code

        # Extraction taux TVA
        tax_raw: object = row["Tax 1 Name"]
        tax_name = tax_raw if _is_notna(tax_raw) else None
        tva_rate = _extract_vat_rate(tax_name)

        # Ventilation frais de port
        shipping_ht = round(shipping, 2)
        shipping_tva = round(shipping_ht * tva_rate / 100, 2)

        # Montants
        amount_ht = round(subtotal, 2)
        amount_tva = round(taxes - shipping_tva, 2)
        if amount_tva < 0:
            anomalies.append(
                Anomaly(
                    type="parse_warning",
                    severity="warning",
                    reference=reference,
                    channel="shopify",
                    detail="TVA produit négative après ventilation port",
                    expected_value=None,
                    actual_value=str(amount_tva),
                )
            )
            amount_tva = 0.0
        amount_ttc = round(total, 2)

        # Date
        date_str = str(row["Created at"])
        try:
            date = pd.to_datetime(date_str).date()
        except (ValueError, TypeError):
            anomalies.append(
                Anomaly(
                    type="parse_warning",
                    severity="warning",
                    reference=reference,
                    channel="shopify",
                    detail=f"Date non parsable : {date_str}",
                    expected_value=None,
                    actual_value=date_str,
                )
            )
            return None, anomalies

        sale: dict[str, Any] = {
            "reference": reference,
            "date": date,
            "amount_ht": amount_ht,
            "amount_tva": amount_tva,
            "amount_ttc": amount_ttc,
            "shipping_ht": shipping_ht,
            "shipping_tva": shipping_tva,
            "tva_rate": tva_rate,
            "country_code": country_code,
        }

        return sale, anomalies

    def _parse_transactions(
        self, transactions_path: Path, config: AppConfig
    ) -> tuple[dict[str, list[dict[str, Any]]], list[Anomaly]]:
        """Lecture du fichier Transactions, groupement par Order."""
        channel_config = config.channels["shopify"]
        psp_mapping: dict[str, str] = {}
        for psp_name in config.psp:
            psp_mapping[psp_name] = psp_name

        df = pd.read_csv(
            transactions_path,
            sep=channel_config.separator,
            encoding=channel_config.encoding,
        )
        self.validate_columns(df, REQUIRED_TRANSACTIONS_COLUMNS)

        anomalies: list[Anomaly] = []
        tx_data: dict[str, list[dict[str, Any]]] = {}

        for _, row in df.iterrows():
            order = str(row["Order"])
            tx_type_raw = str(row["Type"]).strip().lower()
            payment_method_raw = str(row["Payment Method Name"]).strip().lower()

            # Validate type
            if tx_type_raw not in ("charge", "refund"):
                anomalies.append(
                    Anomaly(
                        type="parse_warning",
                        severity="warning",
                        reference=order,
                        channel="shopify",
                        detail=f"Type de transaction inconnu : {tx_type_raw}",
                        expected_value="charge ou refund",
                        actual_value=tx_type_raw,
                    )
                )
                continue

            # Map PSP
            payment_method: str | None = psp_mapping.get(payment_method_raw)
            if payment_method is None:
                anomalies.append(
                    Anomaly(
                        type="unknown_psp",
                        severity="warning",
                        reference=order,
                        channel="shopify",
                        detail=f"PSP inconnu : {payment_method_raw}",
                        expected_value=None,
                        actual_value=payment_method_raw,
                    )
                )

            # Parse payout date
            payout_date_raw = row["Payout Date"]
            payout_date: datetime.date | None = None
            if _is_notna(payout_date_raw):
                try:
                    payout_date = pd.to_datetime(str(payout_date_raw)).date()
                except (ValueError, TypeError):
                    pass

            payout_id_raw = row["Payout ID"]
            payout_reference: str | None = str(payout_id_raw) if _is_notna(payout_id_raw) else None

            tx_entry: dict[str, Any] = {
                "order": order,
                "type": tx_type_raw,
                "payment_method": payment_method,
                "amount": round(float(row["Amount"]), 2),
                "fee": round(float(row["Fee"]), 2),
                "net": round(float(row["Net"]), 2),
                "payout_date": payout_date,
                "payout_reference": payout_reference,
            }

            if order not in tx_data:
                tx_data[order] = []
            tx_data[order].append(tx_entry)

        return tx_data, anomalies

    def _match_and_build(
        self,
        sales: dict[str, dict[str, Any]],
        transactions: dict[str, list[dict[str, Any]]],
        config: AppConfig,
    ) -> tuple[list[NormalizedTransaction], list[Anomaly]]:
        """Matching vente↔transaction et construction des NormalizedTransaction finales."""
        anomalies: list[Anomaly] = []
        result: list[NormalizedTransaction] = []

        for ref, sale in sales.items():
            txs = transactions.get(ref, [])
            charges = [tx for tx in txs if tx["type"] == "charge"]
            refunds = [tx for tx in txs if tx["type"] == "refund"]

            if charges:
                charge = charges[0]
                tx = NormalizedTransaction(
                    reference=sale["reference"],
                    channel="shopify",
                    date=sale["date"],
                    type="sale",
                    amount_ht=sale["amount_ht"],
                    amount_tva=sale["amount_tva"],
                    amount_ttc=sale["amount_ttc"],
                    shipping_ht=sale["shipping_ht"],
                    shipping_tva=sale["shipping_tva"],
                    tva_rate=sale["tva_rate"],
                    country_code=sale["country_code"],
                    commission_ttc=charge["fee"],
                    commission_ht=0.0,
                    net_amount=charge["net"],
                    payout_date=charge.get("payout_date"),
                    payout_reference=charge.get("payout_reference"),
                    payment_method=charge.get("payment_method"),
                    special_type=None,
                )
                result.append(tx)
            else:
                # Orphan sale or degraded mode (no transactions file)
                if transactions:
                    anomalies.append(
                        Anomaly(
                            type="orphan_sale",
                            severity="warning",
                            reference=ref,
                            channel="shopify",
                            detail="Vente sans transaction charge correspondante",
                            expected_value=None,
                            actual_value=None,
                        )
                    )
                tx = NormalizedTransaction(
                    reference=sale["reference"],
                    channel="shopify",
                    date=sale["date"],
                    type="sale",
                    amount_ht=sale["amount_ht"],
                    amount_tva=sale["amount_tva"],
                    amount_ttc=sale["amount_ttc"],
                    shipping_ht=sale["shipping_ht"],
                    shipping_tva=sale["shipping_tva"],
                    tva_rate=sale["tva_rate"],
                    country_code=sale["country_code"],
                    commission_ttc=0.0,
                    commission_ht=0.0,
                    net_amount=sale["amount_ttc"],
                    payout_date=None,
                    payout_reference=None,
                    payment_method=None,
                    special_type=None,
                )
                result.append(tx)

            # Refunds
            for refund_tx in refunds:
                amount_ttc = round(abs(float(refund_tx["amount"])), 2)
                amount_ht = round(amount_ttc / (1 + sale["tva_rate"] / 100), 2)
                amount_tva = round(amount_ttc - amount_ht, 2)
                tx = NormalizedTransaction(
                    reference=sale["reference"],
                    channel="shopify",
                    date=sale["date"],
                    type="refund",
                    amount_ht=amount_ht,
                    amount_tva=amount_tva,
                    amount_ttc=amount_ttc,
                    shipping_ht=0.0,
                    shipping_tva=0.0,
                    tva_rate=sale["tva_rate"],
                    country_code=sale["country_code"],
                    commission_ttc=refund_tx["fee"],
                    commission_ht=0.0,
                    net_amount=refund_tx["net"],
                    payout_date=refund_tx.get("payout_date"),
                    payout_reference=refund_tx.get("payout_reference"),
                    payment_method=refund_tx.get("payment_method"),
                    special_type=None,
                )
                result.append(tx)

        # Orphan settlements (transactions without matching sale)
        for ref in transactions:
            if ref not in sales:
                anomalies.append(
                    Anomaly(
                        type="orphan_settlement",
                        severity="warning",
                        reference=ref,
                        channel="shopify",
                        detail="Transaction sans vente correspondante",
                        expected_value=None,
                        actual_value=None,
                    )
                )

        return result, anomalies

    def _parse_payouts(
        self,
        payouts_path: Path,
        transactions: dict[str, list[dict[str, Any]]],
        config: AppConfig,
    ) -> list[PayoutSummary]:
        """Lecture du fichier Versements PSP, construction des PayoutSummary."""
        channel_config = config.channels["shopify"]

        df = pd.read_csv(
            payouts_path,
            sep=channel_config.separator,
            encoding=channel_config.encoding,
        )
        self.validate_columns(df, REQUIRED_PAYOUTS_COLUMNS)

        # Group all transactions by Payout ID
        tx_by_payout: dict[str, list[dict[str, Any]]] = {}
        for tx_list in transactions.values():
            for tx in tx_list:
                payout_ref = tx.get("payout_reference")
                if payout_ref is not None:
                    if payout_ref not in tx_by_payout:
                        tx_by_payout[payout_ref] = []
                    tx_by_payout[payout_ref].append(tx)

        payouts: list[PayoutSummary] = []

        for _, row in df.iterrows():
            payout_date_raw = row["Payout Date"]
            payout_date: datetime.date | None = None
            if _is_notna(payout_date_raw):
                try:
                    payout_date = pd.to_datetime(str(payout_date_raw)).date()
                except (ValueError, TypeError):
                    pass

            charges_total = round(float(row["Charges"]), 2)
            refunds_total = round(float(row["Refunds"]), 2)
            fees_total = round(float(row["Fees"]), 2)
            total_amount = round(float(row["Total"]), 2)

            # Find matching payout_id — use transactions grouped by Payout ID
            # Find payout IDs whose transactions have matching payout_date
            matched_payout_ids: list[str] = []
            for pid, txs in tx_by_payout.items():
                if txs and txs[0].get("payout_date") == payout_date:
                    matched_payout_ids.append(pid)

            tx_refs: list[str] = []
            payout_reference: str | None = None
            psp_types: set[str | None] = set()

            for pid in matched_payout_ids:
                payout_reference = pid
                for tx in tx_by_payout[pid]:
                    tx_refs.append(str(tx["order"]))
                    psp_types.add(tx.get("payment_method"))

            psp_type: str | None = None
            if len(psp_types) == 1:
                psp_type = psp_types.pop()

            if payout_date is None:
                continue

            payouts.append(
                PayoutSummary(
                    payout_date=payout_date,
                    channel="shopify",
                    total_amount=total_amount,
                    charges=charges_total,
                    refunds=refunds_total,
                    fees=fees_total,
                    transaction_references=tx_refs,
                    psp_type=psp_type,
                    payout_reference=payout_reference,
                )
            )

        return payouts
