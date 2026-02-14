"""Tests unitaires pour ShopifyParser — Transactions, Matching, Versements PSP."""

from __future__ import annotations

import datetime
from pathlib import Path
import pandas as pd
import pytest

from compta_ecom.config.loader import AppConfig, ChannelConfig, DirectPaymentConfig, PspConfig
from compta_ecom.models import ParseError
from compta_ecom.parsers.shopify import ShopifyParser


@pytest.fixture
def shopify_config() -> AppConfig:
    """AppConfig avec PSP mapping pour les tests Transactions."""
    return AppConfig(
        clients={"shopify": "411SHOPIFY"},
        fournisseurs={"manomano": "FMANO"},
        psp={
            "card": PspConfig(compte="51150007", commission="62700002"),
            "paypal": PspConfig(compte="51150004", commission="62700001"),
            "klarna": PspConfig(compte="51150005", commission="62700003"),
        },
        transit="58000000",
        banque="51200000",
        comptes_speciaux={"ADJUSTMENT": "51150002"},
        comptes_vente_prefix="707",
        canal_codes={"shopify": "01"},
        comptes_tva_prefix="4457",
        vat_table={
            "250": {"name": "France", "rate": 20.0, "alpha2": "FR"},
            "056": {"name": "Belgique", "rate": 21.0, "alpha2": "BE"},
        },
        alpha2_to_numeric={"FR": "250", "BE": "056"},
        channels={
            "shopify": ChannelConfig(
                files={"sales": "Ventes*.csv", "transactions": "Transactions*.csv", "payouts": "Versements*.csv"},
                encoding="utf-8",
                separator=",",
            ),
        },
        direct_payments={
            "klarna": DirectPaymentConfig(compte="46740000", sales_payment_method="Klarna"),
            "bank_deposit": DirectPaymentConfig(compte="58010000", sales_payment_method="Bank Deposit"),
        },
    )


def _make_sales_csv(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    """Crée un fichier CSV Ventes."""
    df = pd.DataFrame(rows)
    path = tmp_path / "sales.csv"
    df.to_csv(path, index=False)
    return path


def _make_transactions_csv(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    """Crée un fichier CSV Transactions."""
    df = pd.DataFrame(rows)
    path = tmp_path / "transactions.csv"
    df.to_csv(path, index=False)
    return path


def _make_payouts_csv(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    """Crée un fichier CSV Versements PSP."""
    df = pd.DataFrame(rows)
    path = tmp_path / "payouts.csv"
    df.to_csv(path, index=False)
    return path


def _base_sale(**overrides: object) -> dict[str, object]:
    """Ligne CSV Ventes de base."""
    row: dict[str, object] = {
        "Name": "#1001",
        "Created at": "2025-01-15",
        "Subtotal": 100.0,
        "Shipping": 10.0,
        "Taxes": 22.0,
        "Total": 132.0,
        "Tax 1 Name": "FR TVA 20%",
        "Tax 1 Value": 22.0,
        "Payment Method": "Carte",
        "Shipping Country": "FR",
    }
    row.update(overrides)
    return row


def _base_transaction(**overrides: object) -> dict[str, object]:
    """Ligne CSV Transactions de base."""
    row: dict[str, object] = {
        "Order": "#1001",
        "Type": "charge",
        "Payment Method Name": "card",
        "Amount": 132.0,
        "Fee": 3.96,
        "Net": 128.04,
        "Payout Date": "2025-01-17",
        "Payout ID": "PAY-001",
    }
    row.update(overrides)
    return row


def _base_payout(**overrides: object) -> dict[str, object]:
    """Ligne CSV Versements PSP de base."""
    row: dict[str, object] = {
        "Payout Date": "2025-01-17",
        "Charges": 132.0,
        "Refunds": 0.0,
        "Fees": 3.96,
        "Total": 128.04,
    }
    row.update(overrides)
    return row


class TestParsingTransactionsNominal:
    def test_charge_and_refund(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """CSV nominal avec 1 charge + 1 refund → dict groupé par Order."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [
            _base_transaction(),
            _base_transaction(Type="refund", Amount=-50.0, Fee=-1.50, Net=-48.50, **{"Payout ID": "PAY-001"}),
        ])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        assert len(result.transactions) == 2
        sale_tx = next(tx for tx in result.transactions if tx.type == "sale")
        refund_tx = next(tx for tx in result.transactions if tx.type == "refund")

        assert sale_tx.reference == "#1001"
        assert sale_tx.payment_method == "card"
        assert sale_tx.commission_ttc == 3.96
        assert sale_tx.net_amount == 128.04

        assert refund_tx.reference == "#1001"
        assert refund_tx.type == "refund"
        assert refund_tx.payment_method == "card"

    def test_missing_transactions_columns(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Colonnes manquantes dans Transactions → ParseError."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        df = pd.DataFrame({"Order": ["#1001"], "Type": ["charge"]})
        tx_path = tmp_path / "transactions.csv"
        df.to_csv(tx_path, index=False)

        parser = ShopifyParser()
        with pytest.raises(ParseError, match="Colonnes manquantes"):
            parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)


class TestPspMapping:
    def test_known_psp_card(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """card → mapped to 'card' PSP."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction(**{"Payment Method Name": "card"})])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        assert result.transactions[0].payment_method == "card"

    def test_unknown_psp(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """PSP inconnu → Anomaly(type='unknown_psp'), payment_method=None."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction(**{"Payment Method Name": "bitcoin"})])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        anomalies = [a for a in result.anomalies if a.type == "unknown_psp"]
        assert len(anomalies) == 1
        assert "bitcoin" in anomalies[0].detail
        assert result.transactions[0].payment_method is None


class TestTransactionTypeFiltering:
    def test_unknown_type(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Type inconnu → Anomaly(type='parse_warning'), ligne ignorée."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [
            _base_transaction(),  # charge - kept
            _base_transaction(Type="adjustment"),  # unknown - ignored
        ])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        anomalies = [a for a in result.anomalies if a.type == "parse_warning" and "inconnu" in a.detail]
        assert len(anomalies) == 1
        assert "adjustment" in anomalies[0].actual_value  # type: ignore[operator]

        # Only the charge should produce a NormalizedTransaction
        assert len(result.transactions) == 1
        assert result.transactions[0].type == "sale"


class TestMatching:
    def test_sale_with_charge(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """1 vente + 1 charge → NormalizedTransaction complète."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction()])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        assert len(result.transactions) == 1
        tx = result.transactions[0]
        assert tx.type == "sale"
        assert tx.payment_method == "card"
        assert tx.commission_ttc == 3.96
        assert tx.net_amount == 128.04
        assert tx.payout_date == datetime.date(2025, 1, 17)
        assert tx.payout_reference == "PAY-001"

    def test_sale_with_charge_and_refund(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """1 vente + 1 charge + 1 refund → 2 NormalizedTransaction."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [
            _base_transaction(),
            _base_transaction(Type="refund", Amount=-50.0, Fee=-1.50, Net=-48.50),
        ])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        assert len(result.transactions) == 2
        sale_tx = next(tx for tx in result.transactions if tx.type == "sale")
        refund_tx = next(tx for tx in result.transactions if tx.type == "refund")

        assert sale_tx.commission_ttc == 3.96
        assert sale_tx.net_amount == 128.04

        # Refund amounts: abs(Amount)=50.0, back-calc HT
        assert refund_tx.amount_ttc == 50.0
        assert refund_tx.amount_ht == round(50.0 / 1.20, 2)
        assert refund_tx.shipping_ht == 0.0
        assert refund_tx.shipping_tva == 0.0
        assert refund_tx.commission_ttc == -1.50  # signed, negative
        assert refund_tx.net_amount == -48.50  # signed, negative

    def test_negative_fee_on_refund(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Fee négatif sur refund → commission_ttc négatif correctement propagé."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [
            _base_transaction(),
            _base_transaction(Type="refund", Amount=-132.0, Fee=-3.96, Net=-128.04),
        ])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        refund_tx = next(tx for tx in result.transactions if tx.type == "refund")
        assert refund_tx.commission_ttc == -3.96

    def test_orphan_sale_no_charge(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Vente sans charge → Anomaly(type='orphan_sale') + NormalizedTransaction dégradée."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        # Only a refund transaction, no charge
        tx_path = _make_transactions_csv(tmp_path, [
            _base_transaction(Type="refund", Amount=-50.0, Fee=-1.50, Net=-48.50),
        ])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        anomalies = [a for a in result.anomalies if a.type == "orphan_sale"]
        assert len(anomalies) == 1
        assert anomalies[0].reference == "#1001"

        # Degraded NormalizedTransaction for the sale
        sale_tx = next(tx for tx in result.transactions if tx.type == "sale")
        assert sale_tx.payment_method is None
        assert sale_tx.commission_ttc == 0.0
        assert sale_tx.net_amount == sale_tx.amount_ttc

        # Refund should still be generated
        refund_tx = next(tx for tx in result.transactions if tx.type == "refund")
        assert refund_tx.amount_ttc == 50.0

    def test_orphan_settlement(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Transaction sans vente → Anomaly(type='orphan_settlement'), pas de NormalizedTransaction."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale(Name="#1001")])
        tx_path = _make_transactions_csv(tmp_path, [
            _base_transaction(Order="#1001"),  # matches
            _base_transaction(Order="#9999"),  # orphan
        ])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        anomalies = [a for a in result.anomalies if a.type == "orphan_settlement"]
        assert len(anomalies) == 1
        assert anomalies[0].reference == "#9999"

        # #1001 is a normal transaction, #9999 is an orphan_settlement
        normal_txs = [tx for tx in result.transactions if tx.special_type is None]
        assert {tx.reference for tx in normal_txs} == {"#1001"}

        orphan_txs = [tx for tx in result.transactions if tx.special_type == "orphan_settlement"]
        assert len(orphan_txs) == 1
        assert orphan_txs[0].reference == "#9999"


class TestSplitPayment:
    """Tests for split payments: multiple charges for the same order."""

    def test_split_payment_sums_net_and_fee(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """2 charges for 1 order → commission_ttc = sum(fees), net_amount = sum(nets)."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale(Subtotal=200.0, Taxes=40.0, Total=250.0, Shipping=10.0)])
        tx_path = _make_transactions_csv(tmp_path, [
            _base_transaction(Order="#1001", Amount=150.0, Fee=4.50, Net=145.50, **{"Payment Method Name": "card", "Payout ID": "PAY-001"}),
            _base_transaction(Order="#1001", Amount=100.0, Fee=3.00, Net=97.00, **{"Payment Method Name": "paypal", "Payout ID": "PAY-002"}),
        ])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        sale_tx = next(tx for tx in result.transactions if tx.type == "sale")
        # Sum of fees across both charges
        assert sale_tx.commission_ttc == round(4.50 + 3.00, 2)
        # Sum of nets across both charges
        assert sale_tx.net_amount == round(145.50 + 97.00, 2)
        # payout_reference and payment_method from charges[0]
        assert sale_tx.payout_reference == "PAY-001"
        assert sale_tx.payment_method == "card"


class TestParsingPayouts:
    def test_payout_summary(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """CSV Versements nominal → PayoutSummary avec totaux corrects."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction()])
        payouts_path = _make_payouts_csv(tmp_path, [_base_payout()])

        parser = ShopifyParser()
        result = parser.parse(
            {"sales": sales_path, "transactions": tx_path, "payouts": payouts_path},
            shopify_config,
        )

        assert len(result.payouts) == 1
        payout = result.payouts[0]
        assert payout.payout_date == datetime.date(2025, 1, 17)
        assert payout.charges == 132.0
        assert payout.refunds == 0.0
        assert payout.fees == 3.96
        assert payout.total_amount == 128.04
        assert payout.channel == "shopify"

    def test_payout_transaction_references_by_payout_id(
        self, tmp_path: Path, shopify_config: AppConfig
    ) -> None:
        """transaction_references regroupées par Payout ID."""
        sales_path = _make_sales_csv(tmp_path, [
            _base_sale(Name="#1001"),
            _base_sale(Name="#1002", Subtotal=50.0, Shipping=5.0, Taxes=11.0, Total=66.0),
        ])
        tx_path = _make_transactions_csv(tmp_path, [
            _base_transaction(Order="#1001", **{"Payout ID": "PAY-001"}),
            _base_transaction(Order="#1002", Amount=66.0, Fee=1.98, Net=64.02, **{"Payout ID": "PAY-001"}),
        ])
        payouts_path = _make_payouts_csv(tmp_path, [
            _base_payout(Charges=198.0, Fees=5.94, Total=192.06),
        ])

        parser = ShopifyParser()
        result = parser.parse(
            {"sales": sales_path, "transactions": tx_path, "payouts": payouts_path},
            shopify_config,
        )

        assert len(result.payouts) == 1
        payout = result.payouts[0]
        assert sorted(payout.transaction_references) == ["#1001", "#1002"]
        assert payout.payout_reference == "PAY-001"

    def test_missing_payouts_columns(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Colonnes manquantes dans Versements → ParseError."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction()])
        df = pd.DataFrame({"Payout Date": ["2025-01-17"]})
        payouts_path = tmp_path / "payouts.csv"
        df.to_csv(payouts_path, index=False)

        parser = ShopifyParser()
        with pytest.raises(ParseError, match="Colonnes manquantes"):
            parser.parse(
                {"sales": sales_path, "transactions": tx_path, "payouts": payouts_path},
                shopify_config,
            )


class TestDegradedMode:
    def test_transactions_absent(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Fichier Transactions absent → WARNING + toutes NormalizedTransaction dégradées."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path}, shopify_config)

        assert len(result.transactions) == 1
        tx = result.transactions[0]
        assert tx.payment_method is None
        assert tx.commission_ttc == 0.0
        assert tx.net_amount == tx.amount_ttc
        assert tx.payout_date is None
        assert tx.payout_reference is None

    def test_payouts_absent(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Fichier Versements absent → WARNING + payouts vide."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction()])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        assert result.payouts == []

    def test_both_absent(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Transactions et Versements absents → mode dégradé complet."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale()])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path}, shopify_config)

        assert len(result.transactions) == 1
        assert result.payouts == []
        tx = result.transactions[0]
        assert tx.payment_method is None
        assert tx.commission_ttc == 0.0
        assert tx.net_amount == tx.amount_ttc


class TestDirectPaymentOrphans:
    """Tests pour les ventes orphelines avec paiement direct (Klarna, Bank Deposit)."""

    def test_klarna_orphan_becomes_direct_payment(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Vente Payment Method=Klarna sans charge → special_type=direct_payment, payment_method=klarna."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale(**{"Payment Method": "Klarna"})])
        # Transaction pour une autre commande, donc #1001 est orpheline
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction(Order="#9999")])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        sale_tx = next(tx for tx in result.transactions if tx.reference == "#1001" and tx.type == "sale")
        assert sale_tx.special_type == "direct_payment"
        assert sale_tx.payment_method == "klarna"
        assert sale_tx.commission_ttc == 0.0
        assert sale_tx.net_amount == sale_tx.amount_ttc

        # Anomalie direct_payment (info), pas orphan_sale
        assert not any(a.type == "orphan_sale" and a.reference == "#1001" for a in result.anomalies)
        dp_anomalies = [a for a in result.anomalies if a.type == "direct_payment" and a.reference == "#1001"]
        assert len(dp_anomalies) == 1
        assert dp_anomalies[0].severity == "info"
        assert "Klarna" in dp_anomalies[0].detail

    def test_bank_deposit_orphan_becomes_direct_payment(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Vente Payment Method=Bank Deposit sans charge → special_type=direct_payment."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale(**{"Payment Method": "Bank Deposit"})])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction(Order="#9999")])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        sale_tx = next(tx for tx in result.transactions if tx.reference == "#1001" and tx.type == "sale")
        assert sale_tx.special_type == "direct_payment"
        assert sale_tx.payment_method == "bank_deposit"

        dp_anomalies = [a for a in result.anomalies if a.type == "direct_payment" and a.reference == "#1001"]
        assert len(dp_anomalies) == 1
        assert "Bank Deposit" in dp_anomalies[0].detail

    def test_unknown_payment_method_still_orphan_sale(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Vente Payment Method=Shopify Payments sans charge → orphan_sale classique (non-régression)."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale(**{"Payment Method": "Shopify Payments"})])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction(Order="#9999")])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)

        sale_tx = next(tx for tx in result.transactions if tx.reference == "#1001" and tx.type == "sale")
        assert sale_tx.special_type is None
        assert sale_tx.payment_method is None

        assert any(a.type == "orphan_sale" and a.reference == "#1001" for a in result.anomalies)
        assert not any(a.type == "direct_payment" and a.reference == "#1001" for a in result.anomalies)

    def test_klarna_case_insensitive(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Payment Method en minuscules 'klarna' → detecte comme direct_payment."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale(**{"Payment Method": "klarna"})])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction(Order="#9999")])
        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)
        sale_tx = next(tx for tx in result.transactions if tx.reference == "#1001" and tx.type == "sale")
        assert sale_tx.special_type == "direct_payment"
        assert sale_tx.payment_method == "klarna"

    def test_empty_payment_method_still_orphan(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Payment Method vide → orphan_sale classique, pas de direct_payment."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale(**{"Payment Method": ""})])
        tx_path = _make_transactions_csv(tmp_path, [_base_transaction(Order="#9999")])
        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path, "transactions": tx_path}, shopify_config)
        sale_tx = next(tx for tx in result.transactions if tx.reference == "#1001" and tx.type == "sale")
        assert sale_tx.special_type is None
        assert sale_tx.payment_method is None

    def test_no_transactions_file_no_direct_payment(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Mode dégradé (pas de fichier transactions) → pas de direct_payment même si Klarna."""
        sales_path = _make_sales_csv(tmp_path, [_base_sale(**{"Payment Method": "Klarna"})])

        parser = ShopifyParser()
        result = parser.parse({"sales": sales_path}, shopify_config)

        tx = result.transactions[0]
        assert tx.special_type is None
        assert tx.payment_method is None
        assert not any(a.type == "direct_payment" for a in result.anomalies)
