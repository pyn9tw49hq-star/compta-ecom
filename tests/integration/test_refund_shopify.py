"""Tests d'intégration E2E — Shopify refund (commission restituée et non restituée)."""

from __future__ import annotations

from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.engine.sale_entries import generate_sale_entries
from compta_ecom.engine.settlement_entries import generate_settlement_entries
from compta_ecom.models import NormalizedTransaction
from compta_ecom.parsers.shopify import ShopifyParser

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "shopify"


@pytest.fixture()
def shopify_parse_result(sample_config: AppConfig):
    """Parse les fixtures Shopify refund → ParseResult."""
    parser = ShopifyParser()
    files = {
        "sales": FIXTURES_DIR / "ventes_refund.csv",
        "transactions": FIXTURES_DIR / "transactions_refund.csv",
        "payouts": FIXTURES_DIR / "versements_refund.csv",
    }
    return parser.parse(files, sample_config)


@pytest.fixture()
def shopify_transactions(shopify_parse_result) -> list[NormalizedTransaction]:  # type: ignore[no-untyped-def]
    """Toutes les transactions parsées."""
    return shopify_parse_result.transactions


@pytest.fixture()
def refund_commission_restituee(
    shopify_transactions: list[NormalizedTransaction],
) -> NormalizedTransaction:
    """Refund Shopify avec commission PSP restituée (Fee < 0 → commission_ttc < 0)."""
    matches = [t for t in shopify_transactions if t.type == "refund" and t.commission_ttc < 0]
    assert len(matches) == 1, f"Expected 1 refund with commission_ttc < 0, got {len(matches)}"
    return matches[0]


@pytest.fixture()
def refund_commission_non_restituee(
    shopify_transactions: list[NormalizedTransaction],
) -> NormalizedTransaction:
    """Refund Shopify avec commission PSP non restituée (Fee > 0 → commission_ttc > 0)."""
    matches = [t for t in shopify_transactions if t.type == "refund" and t.commission_ttc > 0]
    assert len(matches) == 1, f"Expected 1 refund with commission_ttc > 0, got {len(matches)}"
    return matches[0]


class TestShopifyRefundParsing:
    """Vérification du parsing correct des fixtures Shopify refund."""

    def test_transaction_count(self, shopify_transactions: list[NormalizedTransaction]) -> None:
        """3 ventes + 2 refunds = 5 transactions (R003 orphan sans charge → sale sans PSP)."""
        sales = [t for t in shopify_transactions if t.type == "sale"]
        refunds = [t for t in shopify_transactions if t.type == "refund"]
        assert len(sales) == 3
        assert len(refunds) == 2

    def test_refund_type(self, shopify_transactions: list[NormalizedTransaction]) -> None:
        """Les transactions refund ont bien type='refund'."""
        refunds = [t for t in shopify_transactions if t.type == "refund"]
        for r in refunds:
            assert r.type == "refund"

    def test_refund_amounts_positive(self, shopify_transactions: list[NormalizedTransaction]) -> None:
        """Les montants des refunds sont positifs (abs appliqué par le parser)."""
        refunds = [t for t in shopify_transactions if t.type == "refund"]
        for r in refunds:
            assert r.amount_ttc > 0
            assert r.amount_ht > 0
            assert r.amount_tva > 0

    def test_refund_references(self, shopify_transactions: list[NormalizedTransaction]) -> None:
        """Les refunds portent la référence de la commande d'origine."""
        refunds = [t for t in shopify_transactions if t.type == "refund"]
        refs = {r.reference for r in refunds}
        assert refs == {"#R001", "#R002"}


class TestShopifyRefundCommissionRestituee:
    """Refund Shopify avec commission PSP restituée (Fee < 0)."""

    def test_sale_entries_inversees(
        self,
        refund_commission_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Écritures vente inversées : 707 D, 4457 D, 411 C."""
        entries = generate_sale_entries(refund_commission_restituee, sample_config)

        entry_411 = [e for e in entries if e.account == "411SHOPIFY"]
        entry_707 = [e for e in entries if e.account.startswith("707")]
        entry_4457 = [e for e in entries if e.account.startswith("4457")]

        assert len(entry_411) == 1
        assert len(entry_707) == 1
        assert len(entry_4457) == 1

        # 411 au crédit (dette client annulée)
        assert entry_411[0].credit > 0
        assert entry_411[0].debit == 0.0

        # 707 au débit (produit remboursé)
        assert entry_707[0].debit > 0
        assert entry_707[0].credit == 0.0

        # 4457 au débit (TVA remboursée)
        assert entry_4457[0].debit > 0
        assert entry_4457[0].credit == 0.0

    def test_sale_entries_balance(
        self,
        refund_commission_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance débit = crédit sur les écritures de vente refund."""
        entries = generate_sale_entries(refund_commission_restituee, sample_config)
        # verify_balance lève BalanceError si déséquilibre
        verify_balance(entries)

    def test_sale_entries_entry_type(
        self,
        refund_commission_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """entry_type = 'refund' sur les écritures de vente."""
        entries = generate_sale_entries(refund_commission_restituee, sample_config)
        for e in entries:
            assert e.entry_type == "refund"

    def test_settlement_entries_commission_restituee(
        self,
        refund_commission_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Settlement : PSP C, 627 C, 411 D — commission restituée."""
        entries = generate_settlement_entries(refund_commission_restituee, sample_config)

        entry_psp = [e for e in entries if e.account == "51150007"]
        entry_627 = [e for e in entries if e.account == "62700002"]
        entry_411 = [e for e in entries if e.account == "411SHOPIFY"]

        assert len(entry_psp) == 1
        assert len(entry_627) == 1
        assert len(entry_411) == 1

        # PSP au crédit (PSP rembourse le net)
        assert entry_psp[0].credit > 0
        assert entry_psp[0].debit == 0.0

        # 627 au crédit (PSP rembourse la commission)
        assert entry_627[0].credit > 0
        assert entry_627[0].debit == 0.0

        # 411 au débit (contrepartie client)
        assert entry_411[0].debit > 0
        assert entry_411[0].credit == 0.0

        # entry_type assertions on settlement entries (QA-002)
        assert entry_psp[0].entry_type == "settlement"
        assert entry_627[0].entry_type == "commission"
        assert entry_411[0].entry_type == "settlement"

    def test_settlement_balance(
        self,
        refund_commission_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance vérifiée sur les écritures settlement."""
        entries = generate_settlement_entries(refund_commission_restituee, sample_config)
        verify_balance(entries)

    def test_piece_number_et_lettrage(
        self,
        refund_commission_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """piece_number et lettrage = référence commande d'origine."""
        sale_entries = generate_sale_entries(refund_commission_restituee, sample_config)
        settlement_entries = generate_settlement_entries(refund_commission_restituee, sample_config)

        for e in sale_entries + settlement_entries:
            assert e.piece_number == "#R001"
            if e.account.startswith("411") or e.account.startswith("511"):
                assert e.lettrage == "#R001"


class TestShopifyRefundCommissionNonRestituee:
    """Refund Shopify avec commission PSP NON restituée (Fee > 0)."""

    def test_sale_entries_identiques(
        self,
        refund_commission_non_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Écritures vente toujours inversées, indépendant de la commission."""
        entries = generate_sale_entries(refund_commission_non_restituee, sample_config)

        entry_411 = [e for e in entries if e.account == "411SHOPIFY"]
        entry_707 = [e for e in entries if e.account.startswith("707")]
        entry_4457 = [e for e in entries if e.account.startswith("4457")]

        # Même schéma que commission restituée
        assert entry_411[0].credit > 0
        assert entry_707[0].debit > 0
        assert entry_4457[0].debit > 0

    def test_sale_entries_balance(
        self,
        refund_commission_non_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance vérifiée."""
        entries = generate_sale_entries(refund_commission_non_restituee, sample_config)
        verify_balance(entries)

    def test_settlement_commission_conservee(
        self,
        refund_commission_non_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Settlement : 627 D (commission conservée), PSP C, 411 D."""
        entries = generate_settlement_entries(refund_commission_non_restituee, sample_config)

        entry_psp = [e for e in entries if e.account == "51150007"]
        entry_627 = [e for e in entries if e.account == "62700002"]
        entry_411 = [e for e in entries if e.account == "411SHOPIFY"]

        assert len(entry_psp) == 1
        assert len(entry_627) == 1
        assert len(entry_411) == 1

        # PSP au crédit (PSP rembourse le net)
        assert entry_psp[0].credit > 0
        assert entry_psp[0].debit == 0.0

        # 627 au débit (commission conservée par le PSP)
        assert entry_627[0].debit > 0
        assert entry_627[0].credit == 0.0

        # 411 au débit (contrepartie client)
        assert entry_411[0].debit > 0
        assert entry_411[0].credit == 0.0

        # entry_type assertions on settlement entries (QA-002)
        assert entry_psp[0].entry_type == "settlement"
        assert entry_627[0].entry_type == "commission"
        assert entry_411[0].entry_type == "settlement"

    def test_settlement_balance(
        self,
        refund_commission_non_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance vérifiée."""
        entries = generate_settlement_entries(refund_commission_non_restituee, sample_config)
        verify_balance(entries)

    def test_settlement_amounts(
        self,
        refund_commission_non_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Vérification montants : PSP C = |net|, 627 D = commission, 411 D = |total_411|."""
        tx = refund_commission_non_restituee
        entries = generate_settlement_entries(tx, sample_config)

        entry_psp = [e for e in entries if e.account == "51150007"][0]
        entry_627 = [e for e in entries if e.account == "62700002"][0]
        entry_411 = [e for e in entries if e.account == "411SHOPIFY"][0]

        # Hardcoded expected values from fixture: #R002 Fee=2.10, Net=-62.10 (QA-004)
        assert entry_psp.credit == 62.10
        assert entry_627.debit == 2.10
        assert entry_411.debit == 60.00

    def test_piece_number_et_lettrage(
        self,
        refund_commission_non_restituee: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """piece_number et lettrage = référence commande d'origine."""
        sale_entries = generate_sale_entries(refund_commission_non_restituee, sample_config)
        settlement_entries = generate_settlement_entries(refund_commission_non_restituee, sample_config)

        for e in sale_entries + settlement_entries:
            assert e.piece_number == "#R002"
            if e.account.startswith("411") or e.account.startswith("511"):
                assert e.lettrage == "#R002"
