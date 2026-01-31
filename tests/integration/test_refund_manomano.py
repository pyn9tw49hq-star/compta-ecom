"""Tests d'intégration E2E — ManoMano refund."""

from __future__ import annotations

from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.engine.marketplace_entries import generate_marketplace_commission
from compta_ecom.engine.sale_entries import generate_sale_entries
from compta_ecom.models import NormalizedTransaction
from compta_ecom.parsers.manomano import ManoManoParser

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "manomano"


@pytest.fixture()
def manomano_parse_result(sample_config: AppConfig):
    """Parse les fixtures ManoMano refund → ParseResult."""
    parser = ManoManoParser()
    files = {
        "ca": FIXTURES_DIR / "ca_refund.csv",
        "payouts": FIXTURES_DIR / "versements_manomano_refund.csv",
    }
    return parser.parse(files, sample_config)


@pytest.fixture()
def manomano_transactions(manomano_parse_result) -> list[NormalizedTransaction]:  # type: ignore[no-untyped-def]
    """Toutes les transactions parsées."""
    return manomano_parse_result.transactions


@pytest.fixture()
def manomano_refund(
    manomano_transactions: list[NormalizedTransaction],
) -> NormalizedTransaction:
    """La transaction refund ManoMano."""
    matches = [t for t in manomano_transactions if t.type == "refund"]
    assert len(matches) == 1, f"Expected 1 refund, got {len(matches)}"
    return matches[0]


class TestManoManoRefundParsing:
    """Vérification du parsing correct des fixtures ManoMano refund."""

    def test_transaction_count(self, manomano_transactions: list[NormalizedTransaction]) -> None:
        """1 ORDER + 1 REFUND = 2 transactions."""
        sales = [t for t in manomano_transactions if t.type == "sale"]
        refunds = [t for t in manomano_transactions if t.type == "refund"]
        assert len(sales) == 1
        assert len(refunds) == 1

    def test_refund_type_correct(self, manomano_refund: NormalizedTransaction) -> None:
        """Type REFUND correctement parsé en type='refund'."""
        assert manomano_refund.type == "refund"

    def test_refund_amounts_positive(self, manomano_refund: NormalizedTransaction) -> None:
        """Montants abs appliqué par le parser."""
        assert manomano_refund.amount_ttc == 120.00
        assert manomano_refund.amount_ht == 100.00
        assert manomano_refund.amount_tva == 20.00

    def test_refund_reference(self, manomano_refund: NormalizedTransaction) -> None:
        """Même référence que la vente."""
        assert manomano_refund.reference == "MR001"

    def test_refund_channel(self, manomano_refund: NormalizedTransaction) -> None:
        """Canal = manomano."""
        assert manomano_refund.channel == "manomano"


class TestManoManoRefundEntries:
    """Écritures de vente et commission marketplace pour refund ManoMano."""

    def test_sale_entries_inversees(
        self,
        manomano_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Écritures vente refund inversées : 707 D, 4457 D, 411 C."""
        entries = generate_sale_entries(manomano_refund, sample_config)

        entry_411 = [e for e in entries if e.account == "411MANO"]
        entry_707 = [e for e in entries if e.account.startswith("707")]
        entry_4457 = [e for e in entries if e.account.startswith("4457")]

        assert len(entry_411) == 1
        assert len(entry_707) == 1
        assert len(entry_4457) == 1

        # 411 au crédit
        assert entry_411[0].credit > 0
        assert entry_411[0].debit == 0.0

        # 707 au débit
        assert entry_707[0].debit > 0
        assert entry_707[0].credit == 0.0

        # 4457 au débit
        assert entry_4457[0].debit > 0
        assert entry_4457[0].credit == 0.0

    def test_sale_entries_balance(
        self,
        manomano_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance vérifiée sur les écritures de vente refund."""
        entries = generate_sale_entries(manomano_refund, sample_config)
        verify_balance(entries)

    def test_sale_entries_entry_type(
        self,
        manomano_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """entry_type = 'refund' sur les écritures de vente."""
        entries = generate_sale_entries(manomano_refund, sample_config)
        for e in entries:
            assert e.entry_type == "refund"

    def test_commission_marketplace_refund(
        self,
        manomano_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Écritures commission marketplace refund : 401 D, 411 C (commission_ttc > 0)."""
        entries = generate_marketplace_commission(manomano_refund, sample_config)

        assert len(entries) == 2

        entry_401 = [e for e in entries if e.account == "FMANO"]
        entry_411 = [e for e in entries if e.account == "411MANO"]

        assert len(entry_401) == 1
        assert len(entry_411) == 1

        # commission_ttc = 18 (positive → marketplace rembourse la commission)
        # 401 au débit (fournisseur débité)
        assert entry_401[0].debit == 18.00
        assert entry_401[0].credit == 0.0

        # 411 au crédit (client crédité)
        assert entry_411[0].credit == 18.00
        assert entry_411[0].debit == 0.0

    def test_commission_balance(
        self,
        manomano_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance vérifiée sur les écritures de commission."""
        entries = generate_marketplace_commission(manomano_refund, sample_config)
        verify_balance(entries)

    def test_piece_number_et_lettrage(
        self,
        manomano_refund: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """piece_number et lettrage = référence commande d'origine."""
        sale_entries = generate_sale_entries(manomano_refund, sample_config)
        commission_entries = generate_marketplace_commission(manomano_refund, sample_config)

        for e in sale_entries + commission_entries:
            assert e.piece_number == "MR001"
            assert e.lettrage == "MR001"
