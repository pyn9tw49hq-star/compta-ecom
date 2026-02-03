"""Tests pour engine/payout_entries.py — écritures de reversement PSP."""

from __future__ import annotations

import datetime

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.payout_entries import generate_payout_entries
from compta_ecom.models import PayoutDetail, PayoutSummary


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
        assert "cross-period" in anomalies[0].detail

    def test_mixed_psp_anomaly_with_matched_transactions(self, sample_config: AppConfig) -> None:
        """psp_type=None, matched_net_sum set → warning severity (true mixed PSP)."""
        payout = _make_payout(psp_type=None, payout_reference="P_MIX", matched_net_sum=100.0)
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert entries == []
        assert len(anomalies) == 1
        assert anomalies[0].type == "mixed_psp_payout"
        assert anomalies[0].severity == "warning"
        assert "hétérogènes" in anomalies[0].detail


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
# Helpers pour le mode détaillé
# ---------------------------------------------------------------------------

def _make_detail(**overrides: object) -> PayoutDetail:
    """Helper pour construire un PayoutDetail avec des valeurs par défaut."""
    defaults: dict[str, object] = {
        "payout_date": datetime.date(2026, 1, 30),
        "payout_id": "144387047761",
        "order_reference": "#1186",
        "transaction_type": "charge",
        "amount": 420.00,
        "fee": -19.70,
        "net": 400.30,
        "payment_method": "card",
        "channel": "shopify",
    }
    defaults.update(overrides)
    return PayoutDetail(**defaults)  # type: ignore[arg-type]


def _make_detailed_payout(**overrides: object) -> PayoutSummary:
    """Helper pour construire un PayoutSummary avec details (mode détaillé)."""
    defaults: dict[str, object] = {
        "payout_date": datetime.date(2026, 1, 30),
        "channel": "shopify",
        "total_amount": 446.44,
        "charges": 466.14,
        "refunds": 0.0,
        "fees": -19.70,
        "transaction_references": ["#1186", "#1185"],
        "psp_type": "card",
        "payout_reference": "144387047761",
        "details": [
            _make_detail(order_reference="#1186", net=400.30),
            _make_detail(order_reference="#1185", net=46.14, amount=48.30, fee=-2.16),
        ],
    }
    defaults.update(overrides)
    return PayoutSummary(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests mode détaillé
# ---------------------------------------------------------------------------


class TestDetailedPayoutNominal:
    """AC11 : Mode détaillé nominal — 2 PayoutDetail card → 4 écritures."""

    def test_two_details_four_entries(self, sample_config: AppConfig) -> None:
        """2 PayoutDetail → 4 écritures (2 paires), lettrage 511 = payout_reference."""
        payout = _make_detailed_payout()
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(anomalies) == 0
        assert len(entries) == 4

        # Pair 1 : #1186 — 400.30
        assert entries[0].account == "58000000"
        assert entries[0].debit == 400.30
        assert entries[0].lettrage == ""
        assert entries[0].piece_number == "#1186"
        assert entries[1].account == "51150007"
        assert entries[1].credit == 400.30
        assert entries[1].lettrage == "144387047761"  # payout_reference

        # Pair 2 : #1185 — 46.14
        assert entries[2].account == "58000000"
        assert entries[2].debit == 46.14
        assert entries[2].lettrage == ""
        assert entries[3].account == "51150007"
        assert entries[3].credit == 46.14
        assert entries[3].lettrage == "144387047761"  # payout_reference (même payout)

    def test_detailed_label_format(self, sample_config: AppConfig) -> None:
        """Label contient psp_type et order_reference."""
        payout = _make_detailed_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        assert entries[0].label == "Reversement card #1186"
        assert entries[2].label == "Reversement card #1185"

    def test_detailed_journal_and_entry_type(self, sample_config: AppConfig) -> None:
        """Journal = RG, entry_type = payout pour toutes les écritures."""
        payout = _make_detailed_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        assert all(e.journal == "RG" for e in entries)
        assert all(e.entry_type == "payout" for e in entries)


class TestDetailedPayoutRefund:
    """AC12 : Refund — net négatif → 511 D / 580 C."""

    def test_refund_inverted(self, sample_config: AppConfig) -> None:
        """PayoutDetail refund net=-29.00 → 580 C 29 / 511 D 29."""
        detail_refund = _make_detail(
            order_reference="#1099",
            transaction_type="refund",
            net=-29.00,
            amount=-29.00,
            fee=0.0,
        )
        payout = _make_detailed_payout(
            total_amount=-29.00,
            details=[detail_refund],
        )
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(anomalies) == 0
        assert len(entries) == 2

        transit = entries[0]
        psp = entries[1]

        # Transit au crédit (net négatif)
        assert transit.account == "58000000"
        assert transit.debit == 0.0
        assert transit.credit == 29.00

        # PSP au débit (net négatif)
        assert psp.account == "51150007"
        assert psp.debit == 29.00
        assert psp.credit == 0.0

        assert transit.lettrage == ""


class TestDetailedPayoutNetZero:
    """AC13 : Net zéro → ignoré, pas d'écriture."""

    def test_net_zero_skipped(self, sample_config: AppConfig) -> None:
        """PayoutDetail avec net=0.0 → aucune écriture."""
        detail_zero = _make_detail(
            order_reference="#ZERO",
            net=0.0,
            amount=10.0,
            fee=-10.0,
        )
        payout = _make_detailed_payout(
            total_amount=400.30,
            details=[
                _make_detail(order_reference="#1186", net=400.30),
                detail_zero,
            ],
        )
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(anomalies) == 0
        # Only 1 pair for #1186, the zero-net detail is skipped
        assert len(entries) == 2
        assert entries[0].lettrage == ""  # transit 580 : pas de lettrage
        assert entries[1].lettrage == "144387047761"  # PSP 511 : payout_reference


class TestDetailedPayoutPaypal:
    """AC14 : PSP paypal → compte 51150004."""

    def test_paypal_account(self, sample_config: AppConfig) -> None:
        """PayoutDetail payment_method='paypal' → account = 51150004."""
        detail_paypal = _make_detail(
            order_reference="#PP01",
            payment_method="paypal",
            net=50.00,
        )
        payout = _make_detailed_payout(
            total_amount=50.00,
            psp_type="paypal",
            details=[detail_paypal],
        )
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(anomalies) == 0
        assert len(entries) == 2
        assert entries[1].account == "51150004"


class TestDetailedPayoutUnknownPsp:
    """AC15 : PSP inconnu → anomalie unknown_psp_detail, pas d'écriture."""

    def test_unknown_psp_anomaly(self, sample_config: AppConfig) -> None:
        """payment_method=None + psp_type=None → anomalie."""
        detail_no_psp = _make_detail(
            order_reference="#NOPSP",
            payment_method=None,
            net=100.0,
        )
        payout = _make_detailed_payout(
            total_amount=100.0,
            psp_type=None,
            details=[detail_no_psp],
        )
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(entries) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "unknown_psp_detail"
        assert anomalies[0].severity == "warning"
        assert "#NOPSP" in anomalies[0].reference


class TestDetailedPayoutFallbackPsp:
    """AC16 : Fallback PSP — payment_method=None + payout.psp_type='card' → utilise card."""

    def test_fallback_to_payout_psp_type(self, sample_config: AppConfig) -> None:
        """payment_method=None → fallback sur payout.psp_type='card' → 51150007."""
        detail_no_method = _make_detail(
            order_reference="#FB01",
            payment_method=None,
            net=75.00,
        )
        payout = _make_detailed_payout(
            total_amount=75.00,
            psp_type="card",
            details=[detail_no_method],
        )
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(anomalies) == 0
        assert len(entries) == 2
        assert entries[1].account == "51150007"
        assert entries[0].label == "Reversement card #FB01"


class TestDetailedPayoutAggregatedUnchanged:
    """AC17 : Mode agrégé inchangé quand details=None."""

    def test_aggregated_when_details_none(self, sample_config: AppConfig) -> None:
        """PayoutSummary sans details → mode agrégé, comportement identique."""
        payout = _make_payout()  # details=None par défaut
        entries, anomalies = generate_payout_entries(payout, sample_config)

        assert len(entries) == 2
        assert len(anomalies) == 0
        # Lettrage = payout_reference uniquement sur 511 (mode agrégé)
        assert entries[0].lettrage == ""  # transit 580 : pas de lettrage
        assert entries[1].lettrage == "P001"  # PSP 511 : lettrage


class TestDetailedPayoutBalance:
    """AC18 : Chaque paire en mode détaillé est équilibrée."""

    def test_each_pair_balanced(self, sample_config: AppConfig) -> None:
        """Vérifier que chaque paire transit/psp est équilibrée."""
        payout = _make_detailed_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        # 4 entries = 2 pairs
        for i in range(0, len(entries), 2):
            pair = entries[i : i + 2]
            total_debit = round(sum(e.debit for e in pair), 2)
            total_credit = round(sum(e.credit for e in pair), 2)
            assert total_debit == total_credit

    def test_total_balance(self, sample_config: AppConfig) -> None:
        """Équilibre total de toutes les écritures."""
        payout = _make_detailed_payout()
        entries, _ = generate_payout_entries(payout, sample_config)

        total_debit = round(sum(e.debit for e in entries), 2)
        total_credit = round(sum(e.credit for e in entries), 2)
        assert total_debit == total_credit
