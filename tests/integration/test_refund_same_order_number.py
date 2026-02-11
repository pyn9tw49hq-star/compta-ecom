"""Tests d'intégration — Remboursement avec même numéro de commande que la vente."""

from __future__ import annotations

from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.engine.sale_entries import generate_sale_entries
from compta_ecom.models import NormalizedTransaction
from compta_ecom.parsers.mirakl import MiraklParser

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "decathlon"


@pytest.fixture()
def parse_result_same_order(sample_config: AppConfig):
    """Parse la fixture avec même numéro de commande pour vente et remboursement."""
    parser = MiraklParser(channel="decathlon")
    files = {"data": FIXTURES_DIR / "decathlon_data_refund_same_order.csv"}
    return parser.parse(files, sample_config)


@pytest.fixture()
def transactions_same_order(parse_result_same_order) -> list[NormalizedTransaction]:
    """Toutes les transactions parsées."""
    return parse_result_same_order.transactions


class TestSameOrderNumberParsing:
    """Vérification que vente et remboursement sur même numéro sont séparés."""

    def test_two_transactions_generated(
        self, transactions_same_order: list[NormalizedTransaction]
    ) -> None:
        """1 vente + 1 refund = 2 transactions malgré même numéro de commande."""
        assert len(transactions_same_order) == 2

    def test_one_sale_one_refund(
        self, transactions_same_order: list[NormalizedTransaction]
    ) -> None:
        """Une transaction sale et une transaction refund."""
        sales = [t for t in transactions_same_order if t.type == "sale"]
        refunds = [t for t in transactions_same_order if t.type == "refund"]
        assert len(sales) == 1
        assert len(refunds) == 1

    def test_sale_has_original_reference(
        self, transactions_same_order: list[NormalizedTransaction]
    ) -> None:
        """La vente conserve la référence originale."""
        sales = [t for t in transactions_same_order if t.type == "sale"]
        assert sales[0].reference == "DECR001"

    def test_refund_has_original_reference(
        self, transactions_same_order: list[NormalizedTransaction]
    ) -> None:
        """Le remboursement conserve la référence commande originale (pas de suffixe -R)."""
        refunds = [t for t in transactions_same_order if t.type == "refund"]
        assert refunds[0].reference == "DECR001"

    def test_sale_amounts_positive(
        self, transactions_same_order: list[NormalizedTransaction]
    ) -> None:
        """La vente a des montants positifs."""
        sales = [t for t in transactions_same_order if t.type == "sale"]
        sale = sales[0]
        assert sale.amount_ht > 0
        assert sale.amount_ttc > 0

    def test_refund_amounts_positive(
        self, transactions_same_order: list[NormalizedTransaction]
    ) -> None:
        """Le remboursement a des montants en valeur absolue (positifs)."""
        refunds = [t for t in transactions_same_order if t.type == "refund"]
        refund = refunds[0]
        assert refund.amount_ht > 0
        assert refund.amount_ttc > 0


class TestSameOrderNumberEntries:
    """Écritures comptables pour vente et remboursement sur même numéro."""

    def test_sale_entries_credit_707(
        self,
        transactions_same_order: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """La vente a 707 au crédit."""
        sales = [t for t in transactions_same_order if t.type == "sale"]
        entries = generate_sale_entries(sales[0], sample_config)
        entry_707 = [e for e in entries if e.account.startswith("707")]
        assert len(entry_707) == 1
        assert entry_707[0].credit > 0

    def test_refund_entries_debit_707(
        self,
        transactions_same_order: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Le remboursement a 707 au débit (avoir)."""
        refunds = [t for t in transactions_same_order if t.type == "refund"]
        entries = generate_sale_entries(refunds[0], sample_config)
        entry_707 = [e for e in entries if e.account.startswith("707")]
        assert len(entry_707) == 1
        assert entry_707[0].debit > 0

    def test_both_entries_balanced(
        self,
        transactions_same_order: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Les écritures sont équilibrées pour les deux transactions."""
        for tx in transactions_same_order:
            entries = generate_sale_entries(tx, sample_config)
            verify_balance(entries)
