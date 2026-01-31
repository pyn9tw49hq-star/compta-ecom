"""Tests pour engine/accounts.py — build_account() et verify_balance()."""

from __future__ import annotations

import datetime

import pytest

from compta_ecom.engine.accounts import build_account, verify_balance
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
