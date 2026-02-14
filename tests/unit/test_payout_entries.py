"""Tests pour engine/payout_entries.py — écritures de reversement PSP."""

from __future__ import annotations

import datetime

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.payout_entries import generate_payout_entries
from compta_ecom.models import PayoutDetail, PayoutSummary

# Note: PayoutDetail imported for test_global_mode_with_details_present


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

    def test_journal_reglement(self, sample_config: AppConfig) -> None:
        """Journal = RG pour les deux lignes."""
        payout = _make_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        assert all(e.journal == "RG" for e in entries)

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
        # Lettrage uniquement sur le compte 511 (PSP), pas sur 580 (transit)
        for e in entries:
            if e.account.startswith("511"):
                assert e.lettrage == "P999"
            else:
                assert e.lettrage == ""

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

    def test_mixed_psp_anomaly_cross_period(self, sample_config: AppConfig) -> None:
        """psp_type=None, matched_net_sum=None → info severity (cross-period)."""
        payout = _make_payout(psp_type=None, payout_reference="P_MIX")
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert entries == []
        assert len(anomalies) == 1
        assert anomalies[0].type == "mixed_psp_payout"
        assert anomalies[0].severity == "info"
        assert "période différente" in anomalies[0].detail

    def test_mixed_psp_anomaly_with_matched_transactions(self, sample_config: AppConfig) -> None:
        """psp_type=None, matched_net_sum set → warning severity (true mixed PSP)."""
        payout = _make_payout(psp_type=None, payout_reference="P_MIX", matched_net_sum=100.0)
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert entries == []
        assert len(anomalies) == 1
        assert anomalies[0].type == "mixed_psp_payout"
        assert anomalies[0].severity == "warning"
        assert "plusieurs moyens de paiement" in anomalies[0].detail


class TestGeneratePayoutEntriesBalance:
    """Tests d'équilibre débit/crédit."""

    def test_balance_verified(self, sample_config: AppConfig) -> None:
        """verify_balance est appelé et passe sans erreur."""
        payout = _make_payout(total_amount=123.45)
        entries, _ = generate_payout_entries(payout, sample_config)

        total_debit = sum(e.debit for e in entries)
        total_credit = sum(e.credit for e in entries)
        assert round(total_debit, 2) == round(total_credit, 2)



# ---------------------------------------------------------------------------
# Tests mode global avec details présents (correctif v2)
# ---------------------------------------------------------------------------


class TestGlobalModeWithDetails:
    """AC12 : Même avec details non-None, 1 seule paire globale."""

    def test_global_mode_with_details_present(self, sample_config: AppConfig) -> None:
        """PayoutSummary avec details non-None → 1 seule paire globale (pas N paires)."""
        details = [
            PayoutDetail(
                payout_date=datetime.date(2026, 1, 30),
                payout_id="144387047761",
                order_reference="#1186",
                transaction_type="charge",
                amount=420.00,
                fee=-19.70,
                net=400.30,
                payment_method="card",
                channel="shopify",
            ),
            PayoutDetail(
                payout_date=datetime.date(2026, 1, 30),
                payout_id="144387047761",
                order_reference="#1185",
                transaction_type="charge",
                amount=48.30,
                fee=-2.16,
                net=46.14,
                payment_method="card",
                channel="shopify",
            ),
        ]
        payout = _make_payout(
            payout_date=datetime.date(2026, 1, 30),
            total_amount=446.44,
            payout_reference="144387047761",
            details=details,
        )
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(anomalies) == 0
        # 1 seule paire (2 lignes), pas 2 paires (4 lignes)
        assert len(entries) == 2

        transit = entries[0]
        psp = entries[1]

        # Montant = total_amount (446.44), pas somme des nets (446.44 ici aussi)
        assert transit.account == "58000000"
        assert transit.debit == 446.44
        assert transit.credit == 0.0

        assert psp.account == "51150007"
        assert psp.debit == 0.0
        assert psp.credit == 446.44

        # Lettrage = payout_reference (pas order_reference)
        assert transit.lettrage == ""
        assert psp.lettrage == "144387047761"

        # Piece number = payout_reference (pas order_reference)
        assert transit.piece_number == "144387047761"
        assert psp.piece_number == "144387047761"


class TestTotalAmountOverMatchedNetSum:
    """AC13 : Montant = total_amount, pas matched_net_sum."""

    def test_uses_total_amount_not_matched_net_sum(self, sample_config: AppConfig) -> None:
        """Quand matched_net_sum != total_amount, le montant = total_amount."""
        payout = _make_payout(
            total_amount=500.00,
            matched_net_sum=480.00,  # Différent de total_amount
        )
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(entries) == 2
        assert len(anomalies) == 0

        # Le montant doit être total_amount (500), pas matched_net_sum (480)
        assert entries[0].debit == 500.00
        assert entries[1].credit == 500.00


class TestAggregatedModeUnchanged:
    """AC14 : Mode agrégé sans details — comportement identique."""

    def test_aggregated_when_details_none(self, sample_config: AppConfig) -> None:
        """PayoutSummary sans details → mode agrégé, comportement identique."""
        payout = _make_payout()  # details=None par défaut
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(entries) == 2
        assert len(anomalies) == 0
        assert entries[0].lettrage == ""  # transit 580 : pas de lettrage
        assert entries[1].lettrage == "P001"  # PSP 511 : lettrage = payout_reference
