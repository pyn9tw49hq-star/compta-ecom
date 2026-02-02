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
        """Vente nominale sans frais de port: 3 lignes — 411 D=120, 707 C=100, 4457 C=20."""
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
    """Ventes avec frais de port isolés sur compte 7085."""

    def test_shipping_separated_4_lines(self, sample_config: AppConfig) -> None:
        """Shipping isolé: 4 lignes — 411, 707 (produit), 7085 (port), 4457 (TVA combinée)."""
        tx = _make_transaction(
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=132.0,
            shipping_ht=10.0,
            shipping_tva=2.0,
        )
        entries = generate_sale_entries(tx, sample_config)

        assert len(entries) == 4

        assert entries[0].debit == 132.0  # 411: TTC
        assert entries[1].account == "70701250"
        assert entries[1].credit == 100.0  # 707: produit HT seul
        assert entries[2].account == "70850100"  # 7085 + canal 01 + zone 00 (France)
        assert entries[2].credit == 10.0  # frais de port HT
        assert entries[3].credit == 22.0  # 4457: TVA combinée (20 + 2)

    def test_shipping_only_order(self, sample_config: AppConfig) -> None:
        """amount_ht=0, shipping_ht=15 → 4 lignes, 707 C=0, 7085 C=15."""
        tx = _make_transaction(
            amount_ht=0.0,
            amount_tva=0.0,
            amount_ttc=18.0,
            shipping_ht=15.0,
            shipping_tva=3.0,
        )
        entries = generate_sale_entries(tx, sample_config)

        assert len(entries) == 4
        assert entries[1].credit == 0.0  # 707: produit HT = 0
        assert entries[2].account == "70850100"  # 7085 France
        assert entries[2].credit == 15.0  # frais de port HT
        assert entries[3].credit == 3.0  # 4457: TVA shipping seule
        assert entries[0].debit == 18.0

    def test_shipping_balance(self, sample_config: AppConfig) -> None:
        """Équilibre débit/crédit avec frais de port."""
        tx = _make_transaction(
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=132.0,
            shipping_ht=10.0,
            shipping_tva=2.0,
        )
        entries = generate_sale_entries(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )

    def test_no_shipping_no_7085_line(self, sample_config: AppConfig) -> None:
        """shipping_ht=0 → pas de ligne 7085."""
        tx = _make_transaction(shipping_ht=0.0, shipping_tva=0.0)
        entries = generate_sale_entries(tx, sample_config)
        accounts = [e.account for e in entries]
        assert not any(a.startswith("7085") for a in accounts)


class TestShippingZones:
    """Comptes 7085 par zone géographique."""

    def test_shipping_france(self, sample_config: AppConfig) -> None:
        """France (250) → zone 00 → compte 70850100."""
        tx = _make_transaction(
            country_code="250", shipping_ht=5.0, shipping_tva=1.0, amount_ttc=126.0
        )
        entries = generate_sale_entries(tx, sample_config)
        port_entry = [e for e in entries if e.account.startswith("7085")]
        assert len(port_entry) == 1
        assert port_entry[0].account == "70850100"  # shopify + france

    def test_shipping_eu(self, sample_config: AppConfig) -> None:
        """Allemagne (276, dans vat_table) → zone 02 → compte 70850102."""
        config = AppConfig(
            clients=sample_config.clients,
            fournisseurs=sample_config.fournisseurs,
            psp=sample_config.psp,
            transit=sample_config.transit,
            banque=sample_config.banque,
            comptes_speciaux=sample_config.comptes_speciaux,
            comptes_vente_prefix=sample_config.comptes_vente_prefix,
            canal_codes=sample_config.canal_codes,
            comptes_tva_prefix=sample_config.comptes_tva_prefix,
            comptes_port_prefix=sample_config.comptes_port_prefix,
            zones_port=sample_config.zones_port,
            vat_table={
                **sample_config.vat_table,
                "276": {"name": "Allemagne", "rate": 19.0, "alpha2": "DE"},
            },
            alpha2_to_numeric={**sample_config.alpha2_to_numeric, "DE": "276"},
            channels=sample_config.channels,
        )
        tx = _make_transaction(
            country_code="276",
            tva_rate=19.0,
            amount_ht=100.0,
            amount_tva=19.0,
            amount_ttc=124.95,
            shipping_ht=5.0,
            shipping_tva=0.95,
        )
        entries = generate_sale_entries(tx, config)
        port_entry = [e for e in entries if e.account.startswith("7085")]
        assert len(port_entry) == 1
        assert port_entry[0].account == "70850102"  # shopify + UE

    def test_shipping_hors_ue(self, sample_config: AppConfig) -> None:
        """Code pays inconnu (840 = USA, pas dans vat_table) → zone 01 → compte 70850101."""
        tx = _make_transaction(
            country_code="840",
            tva_rate=0.0,
            amount_ht=100.0,
            amount_tva=0.0,
            amount_ttc=105.0,
            shipping_ht=5.0,
            shipping_tva=0.0,
        )
        entries = generate_sale_entries(tx, sample_config)
        port_entry = [e for e in entries if e.account.startswith("7085")]
        assert len(port_entry) == 1
        assert port_entry[0].account == "70850101"  # shopify + hors UE

    def test_shipping_dom_tom(self, sample_config: AppConfig) -> None:
        """DOM-TOM (974) → zone hors_ue → compte 70850101."""
        tx = _make_transaction(
            country_code="974",
            tva_rate=0.0,
            amount_ht=100.0,
            amount_tva=0.0,
            amount_ttc=105.0,
            shipping_ht=5.0,
            shipping_tva=0.0,
        )
        entries = generate_sale_entries(tx, sample_config)
        port_entry = [e for e in entries if e.account.startswith("7085")]
        assert len(port_entry) == 1
        assert port_entry[0].account == "70850101"  # shopify + hors UE

    def test_shipping_manomano_france(self, sample_config: AppConfig) -> None:
        """ManoMano France → compte 70850200 (canal 02 + zone 00)."""
        tx = _make_transaction(
            channel="manomano",
            country_code="250",
            amount_ht=80.0,
            amount_tva=16.0,
            amount_ttc=101.0,
            shipping_ht=5.0,
            shipping_tva=0.0,
        )
        entries = generate_sale_entries(tx, sample_config)
        port_entry = [e for e in entries if e.account.startswith("7085")]
        assert len(port_entry) == 1
        assert port_entry[0].account == "70850200"  # manomano + france


class TestSaleEntriesZeroVAT:
    """TVA = 0 (DOM-TOM)."""

    def test_zero_vat_2_lines(self, sample_config: AppConfig) -> None:
        """TVA=0 et pas de shipping → 2 lignes seulement (411 + 707), pas de 4457."""
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
        """amount_tva=0, shipping_tva=0.50, shipping_ht=0 → 3 lignes, 4457 C=0.50."""
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
        """Avoir avec shipping: 4 lignes, shipping inversé aussi."""
        tx = _make_transaction(
            type="refund",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=132.0,
            shipping_ht=10.0,
            shipping_tva=2.0,
        )
        entries = generate_sale_entries(tx, sample_config)

        assert len(entries) == 4
        assert entries[0].credit == 132.0  # 411
        assert entries[1].debit == 100.0  # 707: produit seul
        assert entries[2].account == "70850100"  # 7085 France
        assert entries[2].debit == 10.0  # port inversé
        assert entries[3].debit == 22.0  # 4457: 20+2

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
            comptes_port_prefix=sample_config.comptes_port_prefix,
            zones_port=sample_config.zones_port,
            vat_table=sample_config.vat_table,
            alpha2_to_numeric=sample_config.alpha2_to_numeric,
            channels=sample_config.channels,
        )
        tx = _make_transaction(
            reference="#1200", channel="leroy_merlin", type="refund"
        )
        entries = generate_sale_entries(tx, config)
        assert entries[0].label == "Avoir #1200 Leroy Merlin"

    @pytest.mark.parametrize("channel,expected_journal", [
        ("shopify", "VE"),
        ("manomano", "MM"),
        ("decathlon", "DEC"),
        ("leroy_merlin", "LM"),
    ])
    def test_journal_per_channel(self, sample_config: AppConfig, channel: str, expected_journal: str) -> None:
        """Journal de vente = code journal du canal."""
        tx = _make_transaction(channel=channel)
        entries = generate_sale_entries(tx, sample_config)
        for e in entries:
            assert e.journal == expected_journal

    def test_piece_number_and_lettrage(self, sample_config: AppConfig) -> None:
        """piece_number = reference pour tous ; lettrage = reference uniquement pour 411."""
        tx = _make_transaction(reference="#9999")
        entries = generate_sale_entries(tx, sample_config)
        for e in entries:
            assert e.piece_number == "#9999"
            if e.account.startswith("411"):
                assert e.lettrage == "#9999"
            else:
                assert e.lettrage == ""

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
