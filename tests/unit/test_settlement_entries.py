"""Tests pour engine/settlement_entries.py — écritures de règlement et commission."""

from __future__ import annotations

import datetime

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.settlement_entries import generate_settlement_entries
from compta_ecom.models import AccountingEntry, NormalizedTransaction


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
        "commission_ttc": 5.0,
        "commission_ht": 4.17,
        "net_amount": 95.0,
        "payout_date": None,
        "payout_reference": None,
        "payment_method": "card",
        "special_type": None,
    }
    defaults.update(overrides)
    return NormalizedTransaction(**defaults)  # type: ignore[arg-type]


def _assert_balance(entries: list[AccountingEntry]) -> None:
    """Vérifie l'équilibre débit/crédit."""
    total_d = round(sum(e.debit for e in entries), 2)
    total_c = round(sum(e.credit for e in entries), 2)
    assert total_d == total_c, f"Déséquilibre: D={total_d} C={total_c}"


class TestSettlementSaleNominal:
    """Vente nominale — 3 PSP (Stripe/card, PayPal, Klarna)."""

    def test_sale_stripe_3_lines(self, sample_config: AppConfig) -> None:
        """Stripe (card): PSP D=95, 627 D=5, 411 C=100, équilibre."""
        tx = _make_transaction(
            net_amount=95.0, commission_ttc=5.0, payment_method="card"
        )
        entries = generate_settlement_entries(tx, sample_config)

        assert len(entries) == 3

        # PSP 511 débit
        assert entries[0].account == "51150007"
        assert entries[0].debit == 95.0
        assert entries[0].credit == 0.0
        assert entries[0].entry_type == "settlement"

        # 627 commission débit
        assert entries[1].account == "62700002"
        assert entries[1].debit == 5.0
        assert entries[1].credit == 0.0
        assert entries[1].entry_type == "commission"

        # 411 client crédit
        assert entries[2].account == "411SHOPIFY"
        assert entries[2].debit == 0.0
        assert entries[2].credit == 100.0
        assert entries[2].entry_type == "settlement"

        _assert_balance(entries)

    def test_sale_paypal(self, sample_config: AppConfig) -> None:
        """PayPal: comptes 51150004/62700001."""
        tx = _make_transaction(
            net_amount=95.0, commission_ttc=5.0, payment_method="paypal"
        )
        entries = generate_settlement_entries(tx, sample_config)

        assert entries[0].account == "51150004"
        assert entries[1].account == "62700001"
        _assert_balance(entries)

    def test_sale_klarna(self, sample_config: AppConfig) -> None:
        """Klarna: comptes 51150011/62700003."""
        tx = _make_transaction(
            net_amount=95.0, commission_ttc=5.0, payment_method="klarna"
        )
        entries = generate_settlement_entries(tx, sample_config)

        assert entries[0].account == "51150011"
        assert entries[1].account == "62700003"
        _assert_balance(entries)


class TestSettlementRefund:
    """Écritures de refund (remboursement)."""

    def test_refund_commission_restituee(self, sample_config: AppConfig) -> None:
        """Refund commission restituée: net=-95, commission=-5 → 411 D=100, PSP C=95, 627 C=5."""
        tx = _make_transaction(
            type="refund",
            net_amount=-95.0,
            commission_ttc=-5.0,
        )
        entries = generate_settlement_entries(tx, sample_config)

        assert len(entries) == 3

        # PSP 511 crédit
        assert entries[0].account == "51150007"
        assert entries[0].debit == 0.0
        assert entries[0].credit == 95.0

        # 627 commission crédit
        assert entries[1].account == "62700002"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 5.0

        # 411 client débit
        assert entries[2].account == "411SHOPIFY"
        assert entries[2].debit == 100.0
        assert entries[2].credit == 0.0

        _assert_balance(entries)

    def test_refund_commission_non_restituee(self, sample_config: AppConfig) -> None:
        """Refund commission non restituée: net=-105, commission=5 → 411 D=100 + 627 D=5, PSP C=105."""
        tx = _make_transaction(
            type="refund",
            net_amount=-105.0,
            commission_ttc=5.0,
        )
        entries = generate_settlement_entries(tx, sample_config)

        assert len(entries) == 3

        # PSP 511 crédit
        assert entries[0].account == "51150007"
        assert entries[0].debit == 0.0
        assert entries[0].credit == 105.0

        # 627 commission débit (non restituée)
        assert entries[1].account == "62700002"
        assert entries[1].debit == 5.0
        assert entries[1].credit == 0.0

        # 411 client débit
        assert entries[2].account == "411SHOPIFY"
        assert entries[2].debit == 100.0
        assert entries[2].credit == 0.0

        _assert_balance(entries)


class TestSettlementGuardClauses:
    """Guard clauses et cas limites."""

    def test_payment_method_none_returns_empty(self, sample_config: AppConfig) -> None:
        """payment_method=None → liste vide."""
        tx = _make_transaction(payment_method=None)
        entries = generate_settlement_entries(tx, sample_config)
        assert entries == []

    def test_commission_zero_no_627_line(self, sample_config: AppConfig) -> None:
        """commission_ttc=0 → pas de ligne 627, 2 lignes seulement (PSP + 411)."""
        tx = _make_transaction(
            net_amount=100.0, commission_ttc=0.0
        )
        entries = generate_settlement_entries(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "51150007"  # PSP
        assert entries[1].account == "411SHOPIFY"  # 411
        # Pas de ligne 627
        assert all(e.entry_type != "commission" for e in entries)
        _assert_balance(entries)

    def test_net_amount_zero_no_psp_line(self, sample_config: AppConfig) -> None:
        """net_amount=0, commission>0 → pas de ligne PSP, 2 lignes (627 + 411)."""
        tx = _make_transaction(
            net_amount=0.0, commission_ttc=5.0
        )
        entries = generate_settlement_entries(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "62700002"  # 627
        assert entries[1].account == "411SHOPIFY"  # 411
        _assert_balance(entries)

    def test_total_411_zero_no_411_line(self, sample_config: AppConfig) -> None:
        """net=-5, commission=5 → total_411=0 → pas de ligne 411, 2 lignes (PSP C + 627 D)."""
        tx = _make_transaction(
            net_amount=-5.0, commission_ttc=5.0
        )
        entries = generate_settlement_entries(tx, sample_config)

        assert len(entries) == 2
        # PSP crédit
        assert entries[0].account == "51150007"
        assert entries[0].credit == 5.0
        # 627 débit
        assert entries[1].account == "62700002"
        assert entries[1].debit == 5.0
        # Pas de 411
        assert all(e.account != "411SHOPIFY" for e in entries)
        _assert_balance(entries)

    def test_all_zero_returns_empty(self, sample_config: AppConfig) -> None:
        """net=0, commission=0 → liste vide."""
        tx = _make_transaction(
            net_amount=0.0, commission_ttc=0.0
        )
        entries = generate_settlement_entries(tx, sample_config)
        assert entries == []


class TestSettlementEntryTypes:
    """Vérification des entry_type."""

    def test_entry_types_sale(self, sample_config: AppConfig) -> None:
        """PSP et 411 → 'settlement', 627 → 'commission'."""
        tx = _make_transaction()
        entries = generate_settlement_entries(tx, sample_config)

        assert entries[0].entry_type == "settlement"  # PSP
        assert entries[1].entry_type == "commission"  # 627
        assert entries[2].entry_type == "settlement"  # 411


class TestSettlementLabels:
    """Vérification des libellés."""

    def test_label_sale(self, sample_config: AppConfig) -> None:
        """Sale → 'Règlement #1118 Shopify'."""
        tx = _make_transaction(reference="#1118", channel="shopify", type="sale")
        entries = generate_settlement_entries(tx, sample_config)
        assert entries[0].label == "Règlement #1118 Shopify"

    def test_label_refund(self, sample_config: AppConfig) -> None:
        """Refund → 'Remb. PSP #1200 Shopify'."""
        tx = _make_transaction(
            reference="#1200",
            type="refund",
            net_amount=-95.0,
            commission_ttc=-5.0,
        )
        entries = generate_settlement_entries(tx, sample_config)
        assert entries[0].label == "Remb. PSP #1200 Shopify"

    def test_label_refund_underscore_channel(self, sample_config: AppConfig) -> None:
        """Canal avec underscore → 'Remb. PSP #1300 Leroy Merlin'."""
        config = AppConfig(
            clients={**sample_config.clients, "leroy_merlin": "411LEROY"},
            fournisseurs=sample_config.fournisseurs,
            psp=sample_config.psp,
            transit=sample_config.transit,
            banque=sample_config.banque,
            comptes_speciaux=sample_config.comptes_speciaux,
            comptes_vente_prefix=sample_config.comptes_vente_prefix,
            canal_codes={**sample_config.canal_codes, "leroy_merlin": "03"},
            comptes_tva_prefix=sample_config.comptes_tva_prefix,
            vat_table=sample_config.vat_table,
            alpha2_to_numeric=sample_config.alpha2_to_numeric,
            channels=sample_config.channels,
        )
        tx = _make_transaction(
            reference="#1300",
            channel="leroy_merlin",
            type="refund",
            net_amount=-95.0,
            commission_ttc=-5.0,
        )
        entries = generate_settlement_entries(tx, config)
        assert entries[0].label == "Remb. PSP #1300 Leroy Merlin"


class TestSettlementMetadata:
    """Vérification des métadonnées communes."""

    def test_date(self, sample_config: AppConfig) -> None:
        """Date = date de la transaction."""
        tx = _make_transaction(date=datetime.date(2024, 3, 1))
        entries = generate_settlement_entries(tx, sample_config)
        for e in entries:
            assert e.date == datetime.date(2024, 3, 1)

    def test_journal(self, sample_config: AppConfig) -> None:
        """Journal = 'RG'."""
        tx = _make_transaction()
        entries = generate_settlement_entries(tx, sample_config)
        for e in entries:
            assert e.journal == "RG"

    def test_piece_number_and_lettrage(self, sample_config: AppConfig) -> None:
        """piece_number et lettrage = reference."""
        tx = _make_transaction(reference="#9999")
        entries = generate_settlement_entries(tx, sample_config)
        for e in entries:
            assert e.piece_number == "#9999"
            assert e.lettrage == "#9999"

    def test_balance_on_every_case(self, sample_config: AppConfig) -> None:
        """Équilibre systématique sur tous les cas."""
        cases = [
            {"net_amount": 95.0, "commission_ttc": 5.0, "type": "sale"},
            {"net_amount": -95.0, "commission_ttc": -5.0, "type": "refund"},
            {"net_amount": -105.0, "commission_ttc": 5.0, "type": "refund"},
            {"net_amount": 100.0, "commission_ttc": 0.0, "type": "sale"},
            {"net_amount": 0.0, "commission_ttc": 5.0, "type": "sale"},
            {"net_amount": -5.0, "commission_ttc": 5.0, "type": "sale"},
        ]
        for case in cases:
            tx = _make_transaction(**case)
            entries = generate_settlement_entries(tx, sample_config)
            if entries:
                _assert_balance(entries)
