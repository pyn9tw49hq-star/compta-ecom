"""Tests unitaires pour generate_direct_payment_entries."""

from __future__ import annotations

import datetime

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.direct_payment_entries import generate_direct_payment_entries
from compta_ecom.models import NormalizedTransaction


def _make_transaction(**overrides: object) -> NormalizedTransaction:
    """NormalizedTransaction de base pour paiement direct Klarna."""
    defaults: dict[str, object] = {
        "reference": "#DP01",
        "channel": "shopify",
        "date": datetime.date(2025, 1, 15),
        "type": "sale",
        "amount_ht": 110.0,
        "amount_tva": 22.0,
        "amount_ttc": 132.0,
        "shipping_ht": 8.33,
        "shipping_tva": 1.67,
        "tva_rate": 20.0,
        "country_code": "250",
        "commission_ttc": 0.0,
        "commission_ht": 0.0,
        "net_amount": 132.0,
        "payout_date": None,
        "payout_reference": None,
        "payment_method": "klarna",
        "special_type": "direct_payment",
    }
    defaults.update(overrides)
    return NormalizedTransaction(**defaults)  # type: ignore[arg-type]


def _assert_balance(entries: list) -> None:
    """Vérifie que la somme des débits == somme des crédits."""
    total_debit = round(sum(e.debit for e in entries), 2)
    total_credit = round(sum(e.credit for e in entries), 2)
    assert total_debit == total_credit, f"Déséquilibre: D={total_debit} C={total_credit}"


class TestDirectPaymentKlarna:
    def test_klarna_2_lines(self, sample_config: AppConfig) -> None:
        """Klarna direct: 46740000 D=132, 411SHOPIFY C=132, équilibré."""
        tx = _make_transaction()
        entries = generate_direct_payment_entries(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "46740000"
        assert entries[0].debit == 132.0
        assert entries[0].credit == 0.0
        assert entries[1].account == "411SHOPIFY"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 132.0
        _assert_balance(entries)


class TestDirectPaymentBankDeposit:
    def test_bank_deposit_2_lines(self, sample_config: AppConfig) -> None:
        """Bank Deposit: 58010000 D=132, 411SHOPIFY C=132, équilibré."""
        tx = _make_transaction(payment_method="bank_deposit")
        entries = generate_direct_payment_entries(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "58010000"
        assert entries[0].debit == 132.0
        assert entries[0].credit == 0.0
        assert entries[1].account == "411SHOPIFY"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 132.0
        _assert_balance(entries)


class TestDirectPaymentGuards:
    def test_payment_method_none_returns_empty(self, sample_config: AppConfig) -> None:
        """payment_method=None → aucune écriture."""
        tx = _make_transaction(payment_method=None)
        assert generate_direct_payment_entries(tx, sample_config) == []

    def test_unknown_direct_key_returns_empty(self, sample_config: AppConfig) -> None:
        """Clé inconnue dans direct_payments → aucune écriture."""
        tx = _make_transaction(payment_method="unknown_method")
        assert generate_direct_payment_entries(tx, sample_config) == []

    def test_amount_zero_returns_empty(self, sample_config: AppConfig) -> None:
        """Montant TTC = 0 → aucune écriture."""
        tx = _make_transaction(amount_ttc=0.0)
        assert generate_direct_payment_entries(tx, sample_config) == []

    def test_negative_amount_returns_empty(self, sample_config: AppConfig) -> None:
        """Montant TTC negatif → aucune ecriture (garde defensive)."""
        tx = _make_transaction(amount_ttc=-50.0)
        assert generate_direct_payment_entries(tx, sample_config) == []


class TestDirectPaymentMetadata:
    def test_journal_rg(self, sample_config: AppConfig) -> None:
        """Toutes les lignes utilisent le journal RG."""
        entries = generate_direct_payment_entries(_make_transaction(), sample_config)
        assert all(e.journal == "RG" for e in entries)

    def test_piece_number_is_reference(self, sample_config: AppConfig) -> None:
        """Le numéro de pièce est la référence de la transaction."""
        entries = generate_direct_payment_entries(_make_transaction(), sample_config)
        assert all(e.piece_number == "#DP01" for e in entries)

    def test_lettrage_411_is_reference(self, sample_config: AppConfig) -> None:
        """Le lettrage sur 411 est la référence (rapprochement avec VE)."""
        entries = generate_direct_payment_entries(_make_transaction(), sample_config)
        entry_411 = next(e for e in entries if e.account == "411SHOPIFY")
        assert entry_411.lettrage == "#DP01"

    def test_lettrage_debit_is_empty(self, sample_config: AppConfig) -> None:
        """Le lettrage sur le compte débit est vide (pas de payout)."""
        entries = generate_direct_payment_entries(_make_transaction(), sample_config)
        entry_debit = next(e for e in entries if e.account == "46740000")
        assert entry_debit.lettrage == ""

    def test_entry_type_settlement(self, sample_config: AppConfig) -> None:
        """Toutes les lignes ont entry_type='settlement'."""
        entries = generate_direct_payment_entries(_make_transaction(), sample_config)
        assert all(e.entry_type == "settlement" for e in entries)
