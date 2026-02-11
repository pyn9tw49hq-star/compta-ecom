"""Tests d'intégration — Format CSV réel Decathlon avec remboursements."""

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
def real_format_parse_result(sample_config: AppConfig):
    """Parse le fichier CSV format réel Decathlon."""
    parser = MiraklParser(channel="decathlon")
    files = {"data": FIXTURES_DIR / "Decathlon_real_format.csv"}
    return parser.parse(files, sample_config)


@pytest.fixture()
def real_format_transactions(real_format_parse_result) -> list[NormalizedTransaction]:
    """Toutes les transactions parsées du format réel."""
    return real_format_parse_result.transactions


@pytest.fixture()
def real_format_refund(
    real_format_transactions: list[NormalizedTransaction],
) -> NormalizedTransaction:
    """La transaction refund du format réel."""
    matches = [t for t in real_format_transactions if t.type == "refund"]
    assert len(matches) == 1, f"Expected 1 refund, got {len(matches)}"
    return matches[0]


@pytest.fixture()
def real_format_sale(
    real_format_transactions: list[NormalizedTransaction],
) -> NormalizedTransaction:
    """La transaction vente du format réel."""
    matches = [t for t in real_format_transactions if t.type == "sale"]
    assert len(matches) == 1, f"Expected 1 sale, got {len(matches)}"
    return matches[0]


class TestRealFormatParsing:
    """Vérification du parsing du format CSV réel Decathlon."""

    def test_transaction_count(self, real_format_transactions: list[NormalizedTransaction]) -> None:
        """1 vente + 1 refund = 2 transactions."""
        sales = [t for t in real_format_transactions if t.type == "sale"]
        refunds = [t for t in real_format_transactions if t.type == "refund"]
        assert len(sales) == 1, f"Expected 1 sale, got {len(sales)}"
        assert len(refunds) == 1, f"Expected 1 refund, got {len(refunds)}"

    def test_refund_reference(self, real_format_refund: NormalizedTransaction) -> None:
        """Référence du remboursement correcte."""
        assert real_format_refund.reference == "DECREAL002"

    def test_refund_amounts(self, real_format_refund: NormalizedTransaction) -> None:
        """Montants du remboursement (CSV TTC / 1.20 = HT)."""
        assert real_format_refund.amount_ht == 615.83
        assert real_format_refund.shipping_ht == 3.33
        assert real_format_refund.commission_ttc == 74.30

    def test_sale_reference(self, real_format_sale: NormalizedTransaction) -> None:
        """Référence de la vente correcte."""
        assert real_format_sale.reference == "DECREAL001"

    def test_sale_amounts(self, real_format_sale: NormalizedTransaction) -> None:
        """Montants de la vente (CSV TTC / 1.20 = HT)."""
        assert real_format_sale.amount_ht == 49.17
        assert real_format_sale.shipping_ht == 3.33
        # Commission négative pour vente (prélevée)
        assert real_format_sale.commission_ttc == -6.30


class TestRealFormatRefundEntries:
    """Écritures comptables pour remboursement format réel."""

    def test_sale_entries_are_avoirs(
        self,
        real_format_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Écritures vente refund = avoirs (débit/crédit inversés)."""
        entries = generate_sale_entries(real_format_refund, sample_config)

        # Trouver l'écriture client (411)
        entry_411 = [e for e in entries if e.account == "CDECATHLON"]
        assert len(entry_411) == 1

        # 411 au crédit pour un avoir
        assert entry_411[0].credit > 0
        assert entry_411[0].debit == 0.0

        # Vérifier le label
        assert "Avoir" in entry_411[0].label

    def test_sale_entries_journal_dec(
        self,
        real_format_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Journal = DEC pour Decathlon."""
        entries = generate_sale_entries(real_format_refund, sample_config)
        for e in entries:
            assert e.journal == "DEC", f"Expected journal DEC, got {e.journal}"

    def test_sale_entries_entry_type_refund(
        self,
        real_format_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """entry_type = 'refund'."""
        entries = generate_sale_entries(real_format_refund, sample_config)
        for e in entries:
            assert e.entry_type == "refund", f"Expected entry_type refund, got {e.entry_type}"

    def test_sale_entries_balance(
        self,
        real_format_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance vérifiée."""
        entries = generate_sale_entries(real_format_refund, sample_config)
        verify_balance(entries)

    def test_commission_refund_inverted(
        self,
        real_format_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Commission remboursée : 411 débit, 401 crédit."""
        entries = generate_marketplace_commission(real_format_refund, sample_config)

        # commission_ttc = 74.30 (positive → commission restituée)
        assert len(entries) == 2

        entry_charge = [e for e in entries if e.account == "62220800"]
        entry_411 = [e for e in entries if e.account == "CDECATHLON"]

        assert len(entry_charge) == 1
        assert len(entry_411) == 1

        # 411 au débit, compte charge au crédit
        assert entry_411[0].debit == 74.30
        assert entry_charge[0].credit == 74.30

    def test_commission_balance(
        self,
        real_format_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance commission vérifiée."""
        entries = generate_marketplace_commission(real_format_refund, sample_config)
        verify_balance(entries)


class TestRealFormatSaleEntries:
    """Écritures comptables pour vente format réel."""

    def test_sale_entries_debit_client(
        self,
        real_format_sale: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Vente normale : 411 au débit."""
        entries = generate_sale_entries(real_format_sale, sample_config)

        entry_411 = [e for e in entries if e.account == "CDECATHLON"]
        assert len(entry_411) == 1

        # 411 au débit pour une vente
        assert entry_411[0].debit > 0
        assert entry_411[0].credit == 0.0

        # Vérifier le label
        assert "Vente" in entry_411[0].label

    def test_sale_entries_journal_dec(
        self,
        real_format_sale: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Journal = DEC pour Decathlon."""
        entries = generate_sale_entries(real_format_sale, sample_config)
        for e in entries:
            assert e.journal == "DEC"

    def test_sale_entries_entry_type_sale(
        self,
        real_format_sale: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """entry_type = 'sale'."""
        entries = generate_sale_entries(real_format_sale, sample_config)
        for e in entries:
            assert e.entry_type == "sale"
