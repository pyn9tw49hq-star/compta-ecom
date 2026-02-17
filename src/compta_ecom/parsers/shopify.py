"""Parser pour les fichiers CSV Shopify (Ventes, Transactions, Versements PSP)."""

from __future__ import annotations

import dataclasses
import datetime
import logging
import re
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import Anomaly, NormalizedTransaction, ParseError, ParseResult, PayoutDetail, PayoutSummary
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

REQUIRED_PAYOUT_DETAIL_COLUMNS = [
    "Transaction Date",
    "Type",
    "Order",
    "Amount",
    "Fee",
    "Net",
    "Payout Date",
    "Payout ID",
    "Payment Method Name",
]

REQUIRED_RETURNS_COLUMNS = [
    "Jour",
    "Nom de la commande",
    "Retours nets",
    "Expédition retournée",
    "Taxes retournées",
    "Frais de retour",
    "Total des retours",
]


def _is_notna(value: object) -> bool:
    """Vérifie qu'une valeur scalaire n'est pas NaN/None (compatible mypy --strict)."""
    return bool(pd.notna(pd.Series([value])).iloc[0])


def _normalize_payout_id(raw: object) -> str:
    """Normalise un Payout ID: supprime le suffixe .0 ajouté par pandas sur les colonnes float."""
    s = str(raw)
    if s.endswith(".0"):
        try:
            return str(int(float(s)))
        except (ValueError, OverflowError):
            pass
    return s


def _extract_ref_number(ref: str) -> int | None:
    """Extrait la partie numérique d'une référence Shopify (ex: '#1118' → 1118)."""
    m = re.search(r"(\d+)", ref)
    return int(m.group(1)) if m else None


def _extract_vat_rate(tax_name: object) -> float:
    """Extraire le taux TVA depuis Tax 1 Name. Ex: 'FR TVA 20%' -> 20.0.

    Gère la notation décimale française (virgule) : 'FR TVA 18,826%' -> 18.826.
    Rejette les taux aberrants (> 100%).
    """
    if not tax_name or not isinstance(tax_name, str):
        return 0.0
    match = re.search(r"(\d+(?:[.,]\d+)?)%", tax_name)
    if not match:
        return 0.0
    rate_str = match.group(1).replace(",", ".")
    rate = float(rate_str)
    if rate > 100.0:
        return 0.0
    return rate


class ShopifyParser(BaseParser):
    """Parser Shopify — 3 fichiers CSV (Ventes, Transactions, Versements PSP)."""

    def parse(self, files: dict[str, Path | BytesIO | list[Path | BytesIO]], config: AppConfig) -> ParseResult:
        """Orchestre le parsing des fichiers et le matching."""
        if "sales" not in files and "returns" not in files:
            raise ParseError(
                "Shopify nécessite au moins le fichier Ventes ou le fichier Retours"
            )

        anomalies: list[Anomaly] = []

        # 1. Ventes (conditionnel — absent en mode avoirs seul)
        if "sales" in files:
            sales_data, sales_anomalies = self._parse_sales(files["sales"], config)  # type: ignore[arg-type]
            anomalies.extend(sales_anomalies)
        else:
            sales_data = {}

        # 2. Transactions (optionnel — mode dégradé si absent)
        if "transactions" in files:
            tx_data, tx_anomalies = self._parse_transactions(files["transactions"], config)  # type: ignore[arg-type]
            anomalies.extend(tx_anomalies)
        else:
            logger.warning("Fichier Transactions absent — mode dégradé")
            tx_data = {}

        # 3. Matching + construction NormalizedTransaction
        if sales_data:
            transactions, match_anomalies = self._match_and_build(sales_data, tx_data, config)
            anomalies.extend(match_anomalies)
        else:
            transactions = []

        # 3.4 Fichier retours (optionnel) — écritures d'avoir
        if "returns" in files:
            returns_txs, returns_anomalies = self._parse_returns(
                files["returns"], sales_data, config  # type: ignore[arg-type]
            )
            anomalies.extend(returns_anomalies)

            # Retaguer les refunds existants couverts par le fichier retours
            returns_refs = {t.reference for t in returns_txs}
            retagged: list[NormalizedTransaction] = []
            for tx in transactions:
                if tx.type == "refund" and tx.special_type is None and tx.reference in returns_refs:
                    retagged.append(dataclasses.replace(tx, special_type="refund_settlement"))
                else:
                    retagged.append(tx)
            transactions = retagged
            transactions.extend(returns_txs)

        # 3.5 Detail transactions par versements (optionnel)
        payout_details_by_id: dict[str, list[PayoutDetail]] | None = None
        if "payout_details" in files:
            detail_files = files["payout_details"]  # list[Path]
            payout_details_by_id, detail_anomalies = self._parse_payout_details(
                detail_files, config  # type: ignore[arg-type]
            )
            anomalies.extend(detail_anomalies)

            # 3.6 Refunds découverts dans payout details mais absents de Transactions Shopify
            detail_refunds, detail_refund_anomalies = self._build_refunds_from_payout_details(
                payout_details_by_id, transactions, sales_data
            )
            transactions.extend(detail_refunds)
            anomalies.extend(detail_refund_anomalies)

        # 4. Versements PSP (optionnel)
        if "payouts" in files:
            payouts, payout_anomalies = self._parse_payouts(
                files["payouts"], tx_data, config, payout_details_by_id  # type: ignore[arg-type]
            )
            anomalies.extend(payout_anomalies)
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

        # Détection format "CSV pour Excel/Numbers" : chaque ligne de données
        # est enveloppée dans une seule paire de guillemets doubles.
        # Symptôme : "Created at" entièrement NaN et "Name" contient des virgules.
        if (
            "Created at" in df.columns
            and "Name" in df.columns
            and df["Created at"].isna().all()
            and df["Name"].astype(str).str.contains(",").any()
        ):
            logger.info("Format CSV Excel/Numbers détecté pour le fichier Ventes — re-parsing automatique")
            df = self._reparse_excel_csv(sales_path, channel_config)
            if df["Created at"].isna().all():
                logger.warning("Re-parse Excel CSV : la colonne 'Created at' est toujours vide après correction — vérifier le format du fichier source")

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

    @staticmethod
    def _reparse_excel_csv(
        source: Path | BytesIO, channel_config: object
    ) -> pd.DataFrame:
        """Re-parse un CSV au format Excel/Numbers (lignes data enveloppées de guillemets)."""
        if isinstance(source, BytesIO):
            source.seek(0)
            raw_lines = source.read().decode(
                getattr(channel_config, "encoding", "utf-8")
            ).splitlines(keepends=True)
        else:
            with open(source, encoding=getattr(channel_config, "encoding", "utf-8")) as f:
                raw_lines = f.readlines()

        cleaned: list[str] = []
        for i, line in enumerate(raw_lines):
            if i == 0:
                cleaned.append(line)
                continue
            stripped = line.strip()
            if stripped.startswith('"') and stripped.endswith('"'):
                inner = stripped[1:-1]
                inner = inner.replace('""', '"')
                cleaned.append(inner + "\n")
            else:
                cleaned.append(line)

        return pd.read_csv(
            StringIO("".join(cleaned)),
            sep=getattr(channel_config, "separator", ","),
            encoding=getattr(channel_config, "encoding", "utf-8"),
        )

    def _aggregate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[Anomaly]]:
        """Agrège les commandes multi-lignes par Name."""
        anomalies: list[Anomaly] = []

        sum_cols = ["Subtotal", "Shipping", "Taxes", "Total"]
        extra_tax_cols = [f"Tax {i} Name" for i in range(2, 6) if f"Tax {i} Name" in df.columns]
        first_cols = ["Created at", "Shipping Country", "Tax 1 Name", "Payment Method"] + extra_tax_cols

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

    @staticmethod
    def _find_tva_rate_for_country(row: Any, alpha2_code: str) -> float:
        """Trouve le taux TVA correspondant au pays de livraison parmi Tax 1-5 Name.

        Convention Shopify : les noms de taxe commencent par le code alpha-2 pays,
        ex: "FR TVA 20%", "IT IVA 22%", "ES IVA 21%".
        """
        fallback_rate = 0.0
        for i in range(1, 6):
            col = f"Tax {i} Name"
            if col not in row.index:
                break
            raw = row[col]
            if not _is_notna(raw):
                continue
            name = str(raw).strip()
            rate = _extract_vat_rate(name)
            if i == 1:
                fallback_rate = rate
            if len(name) >= 2 and name[:2].upper() == alpha2_code.upper() and rate > 0:
                return rate
        return fallback_rate

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

        # Extraction taux TVA — scan Tax 1-5 Name, priorité au pays de livraison
        tva_rate = self._find_tva_rate_for_country(row, alpha2_code)

        # Montants — dérivés depuis Total et Taxes pour garantir HT + TVA = TTC.
        # Shopify peut exporter en prix TTC (Total = Subtotal + Shipping, taxes
        # incluses) ou HT (Total = Subtotal + Shipping + Taxes).  En dérivant
        # le HT total depuis Total − Taxes, les deux cas sont couverts.
        amount_ttc = round(total, 2)
        total_tva = round(taxes, 2)
        total_ht = round(amount_ttc - total_tva, 2)

        # Ventilation produit / frais de port (proportionnelle)
        raw_sum = subtotal + shipping
        if raw_sum > 0 and shipping > 0:
            shipping_ratio = shipping / raw_sum
            shipping_ht = round(total_ht * shipping_ratio, 2)
            shipping_tva = round(total_tva * shipping_ratio, 2)
        else:
            shipping_ht = 0.0
            shipping_tva = 0.0

        amount_ht = round(total_ht - shipping_ht, 2)
        amount_tva = round(total_tva - shipping_tva, 2)

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

        payment_method_raw: object = row["Payment Method"]
        sale_payment_method = str(payment_method_raw).strip() if _is_notna(payment_method_raw) else ""

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
            "sale_payment_method": sale_payment_method,
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
                        detail=f"Moyen de paiement non reconnu : « {payment_method_raw} » — vérifier la configuration des moyens de paiement",
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
            payout_reference: str | None = _normalize_payout_id(payout_id_raw) if _is_notna(payout_id_raw) else None

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
        orphan_sale_refs: list[str] = []

        for ref, sale in sales.items():
            txs = transactions.get(ref, [])
            charges = [tx for tx in txs if tx["type"] == "charge"]
            refunds = [tx for tx in txs if tx["type"] == "refund"]

            if charges:
                charge = charges[0]
                # Sum net/fee across all charges (handles split payments)
                total_net = round(sum(c["net"] for c in charges), 2)
                total_fee = round(sum(c["fee"] for c in charges), 2)
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
                    commission_ttc=total_fee,
                    commission_ht=total_fee,
                    net_amount=total_net,
                    payout_date=charge.get("payout_date"),
                    payout_reference=charge.get("payout_reference"),
                    payment_method=charge.get("payment_method"),
                    special_type=None,
                )
                result.append(tx)
            else:
                # Orphan sale or degraded mode (no transactions file)
                sale_pm = sale.get("sale_payment_method", "")
                direct_key: str | None = None
                if transactions and sale_pm:
                    for dp_key, dp_cfg in config.direct_payments.items():
                        if dp_cfg.sales_payment_method.lower() == sale_pm.lower():
                            direct_key = dp_key
                            break

                if direct_key is not None:
                    anomalies.append(
                        Anomaly(
                            type="direct_payment",
                            severity="info",
                            reference=ref,
                            channel="shopify",
                            detail=f"Paiement direct « {sale_pm} » — écriture de règlement générée. Vérifiez l'apurement du compte client.",
                            expected_value=None,
                            actual_value=sale_pm,
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
                        payment_method=direct_key,
                        special_type="direct_payment",
                    )
                else:
                    if transactions and abs(sale["amount_ttc"]) >= 0.01:
                        orphan_sale_refs.append(ref)
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
                    commission_ht=refund_tx["fee"],
                    net_amount=refund_tx["net"],
                    payout_date=refund_tx.get("payout_date"),
                    payout_reference=refund_tx.get("payout_reference"),
                    payment_method=refund_tx.get("payment_method"),
                    special_type=None,
                )
                result.append(tx)

        # --- Orphan sale summary (Issue #2) ---
        if orphan_sale_refs:
            refs_str = ", ".join(orphan_sale_refs)
            anomalies.append(
                Anomaly(
                    type="orphan_sale_summary",
                    severity="info",
                    reference="",
                    channel="shopify",
                    detail=f"{len(orphan_sale_refs)} commandes sans encaissement trouvé — Références : {refs_str}",
                    expected_value=None,
                    actual_value=None,
                )
            )

        # --- Orphan settlements (transactions without matching sale) ---
        # Determine the first sale reference number for prior-period detection
        first_sale_num: int | None = None
        if sales:
            sale_nums = [_extract_ref_number(k) for k in sales]
            valid_nums = [n for n in sale_nums if n is not None]
            if valid_nums:
                first_sale_num = min(valid_nums)

        prior_period_settlement_refs: list[str] = []
        prior_period_refund_refs: list[str] = []

        for ref, txs in transactions.items():
            if ref not in sales:
                # Separate orphan charges from orphan refunds
                orphan_charges = [tx for tx in txs if tx["type"] == "charge"]
                orphan_refunds = [tx for tx in txs if tx["type"] == "refund"]

                # Classify: prior period vs true orphan
                ref_num = _extract_ref_number(ref)
                is_prior = (
                    first_sale_num is not None
                    and ref_num is not None
                    and ref_num < first_sale_num
                )

                # --- Orphan charges (encaissements) ---
                if orphan_charges:
                    if is_prior:
                        prior_period_settlement_refs.append(ref)
                    else:
                        anomalies.append(
                            Anomaly(
                                type="orphan_settlement",
                                severity="warning",
                                reference=ref,
                                channel="shopify",
                                detail="Encaissement présent dans les Transactions mais aucune commande trouvée dans les Ventes — probable décalage de période entre les deux exports",
                                expected_value=None,
                                actual_value=None,
                            )
                        )

                # --- Orphan refunds (remboursements) ---
                if orphan_refunds:
                    if is_prior:
                        prior_period_refund_refs.append(ref)
                    else:
                        anomalies.append(
                            Anomaly(
                                type="orphan_refund",
                                severity="warning",
                                reference=ref,
                                channel="shopify",
                                detail=f"Remboursement pour la commande {ref} mais aucune vente d'origine trouvée — le remboursement est peut-être antérieur à la période exportée",
                                expected_value="vente correspondante",
                                actual_value="aucune",
                            )
                        )

                # Generate settlement-only entries for orphan transactions
                # so they contribute to lettrage balance on 511
                for orphan_tx in txs:
                    tx_type = "refund" if orphan_tx["type"] == "refund" else "sale"
                    net = round(float(orphan_tx["net"]), 2)
                    amount_ttc = round(abs(float(orphan_tx["amount"])), 2)
                    result.append(
                        NormalizedTransaction(
                            reference=ref,
                            channel="shopify",
                            date=orphan_tx.get("payout_date") or datetime.date.today(),
                            type=tx_type,
                            amount_ht=amount_ttc,
                            amount_tva=0.0,
                            amount_ttc=amount_ttc,
                            shipping_ht=0.0,
                            shipping_tva=0.0,
                            tva_rate=0.0,
                            country_code="000",
                            commission_ttc=orphan_tx["fee"],
                            commission_ht=orphan_tx["fee"],
                            net_amount=net,
                            payout_date=orphan_tx.get("payout_date"),
                            payout_reference=orphan_tx.get("payout_reference"),
                            payment_method=orphan_tx.get("payment_method"),
                            special_type="orphan_settlement",
                        )
                    )

        # --- Prior period settlement summary (charges) ---
        if prior_period_settlement_refs:
            refs_str = ", ".join(sorted(prior_period_settlement_refs, key=lambda r: _extract_ref_number(r) or 0))
            anomalies.append(
                Anomaly(
                    type="prior_period_settlement",
                    severity="info",
                    reference="",
                    channel="shopify",
                    detail=f"{len(prior_period_settlement_refs)} encaissement{'s' if len(prior_period_settlement_refs) > 1 else ''} concernent une période antérieure",
                    expected_value=None,
                    actual_value=refs_str,
                )
            )

        # --- Prior period refund summary (remboursements) ---
        if prior_period_refund_refs:
            refs_str = ", ".join(sorted(prior_period_refund_refs, key=lambda r: _extract_ref_number(r) or 0))
            anomalies.append(
                Anomaly(
                    type="prior_period_refund",
                    severity="info",
                    reference="",
                    channel="shopify",
                    detail=f"{len(prior_period_refund_refs)} remboursement{'s' if len(prior_period_refund_refs) > 1 else ''} concernent une période antérieure",
                    expected_value=None,
                    actual_value=refs_str,
                )
            )

        return result, anomalies

    def _parse_returns(
        self,
        returns_path: Path | BytesIO,
        sales_data: dict[str, dict[str, Any]],
        config: AppConfig,
    ) -> tuple[list[NormalizedTransaction], list[Anomaly]]:
        """Parse le fichier 'Total des retours par commande' et crée les NormalizedTransaction d'avoir."""
        channel_config = config.channels["shopify"]
        anomalies: list[Anomaly] = []

        df = pd.read_csv(
            returns_path,
            sep=channel_config.separator,
            encoding=channel_config.encoding,
        )
        self.validate_columns(df, REQUIRED_RETURNS_COLUMNS)

        # Convertir les colonnes montant en float
        for col in ["Retours nets", "Expédition retournée", "Taxes retournées", "Frais de retour", "Total des retours"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        # Filtrer les lignes avec Total des retours == 0
        df = df[df["Total des retours"] != 0].copy()

        if df.empty:
            return [], anomalies

        # Agréger par Nom de la commande
        agg = df.groupby("Nom de la commande", sort=False).agg(
            {
                "Jour": "min",
                "Retours nets": "sum",
                "Expédition retournée": "sum",
                "Taxes retournées": "sum",
                "Frais de retour": "sum",
                "Total des retours": "sum",
            }
        ).reset_index()

        transactions: list[NormalizedTransaction] = []

        for _, row in agg.iterrows():
            ref = str(row["Nom de la commande"])
            nets = round(abs(float(row["Retours nets"])), 2)
            shipping = round(abs(float(row["Expédition retournée"])), 2)
            taxes = round(abs(float(row["Taxes retournées"])), 2)
            frais_retour = round(float(row["Frais de retour"]), 2)

            # Anomalie si frais de retour non-zero
            if frais_retour != 0:
                anomalies.append(
                    Anomaly(
                        type="return_fee_nonzero",
                        severity="info",
                        reference=ref,
                        channel="shopify",
                        detail=f"Frais de retour de {frais_retour}€ détectés sur ce remboursement — à vérifier si ces frais sont normaux",
                        expected_value="0",
                        actual_value=str(frais_retour),
                    )
                )

            # Lookup country_code et tva_rate depuis sales_data
            sale = sales_data.get(ref)
            if sale is not None:
                country_code = str(sale["country_code"])
                fallback_tva_rate = float(sale["tva_rate"])
            else:
                country_code = "250"
                fallback_tva_rate = 20.0
                anomalies.append(
                    Anomaly(
                        type="return_no_matching_sale",
                        severity="warning",
                        reference=ref,
                        channel="shopify",
                        detail=f"Remboursement {ref} sans commande d'origine trouvée — pays par défaut (France) utilisé pour la comptabilisation",
                        expected_value=None,
                        actual_value=None,
                    )
                )

            # Calcul tva_rate : préférer le taux fiable de la vente d'origine (extrait du Tax Name)
            # Ne calculer depuis les montants qu'en fallback (retour orphelin sans vente)
            base = nets + shipping
            if sale is not None:
                tva_rate = fallback_tva_rate
            elif base > 0 and taxes > 0:
                tva_rate = round(taxes / base * 100, 2)
                if tva_rate > 30.0:
                    anomalies.append(
                        Anomaly(
                            type="return_tva_rate_aberrant",
                            severity="warning",
                            reference=ref,
                            channel="shopify",
                            detail=f"Taux TVA calculé aberrant ({tva_rate}%) sur remboursement orphelin — fallback au taux par défaut ({fallback_tva_rate}%)",
                            expected_value=str(fallback_tva_rate),
                            actual_value=str(tva_rate),
                        )
                    )
                    tva_rate = fallback_tva_rate
            else:
                tva_rate = fallback_tva_rate

            # Ventilation TVA entre produit et port (même logique que _parse_sales)
            if base > 0 and shipping > 0:
                shipping_ratio = shipping / base
                shipping_tva = round(taxes * shipping_ratio, 2)
            else:
                shipping_tva = 0.0
            amount_tva = round(taxes - shipping_tva, 2)

            # TTC
            amount_ttc = round(nets + shipping + taxes, 2)

            # Date
            date_str = str(row["Jour"])
            try:
                date = pd.to_datetime(date_str).date()
            except (ValueError, TypeError):
                date = datetime.date.today()

            tx = NormalizedTransaction(
                reference=ref,
                channel="shopify",
                date=date,
                type="refund",
                amount_ht=nets,
                amount_tva=amount_tva,
                amount_ttc=amount_ttc,
                shipping_ht=shipping,
                shipping_tva=shipping_tva,
                tva_rate=tva_rate,
                country_code=country_code,
                commission_ttc=0.0,
                commission_ht=0.0,
                net_amount=0.0,
                payout_date=None,
                payout_reference=None,
                payment_method=None,
                special_type="returns_avoir",
            )
            transactions.append(tx)

        logger.info("Retours Shopify : %d avoirs générés", len(transactions))
        return transactions, anomalies

    def _parse_payout_details(
        self,
        detail_files: list[Path],
        config: AppConfig,
    ) -> tuple[dict[str, list[PayoutDetail]], list[Anomaly]]:
        """Parse les fichiers detail transactions par versements."""
        channel_config = config.channels["shopify"]
        psp_mapping: dict[str, str] = {}
        for psp_name in config.psp:
            psp_mapping[psp_name] = psp_name

        anomalies: list[Anomaly] = []
        details_by_id: dict[str, list[PayoutDetail]] = {}
        seen_details: set[tuple[str, str, str, float, float]] = set()

        for fpath in detail_files:
            try:
                df = pd.read_csv(
                    fpath,
                    sep=channel_config.separator,
                    encoding=channel_config.encoding,
                )
            except Exception:
                anomalies.append(
                    Anomaly(
                        type="parse_warning",
                        severity="warning",
                        reference=fpath.name,
                        channel="shopify",
                        detail=f"Fichier detail illisible : {fpath.name}",
                        expected_value=None,
                        actual_value=None,
                    )
                )
                continue

            missing = [c for c in REQUIRED_PAYOUT_DETAIL_COLUMNS if c not in df.columns]
            if missing:
                anomalies.append(
                    Anomaly(
                        type="parse_warning",
                        severity="warning",
                        reference=fpath.name,
                        channel="shopify",
                        detail=f"Colonnes manquantes dans {fpath.name} : {', '.join(missing)}",
                        expected_value=None,
                        actual_value=None,
                    )
                )
                continue

            for _, row in df.iterrows():
                payout_id = _normalize_payout_id(row["Payout ID"])
                order = str(row["Order"])
                tx_type = str(row["Type"]).strip().lower()
                amount = round(float(row["Amount"]), 2)
                fee = round(float(row["Fee"]), 2)
                net = round(float(row["Net"]), 2)
                payment_method_raw = str(row["Payment Method Name"]).strip().lower()
                payment_method: str | None = psp_mapping.get(payment_method_raw)
                if payment_method is None:
                    anomalies.append(
                        Anomaly(
                            type="unknown_psp",
                            severity="warning",
                            reference=order,
                            channel="shopify",
                            detail=f"Moyen de paiement non reconnu : « {payment_method_raw} » — vérifier la configuration des moyens de paiement",
                            expected_value=None,
                            actual_value=payment_method_raw,
                        )
                    )

                payout_date_raw = row["Payout Date"]
                payout_date: datetime.date | None = None
                if _is_notna(payout_date_raw):
                    try:
                        payout_date = pd.to_datetime(str(payout_date_raw)).date()
                    except (ValueError, TypeError):
                        pass

                if payout_date is None:
                    anomalies.append(
                        Anomaly(
                            type="parse_warning",
                            severity="warning",
                            reference=order,
                            channel="shopify",
                            detail="Payout Date non parsable dans detail — ligne ignorée",
                            expected_value=None,
                            actual_value=str(payout_date_raw),
                        )
                    )
                    continue

                tx_date_raw = row["Transaction Date"]
                tx_date: datetime.date | None = None
                if _is_notna(tx_date_raw):
                    try:
                        tx_date = pd.to_datetime(str(tx_date_raw)).date()
                    except (ValueError, TypeError):
                        pass

                detail = PayoutDetail(
                    payout_date=payout_date,
                    payout_id=payout_id,
                    order_reference=order,
                    transaction_type=tx_type,
                    amount=amount,
                    fee=fee,
                    net=net,
                    payment_method=payment_method,
                    channel="shopify",
                    transaction_date=tx_date,
                )

                dedup_key = (payout_id, order, tx_type, amount, net)
                if dedup_key in seen_details:
                    continue
                seen_details.add(dedup_key)

                if payout_id not in details_by_id:
                    details_by_id[payout_id] = []
                details_by_id[payout_id].append(detail)

        return details_by_id, anomalies

    def _build_refunds_from_payout_details(
        self,
        payout_details_by_id: dict[str, list[PayoutDetail]],
        existing_transactions: list[NormalizedTransaction],
        sales_data: dict[str, dict[str, Any]],
    ) -> tuple[list[NormalizedTransaction], list[Anomaly]]:
        """Crée des NormalizedTransaction refund pour les remboursements présents
        dans les payout details mais absents du fichier Transactions Shopify.

        Ces transactions portent special_type='payout_detail_refund' pour que
        le moteur comptable ne génère que les écritures RG (pas d'avoir VE).
        """
        # Compteur des refunds déjà couverts par (order_reference, payout_id).
        # Un Counter plutôt qu'un set pour supporter les remboursements partiels
        # multiples sur la même commande dans le même batch de payout.
        existing_refund_counts: dict[tuple[str, str], int] = {}
        for tx in existing_transactions:
            if tx.type == "refund" and tx.payout_reference:
                key = (tx.reference, tx.payout_reference)
                existing_refund_counts[key] = existing_refund_counts.get(key, 0) + 1

        # Compteur des refunds dans les payout details par clé
        detail_refund_counts: dict[tuple[str, str], int] = {}

        result: list[NormalizedTransaction] = []
        anomalies: list[Anomaly] = []

        for payout_id, details in payout_details_by_id.items():
            for detail in details:
                if detail.transaction_type != "refund":
                    continue

                key = (detail.order_reference, detail.payout_id)
                detail_refund_counts[key] = detail_refund_counts.get(key, 0) + 1

                # Passer si ce refund est déjà couvert par les transactions existantes
                if detail_refund_counts[key] <= existing_refund_counts.get(key, 0):
                    continue

                # Récupérer le taux TVA et pays depuis la vente d'origine si disponible
                sale = sales_data.get(detail.order_reference)
                tva_rate = sale["tva_rate"] if sale else 0.0
                country_code = sale["country_code"] if sale else "000"

                amount_ttc = round(abs(detail.amount), 2)
                if tva_rate > 0:
                    amount_ht = round(amount_ttc / (1 + tva_rate / 100), 2)
                else:
                    amount_ht = amount_ttc
                amount_tva = round(amount_ttc - amount_ht, 2)

                entry_date = detail.transaction_date or detail.payout_date

                tx = NormalizedTransaction(
                    reference=detail.order_reference,
                    channel="shopify",
                    date=entry_date,
                    type="refund",
                    amount_ht=amount_ht,
                    amount_tva=amount_tva,
                    amount_ttc=amount_ttc,
                    shipping_ht=0.0,
                    shipping_tva=0.0,
                    tva_rate=tva_rate,
                    country_code=country_code,
                    commission_ttc=detail.fee,
                    commission_ht=detail.fee,
                    net_amount=detail.net,
                    payout_date=detail.payout_date,
                    payout_reference=detail.payout_id,
                    payment_method=detail.payment_method,
                    special_type="payout_detail_refund",
                )
                result.append(tx)

                anomalies.append(
                    Anomaly(
                        type="payout_detail_refund_discovered",
                        severity="info",
                        reference=detail.order_reference,
                        channel="shopify",
                        detail=(
                            f"Remboursement de {amount_ttc}€ pour la commande {detail.order_reference} "
                            f"détecté dans le détail du versement {detail.payout_id} "
                            f"— écriture de remboursement générée automatiquement"
                        ),
                        expected_value=None,
                        actual_value=None,
                    )
                )

                logger.info(
                    "Refund %s découvert dans payout detail %s (montant=%s€)",
                    detail.order_reference,
                    detail.payout_id,
                    amount_ttc,
                )

        return result, anomalies

    def _parse_payouts(
        self,
        payouts_path: Path,
        transactions: dict[str, list[dict[str, Any]]],
        config: AppConfig,
        payout_details_by_id: dict[str, list[PayoutDetail]] | None = None,
    ) -> tuple[list[PayoutSummary], list[Anomaly]]:
        """Lecture du fichier Versements PSP, construction des PayoutSummary."""
        channel_config = config.channels["shopify"]
        anomalies: list[Anomaly] = []

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
            psp_amounts: dict[str, float] | None = None
            if len(psp_types) == 1:
                psp_type = psp_types.pop()
            elif len(psp_types) > 1:
                # Multiple PSP types — compute per-PSP net amounts
                _psp_nets: dict[str, float] = {}
                for pid in matched_payout_ids:
                    for tx in tx_by_payout[pid]:
                        pm = tx.get("payment_method")
                        if pm is not None:
                            _psp_nets[pm] = round(_psp_nets.get(pm, 0.0) + tx.get("net", 0.0), 2)
                if _psp_nets:
                    psp_amounts = _psp_nets

            # Compute matched transaction net sum for aggregated mode balance
            matched_net_sum: float | None = None
            if matched_payout_ids:
                _net_sum = 0.0
                for pid in matched_payout_ids:
                    for tx in tx_by_payout[pid]:
                        _net_sum += tx.get("net", 0.0)
                matched_net_sum = round(_net_sum, 2)

            # Fallback : si tx_data ne couvre pas ce versement, chercher le
            # payout_reference dans payout_details_by_id via payout_date
            if payout_reference is None and payout_details_by_id is not None:
                for pid, dets in payout_details_by_id.items():
                    if dets and dets[0].payout_date == payout_date:
                        payout_reference = pid
                        psp_types_det = {d.payment_method for d in dets}
                        if len(psp_types_det) == 1:
                            psp_type = psp_types_det.pop()
                        break

            if payout_date is None:
                continue

            # Rattachement details
            details: list[PayoutDetail] | None = None
            if payout_details_by_id is not None and payout_reference is not None:
                details = payout_details_by_id.get(payout_reference)

            # Validation somme
            if details is not None:
                detail_sum = round(sum(d.net for d in details), 2)
                date_str = str(payout_date)
                if abs(detail_sum - total_amount) > config.matching_tolerance:
                    anomalies.append(
                        Anomaly(
                            type="payout_detail_mismatch",
                            severity="error",
                            reference=payout_reference or f"PAYOUT-{date_str}",
                            channel="shopify",
                            detail=f"Le détail du versement ({detail_sum}€) ne correspond pas au montant total versé ({total_amount}€) — écart de {round(abs(detail_sum - total_amount), 2)}€ à vérifier",
                            expected_value=str(total_amount),
                            actual_value=str(detail_sum),
                        )
                    )

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
                    details=details,
                    psp_amounts=psp_amounts,
                    matched_net_sum=matched_net_sum,
                )
            )

        # --- Contrôle : payout_missing_details (Story 4.3) ---
        if payout_details_by_id is not None and len(payout_details_by_id) > 0:
            for payout in payouts:
                if payout.details is None:
                    date_str = str(payout.payout_date)
                    anomalies.append(
                        Anomaly(
                            type="payout_missing_details",
                            severity="warning",
                            reference=payout.payout_reference or f"PAYOUT-{date_str}",
                            channel="shopify",
                            detail=f"Aucun fichier de détail trouvé pour le versement du {date_str} — le montant est comptabilisé en bloc sans ventilation par commande",
                            expected_value="fichier detail avec Payout ID correspondant",
                            actual_value="aucun fichier detail trouvé",
                        )
                    )

            # --- Contrôle : orphan_payout_detail (Story 4.3) ---
            payout_refs = {p.payout_reference for p in payouts if p.payout_reference is not None}
            for orphan_payout_id in payout_details_by_id:
                if orphan_payout_id not in payout_refs:
                    anomalies.append(
                        Anomaly(
                            type="orphan_payout_detail",
                            severity="warning",
                            reference=orphan_payout_id,
                            channel="shopify",
                            detail=f"Fichier de détail trouvé pour le versement {orphan_payout_id} mais ce versement n'apparaît pas dans le récapitulatif des versements",
                            expected_value="versement correspondant dans Détails versements.csv",
                            actual_value="aucun versement trouvé",
                        )
                    )

        return payouts, anomalies
