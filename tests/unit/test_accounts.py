"""Tests pour engine/accounts.py — build_account(), verify_balance() et normalize_lettrage()."""

from __future__ import annotations

import datetime

import pytest

from compta_ecom.engine.accounts import (
    _index_to_letter,
    build_account,
    normalize_lettrage,
    resolve_shipping_zone,
    verify_balance,
)
from compta_ecom.models import AccountingEntry, BalanceError


class TestBuildAccount:
    """Tests de construction dynamique des numéros de compte."""

    def test_nominal_with_channel(self) -> None:
        """707 + canal 01 + pays 250 → 70701250."""
        assert build_account("707", "01", "250") == "70701250"

    def test_without_channel_none(self) -> None:
        """4457 + None + pays 250 → 4457250."""
        assert build_account("4457", None, "250") == "4457250"

    def test_empty_string_treated_as_none(self) -> None:
        """channel_code="" traité comme None."""
        assert build_account("4457", "", "250") == "4457250"

    def test_country_belgique(self) -> None:
        """Pays 056 (Belgique)."""
        assert build_account("707", "01", "056") == "70701056"

    def test_country_domtom(self) -> None:
        """Pays 974 (DOM-TOM)."""
        assert build_account("707", "01", "974") == "70701974"

    def test_country_fallback(self) -> None:
        """Pays 000 (fallback inconnu)."""
        assert build_account("707", "01", "000") == "70701000"

    def test_tva_prefix_belgique(self) -> None:
        """4457 + None + pays 056 → 4457056."""
        assert build_account("4457", None, "056") == "4457056"


class TestResolveShippingZone:
    """Tests de resolve_shipping_zone()."""

    VAT_TABLE: dict[str, dict[str, object]] = {
        "250": {"name": "France", "rate": 20.0, "alpha2": "FR"},
        "276": {"name": "Allemagne", "rate": 19.0, "alpha2": "DE"},
        "826": {"name": "Royaume-Uni", "rate": 0.0, "alpha2": "GB"},
        "972": {"name": "Martinique", "rate": 0.0, "alpha2": "MQ"},
    }

    def test_france(self) -> None:
        """France (250) → france."""
        assert resolve_shipping_zone("250", self.VAT_TABLE) == "france"

    def test_domtom(self) -> None:
        """DOM-TOM Martinique (972) → hors_ue."""
        assert resolve_shipping_zone("972", self.VAT_TABLE) == "hors_ue"

    def test_ue_with_rate(self) -> None:
        """Allemagne (276, rate=19%) → ue."""
        assert resolve_shipping_zone("276", self.VAT_TABLE) == "ue"

    def test_export_zero_rate(self) -> None:
        """Royaume-Uni (826, rate=0%) → hors_ue."""
        assert resolve_shipping_zone("826", self.VAT_TABLE) == "hors_ue"

    def test_absent_country(self) -> None:
        """Pays absent de la table → hors_ue."""
        assert resolve_shipping_zone("999", self.VAT_TABLE) == "hors_ue"


class TestVerifyBalance:
    """Tests de verify_balance()."""

    def test_balanced_no_error(self) -> None:
        """Entrées équilibrées → pas d'erreur."""
        entries = [
            AccountingEntry(
                date=datetime.date(2024, 1, 1),
                journal="VE",
                account="411",
                label="test",
                debit=100.0,
                credit=0.0,
                piece_number="X",
                lettrage="X",
                channel="shopify",
                entry_type="sale",
            ),
            AccountingEntry(
                date=datetime.date(2024, 1, 1),
                journal="VE",
                account="707",
                label="test",
                debit=0.0,
                credit=100.0,
                piece_number="X",
                lettrage="X",
                channel="shopify",
                entry_type="sale",
            ),
        ]
        verify_balance(entries)  # should not raise

    def test_unbalanced_raises(self) -> None:
        """Entrées déséquilibrées → BalanceError."""
        entries = [
            AccountingEntry(
                date=datetime.date(2024, 1, 1),
                journal="VE",
                account="411",
                label="test",
                debit=100.0,
                credit=0.0,
                piece_number="X",
                lettrage="X",
                channel="shopify",
                entry_type="sale",
            ),
            AccountingEntry(
                date=datetime.date(2024, 1, 1),
                journal="VE",
                account="707",
                label="test",
                debit=0.0,
                credit=99.0,
                piece_number="X",
                lettrage="X",
                channel="shopify",
                entry_type="sale",
            ),
        ]
        with pytest.raises(BalanceError):
            verify_balance(entries)


class TestIndexToLetter:
    """Tests de _index_to_letter()."""

    def test_first_letter(self) -> None:
        assert _index_to_letter(0) == "A"

    def test_last_single_letter(self) -> None:
        assert _index_to_letter(25) == "Z"

    def test_first_double_letter(self) -> None:
        assert _index_to_letter(26) == "AA"

    def test_second_double_letter(self) -> None:
        assert _index_to_letter(27) == "BB"

    def test_last_double_letter(self) -> None:
        assert _index_to_letter(51) == "ZZ"

    def test_first_triple_letter(self) -> None:
        assert _index_to_letter(52) == "AAA"

    def test_middle_letter(self) -> None:
        assert _index_to_letter(2) == "C"

    def test_sequence_first_26(self) -> None:
        """Les 26 premières valeurs sont A..Z."""
        result = [_index_to_letter(i) for i in range(26)]
        expected = [chr(ord("A") + i) for i in range(26)]
        assert result == expected


def _make_entry(account: str, lettrage: str) -> AccountingEntry:
    """Helper pour créer une entrée avec compte et lettrage."""
    return AccountingEntry(
        date=datetime.date(2024, 1, 1),
        journal="RG",
        account=account,
        label="test",
        debit=100.0,
        credit=0.0,
        piece_number="X",
        lettrage=lettrage,
        channel="shopify",
        entry_type="settlement",
    )


class TestNormalizeLettrage:
    """Tests de normalize_lettrage()."""

    def test_empty_lettrage_unchanged(self) -> None:
        """Les entrées avec lettrage vide restent vides."""
        entries = [_make_entry("627000", "")]
        result = normalize_lettrage(entries)
        assert result[0].lettrage == ""

    def test_single_group_gets_letter_a(self) -> None:
        """Un seul groupe de lettrage → A."""
        entries = [
            _make_entry("41100250", "#1118"),
            _make_entry("41100250", "#1118"),
        ]
        result = normalize_lettrage(entries)
        assert all(e.lettrage == "A" for e in result)

    def test_two_groups_get_a_and_b(self) -> None:
        """Deux groupes de lettrage → A et B."""
        entries = [
            _make_entry("41100250", "#1118"),
            _make_entry("41100250", "#1119"),
        ]
        result = normalize_lettrage(entries)
        assert result[0].lettrage == "A"
        assert result[1].lettrage == "B"

    def test_independent_counters_per_account_prefix(self) -> None:
        """Compteurs indépendants : 411 et 511 ont chacun leur A."""
        entries = [
            _make_entry("41100250", "#1118"),
            _make_entry("51100001", "PAYOUT-123"),
        ]
        result = normalize_lettrage(entries)
        assert result[0].lettrage == "A"
        assert result[1].lettrage == "A"

    def test_same_lettrage_same_letter(self) -> None:
        """Deux entrées avec le même lettrage original → même lettre."""
        entries = [
            _make_entry("51100001", "PAYOUT-123"),
            _make_entry("51100001", "PAYOUT-123"),
            _make_entry("51100001", "PAYOUT-456"),
        ]
        result = normalize_lettrage(entries)
        assert result[0].lettrage == "A"
        assert result[1].lettrage == "A"
        assert result[2].lettrage == "B"

    def test_mixed_empty_and_non_empty(self) -> None:
        """Mix d'entrées avec et sans lettrage."""
        entries = [
            _make_entry("41100250", "#1118"),
            _make_entry("627000", ""),
            _make_entry("41100250", "#1119"),
        ]
        result = normalize_lettrage(entries)
        assert result[0].lettrage == "A"
        assert result[1].lettrage == ""
        assert result[2].lettrage == "B"

    def test_more_than_26_groups(self) -> None:
        """Plus de 26 groupes → passage aux lettres doublées."""
        refs = [f"REF-{i}" for i in range(28)]
        entries = [_make_entry("41100250", ref) for ref in refs]
        result = normalize_lettrage(entries)
        assert result[0].lettrage == "A"
        assert result[25].lettrage == "Z"
        assert result[26].lettrage == "AA"
        assert result[27].lettrage == "BB"
