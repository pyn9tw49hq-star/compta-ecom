"""Tests pour engine/sale_entries.py — écritures de vente et d'avoir."""

from __future__ import annotations

import datetime

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.sale_entries import generate_sale_entries
from compta_ecom.models import NormalizedTransaction


def _make_transaction(**overrides: object) -> NormalizedTransaction:
    """Helper pour construire une NormalizedTransaction avec des valeurs par défaut."""
    defaults: dict[str, object] = {
        "reference": "#1118",
        "channel": "shopify",
        "date": datetime.date(2024, 1, 15),
        "type": "sale",
        "amount_ht": 100.0,
        "amount_tva": 20.0,
        "amount_ttc": 120.0,
        "shipping_ht": 0.0,
        "shipping_tva": 0.0,
        "tva_rate": 20.0,
        "country_code": "250",
        "commission_ttc": 0.0,
        "commission_ht": 0.0,
        "net_amount": 120.0,
        "payout_date": None,
        "payout_reference": None,
        "payment_method": None,
        "special_type": None,
    }
    defaults.update(overrides)
    return NormalizedTransaction(**defaults)  # type: ignore[arg-type]


class TestSaleEntriesNominal:
    """Vente nominale FR TVA 20%."""

    def test_nominal_sale_3_lines(self, sample_config: AppConfig) -> None:
        """Vente nominale: 3 lignes — 411 D=120, 707 C=100, 4457 C=20."""
        tx = _make_transaction()
        entries = generate_sale_entries(tx, sample_config)

        assert len(entries) == 3

        # 411 débit TTC
        assert entries[0].account == "411SHOPIFY"
        assert entries[0].debit == 120.0
        assert entries[0].credit == 0.0

        # 707 crédit HT
        assert entries[1].account == "70701250"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 100.0

        # 4457 crédit TVA
        assert entries[2].account == "4457250"
        assert entries[2].debit == 0.0
        assert entries[2].credit == 20.0

    def test_nominal_balance(self, sample_config: AppConfig) -> None:
        """Équilibre débit/crédit."""
        tx = _make_transaction()
        entries = generate_sale_entries(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )


class TestSaleEntriesWithShipping:
    """Ventes avec frais de port."""

    def test_shipping_included_in_ht_tva(self, sample_config: AppConfig) -> None:
        """HT = amount_ht + shipping_ht, TVA = amount_tva + shipping_tva."""
        tx = _make_transaction(
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=132.0,
            shipping_ht=10.0,
            shipping_tva=2.0,
        )
        entries = generate_sale_entries(tx, sample_config)

        assert entries[1].credit == 110.0  # 707: 100 + 10
        assert entries[2].credit == 22.0  # 4457: 20 + 2
        assert entries[0].debit == 132.0  # 411: TTC

    def test_shipping_only_order(self, sample_config: AppConfig) -> None:
        """amount_ht=0, shipping_ht=15 → HT=15."""
        tx = _make_transaction(
            amount_ht=0.0,
            amount_tva=0.0,
            amount_ttc=18.0,
            shipping_ht=15.0,
            shipping_tva=3.0,
        )
        entries = generate_sale_entries(tx, sample_config)

        assert entries[1].credit == 15.0  # 707: shipping_ht seul
        assert entries[2].credit == 3.0  # 4457: shipping_tva seul
        assert entries[0].debit == 18.0


class TestSaleEntriesZeroVAT:
    """TVA = 0 (DOM-TOM)."""

    def test_zero_vat_2_lines(self, sample_config: AppConfig) -> None:
        """TVA=0 → 2 lignes seulement (411 + 707), pas de 4457."""
        tx = _make_transaction(
            amount_ht=100.0,
            amount_tva=0.0,
            amount_ttc=100.0,
            shipping_ht=0.0,
            shipping_tva=0.0,
            country_code="974",
        )
        entries = generate_sale_entries(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "411SHOPIFY"
        assert entries[1].account == "70701974"

    def test_mixed_vat_shipping_only(self, sample_config: AppConfig) -> None:
        """amount_tva=0, shipping_tva=0.50 → 3 lignes, 4457 C=0.50."""
        tx = _make_transaction(
            amount_ht=50.0,
            amount_tva=0.0,
            amount_ttc=50.50,
            shipping_ht=0.0,
            shipping_tva=0.50,
        )
        entries = generate_sale_entries(tx, sample_config)

        assert len(entries) == 3
        assert entries[2].account == "4457250"
        assert entries[2].credit == 0.50


class TestRefundEntries:
    """Écritures d'avoir (refund)."""

    def test_refund_inverted(self, sample_config: AppConfig) -> None:
        """Refund: 707+4457 débit, 411 crédit — sens inversé."""
        tx = _make_transaction(type="refund")
        entries = generate_sale_entries(tx, sample_config)

        assert len(entries) == 3

        # 411 crédit TTC
        assert entries[0].account == "411SHOPIFY"
        assert entries[0].debit == 0.0
        assert entries[0].credit == 120.0

        # 707 débit HT
        assert entries[1].account == "70701250"
        assert entries[1].debit == 100.0
        assert entries[1].credit == 0.0

        # 4457 débit TVA
        assert entries[2].account == "4457250"
        assert entries[2].debit == 20.0
        assert entries[2].credit == 0.0

    def test_refund_with_shipping(self, sample_config: AppConfig) -> None:
        """Avoir avec shipping: shipping inversé aussi."""
        tx = _make_transaction(
            type="refund",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=132.0,
            shipping_ht=10.0,
            shipping_tva=2.0,
        )
        entries = generate_sale_entries(tx, sample_config)

        assert entries[0].credit == 132.0  # 411
        assert entries[1].debit == 110.0  # 707: 100+10
        assert entries[2].debit == 22.0  # 4457: 20+2

    def test_refund_balance(self, sample_config: AppConfig) -> None:
        """Équilibre débit/crédit sur refund."""
        tx = _make_transaction(type="refund")
        entries = generate_sale_entries(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )


class TestEntryMetadata:
    """Vérification des métadonnées d'écriture."""

    def test_entry_type_sale(self, sample_config: AppConfig) -> None:
        """entry_type='sale' pour ventes."""
        tx = _make_transaction(type="sale")
        entries = generate_sale_entries(tx, sample_config)
        for e in entries:
            assert e.entry_type == "sale"

    def test_entry_type_refund(self, sample_config: AppConfig) -> None:
        """entry_type='refund' pour avoirs."""
        tx = _make_transaction(type="refund")
        entries = generate_sale_entries(tx, sample_config)
        for e in entries:
            assert e.entry_type == "refund"

    def test_label_sale(self, sample_config: AppConfig) -> None:
        """Libellé vente: 'Vente #1118 Shopify'."""
        tx = _make_transaction(reference="#1118", channel="shopify")
        entries = generate_sale_entries(tx, sample_config)
        assert entries[0].label == "Vente #1118 Shopify"

    def test_label_refund_multiword(self, sample_config: AppConfig) -> None:
        """Libellé avoir avec canal multi-mots: 'leroy_merlin' → 'Leroy Merlin'."""
        config = AppConfig(
            clients={
                **sample_config.clients,
                "leroy_merlin": "411LEROY",
            },
            fournisseurs=sample_config.fournisseurs,
            psp=sample_config.psp,
            transit=sample_config.transit,
            banque=sample_config.banque,
            comptes_speciaux=sample_config.comptes_speciaux,
            comptes_vente_prefix=sample_config.comptes_vente_prefix,
            canal_codes={
                **sample_config.canal_codes,
                "leroy_merlin": "03",
            },
            comptes_tva_prefix=sample_config.comptes_tva_prefix,
            vat_table=sample_config.vat_table,
            alpha2_to_numeric=sample_config.alpha2_to_numeric,
            channels=sample_config.channels,
        )
        tx = _make_transaction(
            reference="#1200", channel="leroy_merlin", type="refund"
        )
        entries = generate_sale_entries(tx, config)
        assert entries[0].label == "Avoir #1200 Leroy Merlin"

    def test_journal_vente(self, sample_config: AppConfig) -> None:
        """Journal = 'VE'."""
        tx = _make_transaction()
        entries = generate_sale_entries(tx, sample_config)
        for e in entries:
            assert e.journal == "VE"

    def test_piece_number_and_lettrage(self, sample_config: AppConfig) -> None:
        """piece_number et lettrage = reference."""
        tx = _make_transaction(reference="#9999")
        entries = generate_sale_entries(tx, sample_config)
        for e in entries:
            assert e.piece_number == "#9999"
            assert e.lettrage == "#9999"

    def test_date(self, sample_config: AppConfig) -> None:
        """Date = date de la transaction."""
        tx = _make_transaction(date=datetime.date(2024, 3, 1))
        entries = generate_sale_entries(tx, sample_config)
        for e in entries:
            assert e.date == datetime.date(2024, 3, 1)

    def test_dynamic_accounts(self, sample_config: AppConfig) -> None:
        """Comptes dynamiques: 70701250, 4457250, 411SHOPIFY."""
        tx = _make_transaction()
        entries = generate_sale_entries(tx, sample_config)
        assert entries[0].account == "411SHOPIFY"
        assert entries[1].account == "70701250"
        assert entries[2].account == "4457250"


class TestMarketplaceTransaction:
    """Écritures de vente pour transaction marketplace (AC17)."""

    def test_manomano_sale_entries(self, sample_config: AppConfig) -> None:
        """Transaction ManoMano → comptes 411MANO, 70702250, 4457250."""
        tx = _make_transaction(
            channel="manomano",
            payment_method=None,
            type="sale",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=120.0,
            shipping_ht=0.0,
            shipping_tva=0.0,
        )
        entries = generate_sale_entries(tx, sample_config)

        assert len(entries) == 3

        # 411MANO débit TTC
        assert entries[0].account == "411MANO"
        assert entries[0].debit == 120.0
        assert entries[0].credit == 0.0

        # 70702250 crédit HT (canal_code "02" pour manomano)
        assert entries[1].account == "70702250"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 100.0

        # 4457250 crédit TVA
        assert entries[2].account == "4457250"
        assert entries[2].debit == 0.0
        assert entries[2].credit == 20.0

    def test_manomano_payment_method_none_ok(self, sample_config: AppConfig) -> None:
        """payment_method=None ne pose aucun problème dans sale_entries."""
        tx = _make_transaction(
            channel="manomano",
            payment_method=None,
        )
        entries = generate_sale_entries(tx, sample_config)
        assert len(entries) == 3

    def test_manomano_balance(self, sample_config: AppConfig) -> None:
        """Équilibre débit/crédit pour transaction marketplace."""
        tx = _make_transaction(
            channel="manomano",
            payment_method=None,
        )
        entries = generate_sale_entries(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )


class TestChannelErrors:
    """Erreurs de configuration canal."""

    def test_unknown_channel_raises_keyerror(self, sample_config: AppConfig) -> None:
        """Channel inconnu dans config.canal_codes → KeyError."""
        tx = _make_transaction(channel="amazon")
        with pytest.raises(KeyError):
            generate_sale_entries(tx, sample_config)
