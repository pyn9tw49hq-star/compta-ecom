"""Tests unitaires pour les modèles de données et la hiérarchie d'exceptions."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from compta_ecom.models import (
    AccountingEntry,
    Anomaly,
    BalanceError,
    ComptaEcomError,
    ConfigError,
    NormalizedTransaction,
    ParseError,
    ParseResult,
    PayoutSummary,
)


class TestNormalizedTransaction:
    def test_construction_all_fields(self) -> None:
        tx = NormalizedTransaction(
            reference="REF001",
            channel="shopify",
            date=date(2024, 1, 15),
            type="sale",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=120.0,
            shipping_ht=5.0,
            shipping_tva=1.0,
            tva_rate=20.0,
            country_code="250",
            commission_ttc=3.6,
            commission_ht=3.0,
            net_amount=116.4,
            payout_date=date(2024, 1, 20),
            payout_reference="PAY001",
            payment_method="card",
            special_type=None,
        )
        assert tx.reference == "REF001"
        assert tx.amount_ttc == 120.0
        assert tx.payment_method == "card"
        assert tx.special_type is None

    def test_construction_optional_none(self) -> None:
        tx = NormalizedTransaction(
            reference="REF002",
            channel="shopify",
            date=date(2024, 1, 15),
            type="sale",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=120.0,
            shipping_ht=0.0,
            shipping_tva=0.0,
            tva_rate=20.0,
            country_code="250",
            commission_ttc=0.0,
            commission_ht=0.0,
            net_amount=120.0,
            payout_date=None,
            payout_reference=None,
            payment_method=None,
            special_type=None,
        )
        assert tx.payout_date is None
        assert tx.payout_reference is None
        assert tx.payment_method is None

    def test_frozen_immutability(self) -> None:
        tx = NormalizedTransaction(
            reference="REF003",
            channel="shopify",
            date=date(2024, 1, 15),
            type="sale",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=120.0,
            shipping_ht=0.0,
            shipping_tva=0.0,
            tva_rate=20.0,
            country_code="250",
            commission_ttc=0.0,
            commission_ht=0.0,
            net_amount=120.0,
            payout_date=None,
            payout_reference=None,
            payment_method=None,
            special_type=None,
        )
        with pytest.raises(FrozenInstanceError):
            tx.reference = "CHANGED"  # type: ignore[misc]


class TestAccountingEntry:
    def test_construction(self) -> None:
        entry = AccountingEntry(
            date=date(2024, 1, 15),
            journal="VE",
            account="411SHOPIFY",
            label="Vente REF001",
            debit=120.0,
            credit=0.0,
            piece_number="REF001",
            lettrage="REF001",
            channel="shopify",
            entry_type="sale",
        )
        assert entry.account == "411SHOPIFY"
        assert entry.debit == 120.0
        assert entry.credit == 0.0

    def test_frozen_immutability(self) -> None:
        entry = AccountingEntry(
            date=date(2024, 1, 15),
            journal="VE",
            account="411SHOPIFY",
            label="Vente",
            debit=120.0,
            credit=0.0,
            piece_number="REF001",
            lettrage="REF001",
            channel="shopify",
            entry_type="sale",
        )
        with pytest.raises(FrozenInstanceError):
            entry.debit = 0.0  # type: ignore[misc]


class TestAnomaly:
    def test_construction(self) -> None:
        anomaly = Anomaly(
            type="missing_field",
            severity="warning",
            reference="REF001",
            channel="shopify",
            detail="Champ manquant",
            expected_value="100.0",
            actual_value=None,
        )
        assert anomaly.type == "missing_field"
        assert anomaly.expected_value == "100.0"
        assert anomaly.actual_value is None

    def test_frozen_immutability(self) -> None:
        anomaly = Anomaly(
            type="error",
            severity="critical",
            reference="REF001",
            channel="shopify",
            detail="Erreur",
            expected_value=None,
            actual_value=None,
        )
        with pytest.raises(FrozenInstanceError):
            anomaly.type = "changed"  # type: ignore[misc]


class TestPayoutSummary:
    def test_construction(self) -> None:
        payout = PayoutSummary(
            payout_date=date(2024, 1, 20),
            channel="shopify",
            total_amount=1000.0,
            charges=50.0,
            refunds=20.0,
            fees=15.0,
            transaction_references=["REF001", "REF002"],
            psp_type="card",
            payout_reference="PAY001",
        )
        assert payout.total_amount == 1000.0
        assert len(payout.transaction_references) == 2

    def test_construction_optional_none(self) -> None:
        payout = PayoutSummary(
            payout_date=date(2024, 1, 20),
            channel="shopify",
            total_amount=500.0,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=[],
            psp_type=None,
            payout_reference=None,
        )
        assert payout.psp_type is None
        assert payout.payout_reference is None

    def test_frozen_immutability(self) -> None:
        payout = PayoutSummary(
            payout_date=date(2024, 1, 20),
            channel="shopify",
            total_amount=500.0,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=[],
            psp_type=None,
            payout_reference=None,
        )
        with pytest.raises(FrozenInstanceError):
            payout.total_amount = 999.0  # type: ignore[misc]


class TestParseResult:
    def test_construction(self) -> None:
        result = ParseResult(
            transactions=[],
            payouts=[],
            anomalies=[],
            channel="shopify",
        )
        assert result.channel == "shopify"
        assert result.transactions == []

    def test_frozen_immutability(self) -> None:
        result = ParseResult(
            transactions=[],
            payouts=[],
            anomalies=[],
            channel="shopify",
        )
        with pytest.raises(FrozenInstanceError):
            result.channel = "other"  # type: ignore[misc]


class TestExceptionHierarchy:
    def test_compta_ecom_error_inherits_exception(self) -> None:
        assert issubclass(ComptaEcomError, Exception)

    def test_config_error_inherits_compta_ecom_error(self) -> None:
        assert issubclass(ConfigError, ComptaEcomError)

    def test_parse_error_inherits_compta_ecom_error(self) -> None:
        assert issubclass(ParseError, ComptaEcomError)

    def test_balance_error_inherits_compta_ecom_error(self) -> None:
        assert issubclass(BalanceError, ComptaEcomError)

    def test_exceptions_carry_message(self) -> None:
        err = ConfigError("fichier manquant")
        assert str(err) == "fichier manquant"

        err2 = ParseError("colonne absente")
        assert str(err2) == "colonne absente"

        err3 = BalanceError("déséquilibre")
        assert str(err3) == "déséquilibre"
