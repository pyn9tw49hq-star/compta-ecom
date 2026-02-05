"""Tests d'intégration E2E — Contrôles sur refunds + orchestration multi-canal."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.controls.matching_checker import MatchingChecker
from compta_ecom.controls.vat_checker import VatChecker
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.engine.marketplace_entries import generate_marketplace_commission
from compta_ecom.engine.sale_entries import generate_sale_entries
from compta_ecom.engine.settlement_entries import generate_settlement_entries
from compta_ecom.models import AccountingEntry, NormalizedTransaction
from compta_ecom.parsers.manomano import ManoManoParser
from compta_ecom.parsers.mirakl import MiraklParser
from compta_ecom.parsers.shopify import ShopifyParser

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures — parse all channels
# ---------------------------------------------------------------------------


@pytest.fixture()
def shopify_transactions(sample_config: AppConfig) -> list[NormalizedTransaction]:
    """Parse Shopify refund fixtures."""
    parser = ShopifyParser()
    files = {
        "sales": FIXTURES_DIR / "shopify" / "ventes_refund.csv",
        "transactions": FIXTURES_DIR / "shopify" / "transactions_refund.csv",
        "payouts": FIXTURES_DIR / "shopify" / "versements_refund.csv",
    }
    result = parser.parse(files, sample_config)
    return result.transactions


@pytest.fixture()
def manomano_transactions(sample_config: AppConfig) -> list[NormalizedTransaction]:
    """Parse ManoMano refund fixtures."""
    parser = ManoManoParser()
    files = {
        "ca": FIXTURES_DIR / "manomano" / "ca_refund.csv",
        "payouts": FIXTURES_DIR / "manomano" / "versements_manomano_refund.csv",
    }
    result = parser.parse(files, sample_config)
    return result.transactions


@pytest.fixture()
def mirakl_transactions(sample_config: AppConfig) -> list[NormalizedTransaction]:
    """Parse Mirakl (Décathlon) refund fixtures."""
    parser = MiraklParser(channel="decathlon")
    files = {"data": FIXTURES_DIR / "decathlon" / "decathlon_data_refund.csv"}
    result = parser.parse(files, sample_config)
    return result.transactions


@pytest.fixture()
def all_transactions(
    shopify_transactions: list[NormalizedTransaction],
    manomano_transactions: list[NormalizedTransaction],
    mirakl_transactions: list[NormalizedTransaction],
) -> list[NormalizedTransaction]:
    """Toutes les transactions des 3 canaux combinées."""
    return shopify_transactions + manomano_transactions + mirakl_transactions


# ---------------------------------------------------------------------------
# VatChecker sur refunds
# ---------------------------------------------------------------------------


class TestVatCheckerOnRefunds:
    """VatChecker s'applique identiquement aux refunds."""

    def test_vat_checker_on_shopify_refunds(
        self,
        shopify_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """VatChecker sur les refunds Shopify — mêmes règles que les ventes."""
        refunds = [t for t in shopify_transactions if t.type == "refund"]
        anomalies = VatChecker.check(refunds, sample_config)
        # Les fixtures sont cohérentes → pas d'anomalie TVA
        vat_anomalies = [a for a in anomalies if a.type in ("tva_mismatch", "tva_amount_mismatch", "ttc_coherence_mismatch")]
        assert len(vat_anomalies) == 0

    def test_vat_checker_on_manomano_refunds(
        self,
        manomano_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """VatChecker sur les refunds ManoMano."""
        refunds = [t for t in manomano_transactions if t.type == "refund"]
        anomalies = VatChecker.check(refunds, sample_config)
        vat_anomalies = [a for a in anomalies if a.type in ("tva_mismatch", "tva_amount_mismatch", "ttc_coherence_mismatch")]
        assert len(vat_anomalies) == 0

    def test_vat_checker_on_mirakl_refunds(
        self,
        mirakl_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """VatChecker sur les refunds Mirakl."""
        refunds = [t for t in mirakl_transactions if t.type == "refund"]
        anomalies = VatChecker.check(refunds, sample_config)
        vat_anomalies = [a for a in anomalies if a.type in ("tva_mismatch", "tva_amount_mismatch", "ttc_coherence_mismatch")]
        assert len(vat_anomalies) == 0


# ---------------------------------------------------------------------------
# MatchingChecker sur refunds
# ---------------------------------------------------------------------------


class TestMatchingCheckerOnRefunds:
    """MatchingChecker : orphan_refund et cohérence montant."""

    def test_refund_with_matching_sale_no_orphan(
        self,
        shopify_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Refund avec vente correspondante → pas d'orphan_refund."""
        # Shopify fixtures: R001 et R002 ont sale + refund (même référence)
        anomalies = MatchingChecker.check(shopify_transactions, sample_config)
        orphan_refunds = [a for a in anomalies if a.type == "orphan_refund"]
        assert len(orphan_refunds) == 0

    def test_orphan_refund_detected(
        self,
        shopify_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Refund sans vente correspondante → orphan_refund détecté."""
        # Ajouter un refund avec une référence inconnue
        orphan = NormalizedTransaction(
            reference="#ORPHAN999",
            channel="shopify",
            date=datetime.date(2026, 1, 20),
            type="refund",
            amount_ht=50.00,
            amount_tva=10.00,
            amount_ttc=60.00,
            shipping_ht=0.0,
            shipping_tva=0.0,
            tva_rate=20.0,
            country_code="250",
            commission_ttc=-2.00,
            commission_ht=0.0,
            net_amount=-58.00,
            payout_date=None,
            payout_reference=None,
            payment_method="card",
            special_type=None,
        )
        transactions_with_orphan = list(shopify_transactions) + [orphan]
        anomalies = MatchingChecker.check(transactions_with_orphan, sample_config)
        orphan_refunds = [a for a in anomalies if a.type == "orphan_refund"]
        assert len(orphan_refunds) == 1
        assert orphan_refunds[0].reference == "#ORPHAN999"

    def test_amount_coherence_shopify_refund(
        self,
        shopify_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Cohérence montant sur refunds Shopify : amount_ttc = abs(commission + net)."""
        refunds = [t for t in shopify_transactions if t.type == "refund"]
        anomalies = MatchingChecker.check(refunds, sample_config)
        amount_mismatches = [a for a in anomalies if a.type == "amount_mismatch"]
        assert len(amount_mismatches) == 0


# ---------------------------------------------------------------------------
# Orchestration multi-canal refund
# ---------------------------------------------------------------------------


class TestMultiChannelRefundOrchestration:
    """Test unique exécutant parsing + engine + controls sur les 3 canaux."""

    def test_all_channels_parsed(
        self,
        all_transactions: list[NormalizedTransaction],
    ) -> None:
        """Les 3 canaux produisent des transactions."""
        channels = {t.channel for t in all_transactions}
        assert "shopify" in channels
        assert "manomano" in channels
        assert "decathlon" in channels

    def test_total_transaction_count(
        self,
        all_transactions: list[NormalizedTransaction],
    ) -> None:
        """Nombre total de transactions attendu."""
        # Shopify: 3 sales + 2 refunds = 5
        # ManoMano: 1 sale + 1 refund = 2
        # Mirakl: 1 sale + 1 refund = 2
        # Total = 9
        assert len(all_transactions) == 9

    def test_refund_count_by_channel(
        self,
        all_transactions: list[NormalizedTransaction],
    ) -> None:
        """Nombre de refunds par canal."""
        refunds = [t for t in all_transactions if t.type == "refund"]
        shopify_refunds = [r for r in refunds if r.channel == "shopify"]
        manomano_refunds = [r for r in refunds if r.channel == "manomano"]
        decathlon_refunds = [r for r in refunds if r.channel == "decathlon"]

        assert len(shopify_refunds) == 2
        assert len(manomano_refunds) == 1
        assert len(decathlon_refunds) == 1

    def test_all_entries_generated_and_balanced(
        self,
        all_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Toutes les écritures générées sont équilibrées par jeu."""
        all_entries: list[AccountingEntry] = []

        for tx in all_transactions:
            # Sale/refund entries
            sale_entries = generate_sale_entries(tx, sample_config)
            verify_balance(sale_entries)
            all_entries.extend(sale_entries)

            # Settlement entries (Shopify only — requires payment_method)
            if tx.payment_method is not None:
                settlement_entries = generate_settlement_entries(tx, sample_config)
                if settlement_entries:
                    verify_balance(settlement_entries)
                    all_entries.extend(settlement_entries)

            # Marketplace commission entries (ManoMano, Décathlon)
            if tx.channel in ("manomano", "decathlon") and tx.special_type is None:
                commission_entries = generate_marketplace_commission(tx, sample_config)
                if commission_entries:
                    verify_balance(commission_entries)
                    all_entries.extend(commission_entries)

        # Hardcoded expected entry counts — catches silent regressions (QA-003)
        # Shipping isolation adds 1 extra 7085 line per transaction with shipping_ht > 0
        assert len(all_entries) == 51

        # Refund-type entries include 7085 lines for refunds with shipping
        refund_entries = [e for e in all_entries if e.entry_type == "refund"]
        assert len(refund_entries) == 13

    def test_no_unexpected_anomalies_on_coherent_refunds(
        self,
        all_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Aucune anomalie inattendue pour les refunds cohérents."""
        anomalies = VatChecker.check(all_transactions, sample_config)
        vat_errors = [a for a in anomalies if a.severity == "error"]
        assert len(vat_errors) == 0

    def test_orphan_refund_from_mirakl(
        self,
        all_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Le refund Mirakl (DECR002) est un orphan_refund intentionnel."""
        # DECR002 est un refund sans vente correspondante au même ref
        # (sale = DECR001, refund = DECR002 — refs différentes car Mirakl agrège par numéro)
        anomalies = MatchingChecker.check(all_transactions, sample_config)
        orphan_refunds = [a for a in anomalies if a.type == "orphan_refund"]
        orphan_refs = {a.reference for a in orphan_refunds}
        assert "DECR002" in orphan_refs

    def test_channels_independent(
        self,
        all_transactions: list[NormalizedTransaction],
        sample_config: AppConfig,
    ) -> None:
        """Les écritures de chaque canal sont indépendantes (comptes distincts)."""
        channel_accounts: dict[str, set[str]] = {}

        for tx in all_transactions:
            if tx.type != "refund":
                continue
            entries = generate_sale_entries(tx, sample_config)
            client_accounts = {e.account for e in entries if e.account.startswith("411") or e.account == "CDECATHLON"}
            channel_accounts.setdefault(tx.channel, set()).update(client_accounts)

        # Chaque canal utilise un compte client 411 distinct
        assert channel_accounts.get("shopify") == {"411SHOPIFY"}
        assert channel_accounts.get("manomano") == {"411MANO"}
        assert channel_accounts.get("decathlon") == {"CDECATHLON"}
