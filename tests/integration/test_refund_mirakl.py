"""Tests d'intégration E2E — Mirakl (Décathlon) refund."""

from __future__ import annotations

from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.engine.marketplace_entries import generate_marketplace_commission
from compta_ecom.engine.sale_entries import generate_sale_entries
from compta_ecom.models import NormalizedTransaction
from compta_ecom.parsers.mirakl import MiraklParser

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "decathlon"


@pytest.fixture()
def mirakl_parse_result(sample_config: AppConfig):
    """Parse les fixtures Mirakl (Décathlon) refund → ParseResult."""
    parser = MiraklParser(channel="decathlon")
    files = {"data": FIXTURES_DIR / "decathlon_data_refund.csv"}
    return parser.parse(files, sample_config)


@pytest.fixture()
def mirakl_transactions(mirakl_parse_result) -> list[NormalizedTransaction]:  # type: ignore[no-untyped-def]
    """Toutes les transactions parsées."""
    return mirakl_parse_result.transactions


@pytest.fixture()
def mirakl_refund(
    mirakl_transactions: list[NormalizedTransaction],
) -> NormalizedTransaction:
    """La transaction refund Mirakl."""
    matches = [t for t in mirakl_transactions if t.type == "refund"]
    assert len(matches) == 1, f"Expected 1 refund, got {len(matches)}"
    return matches[0]


class TestMiraklRefundParsing:
    """Vérification du parsing Mirakl refund."""

    def test_transaction_count(self, mirakl_transactions: list[NormalizedTransaction]) -> None:
        """1 vente + 1 refund = 2 transactions."""
        sales = [t for t in mirakl_transactions if t.type == "sale"]
        refunds = [t for t in mirakl_transactions if t.type == "refund"]
        assert len(sales) == 1
        assert len(refunds) == 1

    def test_refund_determined_by_sign(self, mirakl_refund: NormalizedTransaction) -> None:
        """Montant négatif dans le CSV → type='refund'."""
        assert mirakl_refund.type == "refund"

    def test_refund_amounts_positive(self, mirakl_refund: NormalizedTransaction) -> None:
        """Montants en valeur absolue."""
        assert mirakl_refund.amount_ht == 100.00
        assert mirakl_refund.amount_ttc > 0

    def test_refund_channel(self, mirakl_refund: NormalizedTransaction) -> None:
        """Canal = decathlon."""
        assert mirakl_refund.channel == "decathlon"


class TestMiraklRefundEntries:
    """Écritures de vente et commission pour refund Mirakl (Décathlon)."""

    def test_sale_entries_inversees(
        self,
        mirakl_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Écritures vente refund inversées."""
        entries = generate_sale_entries(mirakl_refund, sample_config)

        entry_411 = [e for e in entries if e.account == "411DECA"]
        entry_707 = [e for e in entries if e.account.startswith("707")]

        assert len(entry_411) == 1
        assert len(entry_707) == 1

        # 411 au crédit
        assert entry_411[0].credit > 0
        assert entry_411[0].debit == 0.0

        # 707 au débit
        assert entry_707[0].debit > 0
        assert entry_707[0].credit == 0.0

    def test_sale_entries_balance(
        self,
        mirakl_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance vérifiée."""
        entries = generate_sale_entries(mirakl_refund, sample_config)
        verify_balance(entries)

    def test_sale_entries_entry_type(
        self,
        mirakl_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """entry_type = 'refund'."""
        entries = generate_sale_entries(mirakl_refund, sample_config)
        for e in entries:
            assert e.entry_type == "refund"

    def test_commission_marketplace_refund(
        self,
        mirakl_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Écritures commission marketplace pour refund Mirakl."""
        entries = generate_marketplace_commission(mirakl_refund, sample_config)

        # commission_ttc = 15 (positive → commission restituée au vendeur)
        assert len(entries) == 2

        entry_401 = [e for e in entries if e.account == "FDECATHLON"]
        entry_411 = [e for e in entries if e.account == "411DECA"]

        assert len(entry_401) == 1
        assert len(entry_411) == 1

        # 401 au débit, 411 au crédit (commission_ttc > 0)
        assert entry_401[0].debit == 15.00
        assert entry_411[0].credit == 15.00

    def test_commission_balance(
        self,
        mirakl_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance vérifiée."""
        entries = generate_marketplace_commission(mirakl_refund, sample_config)
        verify_balance(entries)

    def test_lettrage(
        self,
        mirakl_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Lettrage = référence commande."""
        sale_entries = generate_sale_entries(mirakl_refund, sample_config)
        commission_entries = generate_marketplace_commission(mirakl_refund, sample_config)

        for e in sale_entries + commission_entries:
            assert e.piece_number == "DECR002"
            assert e.lettrage == "DECR002"
