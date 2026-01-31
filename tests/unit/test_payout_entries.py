"""Tests pour engine/payout_entries.py — écritures de reversement PSP."""

from __future__ import annotations

import datetime

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.payout_entries import generate_payout_entries
from compta_ecom.models import PayoutSummary


def _make_payout(**overrides: object) -> PayoutSummary:
    """Helper pour construire un PayoutSummary avec des valeurs par défaut."""
    defaults: dict[str, object] = {
        "payout_date": datetime.date(2026, 1, 23),
        "channel": "shopify",
        "total_amount": 186.06,
        "charges": 192.0,
        "refunds": 0.0,
        "fees": -5.94,
        "transaction_references": ["#TEST001", "#TEST002"],
        "psp_type": "card",
        "payout_reference": "P001",
    }
    defaults.update(overrides)
    return PayoutSummary(**defaults)  # type: ignore[arg-type]


class TestGeneratePayoutEntriesNominal:
    """Tests nominaux pour generate_payout_entries."""

    def test_nominal_card_two_lines(self, sample_config: AppConfig) -> None:
        """PayoutSummary card → 2 lignes (transit D, PSP C), équilibre OK."""
        payout = _make_payout()
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(entries) == 2
        assert len(anomalies) == 0

        transit_entry = entries[0]
        psp_entry = entries[1]

        # Transit 58000000 au débit
        assert transit_entry.account == "58000000"
        assert transit_entry.debit == 186.06
        assert transit_entry.credit == 0.0

        # PSP 51150007 au crédit
        assert psp_entry.account == "51150007"
        assert psp_entry.debit == 0.0
        assert psp_entry.credit == 186.06

    def test_journal_banque(self, sample_config: AppConfig) -> None:
        """Journal = BQ pour les deux lignes."""
        payout = _make_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        assert all(e.journal == "BQ" for e in entries)

    def test_entry_type_payout(self, sample_config: AppConfig) -> None:
        """entry_type = payout pour les deux lignes."""
        payout = _make_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        assert all(e.entry_type == "payout" for e in entries)

    def test_label_format(self, sample_config: AppConfig) -> None:
        """Libellé : 'Reversement card 2026-01-23'."""
        payout = _make_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        expected_label = "Reversement card 2026-01-23"
        assert all(e.label == expected_label for e in entries)

    def test_piece_number_is_payout_reference(self, sample_config: AppConfig) -> None:
        """Numéro de pièce = payout_reference."""
        payout = _make_payout(payout_reference="P999")
        entries, _ = generate_payout_entries(payout, sample_config)

        assert all(e.piece_number == "P999" for e in entries)
        assert all(e.lettrage == "P999" for e in entries)

    def test_date_is_payout_date(self, sample_config: AppConfig) -> None:
        """La date de l'écriture est payout_date."""
        payout = _make_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        assert all(e.date == datetime.date(2026, 1, 23) for e in entries)


class TestGeneratePayoutEntriesNegative:
    """Tests pour total_amount négatif."""

    def test_negative_amount_inverted(self, sample_config: AppConfig) -> None:
        """total_amount < 0 → PSP au débit, transit au crédit."""
        payout = _make_payout(total_amount=-50.0)
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(entries) == 2
        assert len(anomalies) == 0

        transit_entry = entries[0]
        psp_entry = entries[1]

        # Transit au crédit (montant négatif)
        assert transit_entry.account == "58000000"
        assert transit_entry.debit == 0.0
        assert transit_entry.credit == 50.0

        # PSP au débit (montant négatif)
        assert psp_entry.account == "51150007"
        assert psp_entry.debit == 50.0
        assert psp_entry.credit == 0.0


class TestGeneratePayoutEntriesZero:
    """Tests pour total_amount == 0."""

    def test_zero_amount_empty(self, sample_config: AppConfig) -> None:
        """total_amount == 0 → liste vide, pas d'anomalie."""
        payout = _make_payout(total_amount=0.0)
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert entries == []
        assert anomalies == []


class TestGeneratePayoutEntriesMixedPsp:
    """Tests pour psp_type = None (payout multi-PSP hétérogène)."""

    def test_mixed_psp_anomaly(self, sample_config: AppConfig) -> None:
        """psp_type = None → Anomaly(type='mixed_psp_payout'), pas d'écriture."""
        payout = _make_payout(psp_type=None, payout_reference="P_MIX")
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert entries == []
        assert len(anomalies) == 1
        assert anomalies[0].type == "mixed_psp_payout"
        assert anomalies[0].severity == "warning"
        assert "P_MIX" in anomalies[0].detail


class TestGeneratePayoutEntriesBalance:
    """Tests d'équilibre débit/crédit."""

    def test_balance_verified(self, sample_config: AppConfig) -> None:
        """verify_balance est appelé et passe sans erreur."""
        payout = _make_payout(total_amount=123.45)
        entries, _ = generate_payout_entries(payout, sample_config)

        total_debit = sum(e.debit for e in entries)
        total_credit = sum(e.credit for e in entries)
        assert round(total_debit, 2) == round(total_credit, 2)
