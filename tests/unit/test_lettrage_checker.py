"""Tests pour controls/lettrage_checker.py — contrôle lettrage soldé 511."""

from __future__ import annotations

import datetime

from compta_ecom.controls.lettrage_checker import LettrageChecker
from compta_ecom.models import AccountingEntry


def _make_entry(**overrides: object) -> AccountingEntry:
    """Helper pour construire une AccountingEntry avec des valeurs par défaut."""
    defaults: dict[str, object] = {
        "date": datetime.date(2026, 1, 16),
        "journal": "RG",
        "account": "51150007",
        "label": "Test",
        "debit": 0.0,
        "credit": 0.0,
        "piece_number": "REF",
        "lettrage": "PAY001",
        "channel": "shopify",
        "entry_type": "settlement",
    }
    defaults.update(overrides)
    return AccountingEntry(**defaults)  # type: ignore[arg-type]


class TestLettrageCheckerBalanced:
    """Groupes de lettrage 511 équilibrés → aucune anomalie."""

    def test_single_group_balanced(self) -> None:
        """1 groupe avec 2 débits + 1 crédit → soldé → 0 anomalie."""
        entries = [
            _make_entry(debit=64.89, credit=0.0, lettrage="PAY001"),
            _make_entry(debit=51.07, credit=0.0, lettrage="PAY001"),
            _make_entry(debit=0.0, credit=115.96, lettrage="PAY001", entry_type="payout"),
        ]
        anomalies = LettrageChecker.check(entries)
        assert anomalies == []

    def test_multiple_groups_balanced(self) -> None:
        """2 groupes soldés → 0 anomalie."""
        entries = [
            _make_entry(debit=100.0, lettrage="PAY001"),
            _make_entry(credit=100.0, lettrage="PAY001", entry_type="payout"),
            _make_entry(debit=50.0, lettrage="PAY002"),
            _make_entry(credit=50.0, lettrage="PAY002", entry_type="payout"),
        ]
        anomalies = LettrageChecker.check(entries)
        assert anomalies == []

    def test_payout_example_819_70(self) -> None:
        """Exemple concret du plan : payout 819.70€ avec 8 commandes → soldé."""
        amounts = [64.89, 51.07, 29.26, 26.30, 255.38, 93.25, 147.80, 151.75]
        entries = [_make_entry(debit=a, lettrage="143559229777") for a in amounts]
        entries.append(
            _make_entry(credit=819.70, lettrage="143559229777", entry_type="payout")
        )
        anomalies = LettrageChecker.check(entries)
        assert anomalies == []


class TestLettrageCheckerUnbalanced:
    """Groupes de lettrage 511 déséquilibrés → anomalie."""

    def test_unbalanced_group(self) -> None:
        """Débit != crédit → 1 anomalie severity=error."""
        entries = [
            _make_entry(debit=100.0, lettrage="PAY001"),
            _make_entry(credit=90.0, lettrage="PAY001", entry_type="payout"),
        ]
        anomalies = LettrageChecker.check(entries)
        assert len(anomalies) == 1
        assert anomalies[0].type == "lettrage_511_unbalanced"
        assert anomalies[0].severity == "error"
        assert anomalies[0].reference == "PAY001"

    def test_within_tolerance(self) -> None:
        """Écart <= 0.01€ → toléré, pas d'anomalie."""
        entries = [
            _make_entry(debit=100.0, lettrage="PAY001"),
            _make_entry(credit=99.99, lettrage="PAY001", entry_type="payout"),
        ]
        anomalies = LettrageChecker.check(entries)
        assert anomalies == []

    def test_just_above_tolerance(self) -> None:
        """Écart = 0.02€ → anomalie."""
        entries = [
            _make_entry(debit=100.0, lettrage="PAY001"),
            _make_entry(credit=99.98, lettrage="PAY001", entry_type="payout"),
        ]
        anomalies = LettrageChecker.check(entries)
        assert len(anomalies) == 1


class TestLettrageCheckerFiltering:
    """Filtrage : seuls les comptes 511 avec lettrage non vide sont vérifiés."""

    def test_non_511_ignored(self) -> None:
        """Comptes 411, 627, 580 ignorés même si déséquilibrés."""
        entries = [
            _make_entry(account="411SHOPIFY", debit=100.0, lettrage="REF1"),
            _make_entry(account="62700002", debit=5.0, lettrage=""),
            _make_entry(account="58000000", debit=50.0, lettrage=""),
        ]
        anomalies = LettrageChecker.check(entries)
        assert anomalies == []

    def test_empty_lettrage_ignored(self) -> None:
        """Écritures 511 avec lettrage vide (orphelines sans payout) ignorées."""
        entries = [
            _make_entry(debit=100.0, lettrage=""),
        ]
        anomalies = LettrageChecker.check(entries)
        assert anomalies == []

    def test_empty_entries(self) -> None:
        """Liste vide → 0 anomalie."""
        anomalies = LettrageChecker.check([])
        assert anomalies == []

    def test_mixed_511_and_non_511(self) -> None:
        """Seules les écritures 511 comptent dans l'équilibre."""
        entries = [
            _make_entry(account="51150007", debit=100.0, lettrage="PAY001"),
            _make_entry(account="51150007", credit=100.0, lettrage="PAY001", entry_type="payout"),
            _make_entry(account="411SHOPIFY", debit=200.0, lettrage="PAY001"),  # ignoré
        ]
        anomalies = LettrageChecker.check(entries)
        assert anomalies == []
