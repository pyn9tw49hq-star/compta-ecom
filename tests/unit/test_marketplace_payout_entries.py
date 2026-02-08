"""Tests pour engine/marketplace_payout_entries.py — reversements marketplace."""

from __future__ import annotations

import datetime
import logging

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.marketplace_payout_entries import (
    generate_marketplace_payout,
    generate_marketplace_payout_from_summary,
)
from compta_ecom.models import BalanceError, NormalizedTransaction, PayoutSummary


def _make_transaction(**overrides: object) -> NormalizedTransaction:
    """Helper pour construire une NormalizedTransaction avec des valeurs par défaut."""
    defaults: dict[str, object] = {
        "reference": "CMD-001",
        "channel": "manomano",
        "date": datetime.date(2024, 1, 15),
        "type": "sale",
        "amount_ht": 100.0,
        "amount_tva": 20.0,
        "amount_ttc": 120.0,
        "shipping_ht": 0.0,
        "shipping_tva": 0.0,
        "tva_rate": 20.0,
        "country_code": "250",
        "commission_ttc": 18.0,
        "commission_ht": 15.0,
        "net_amount": 850.0,
        "payout_date": datetime.date(2024, 1, 20),
        "payout_reference": "PAY-001",
        "payment_method": None,
        "special_type": None,
    }
    defaults.update(overrides)
    return NormalizedTransaction(**defaults)  # type: ignore[arg-type]


class TestNominalPayoutEntries:
    """Tests nominaux de reversement marketplace."""

    def test_sale_manomano_nominal(self, sample_config: AppConfig) -> None:
        """Vente nominale ManoMano : net_amount=850.00 → 51200000 D, FMANO C."""
        tx = _make_transaction(net_amount=850.0)
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        debit_entry = entries[0]
        credit_entry = entries[1]
        assert debit_entry.account == "51200000"
        assert debit_entry.debit == 850.0
        assert debit_entry.credit == 0.0
        assert credit_entry.account == "FMANO"
        assert credit_entry.debit == 0.0
        assert credit_entry.credit == 850.0

    def test_refund_reversal(self, sample_config: AppConfig) -> None:
        """Refund : net_amount=-200.00 → FMANO D, 51200000 C."""
        tx = _make_transaction(net_amount=-200.0, type="refund")
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "FMANO"
        assert entries[0].debit == 200.0
        assert entries[0].credit == 0.0
        assert entries[1].account == "51200000"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 200.0

    @pytest.mark.parametrize(
        "channel,expected_account",
        [
            ("manomano", "FMANO"),
            ("decathlon", "FDECATHLON"),
            ("leroy_merlin", "FADEO"),
        ],
    )
    def test_three_marketplaces_nominal(
        self, sample_config: AppConfig, channel: str, expected_account: str
    ) -> None:
        """Cas nominal paramétré sur 3 marketplaces → comptes fournisseurs distincts."""
        tx = _make_transaction(channel=channel, net_amount=500.0)
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "51200000"
        assert entries[0].debit == 500.0
        assert entries[1].account == expected_account
        assert entries[1].credit == 500.0


class TestGuardClauses:
    """Tests des guard clauses."""

    def test_payout_date_none_returns_empty(self, sample_config: AppConfig) -> None:
        """payout_date is None → liste vide."""
        tx = _make_transaction(payout_date=None)
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries == []

    def test_net_amount_zero_returns_empty(self, sample_config: AppConfig) -> None:
        """net_amount == 0.0 → liste vide."""
        tx = _make_transaction(net_amount=0.0)
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries == []

    def test_special_type_no_payout_date_warning(
        self, sample_config: AppConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        """special_type non-SUBSCRIPTION + payout_date is None → [] + logger.warning."""
        tx = _make_transaction(
            special_type="ADJUSTMENT",
            payout_date=None,
        )
        with caplog.at_level(logging.WARNING):
            entries = generate_marketplace_payout(tx, sample_config)

        assert entries == []
        assert "sans payout_date" in caplog.text

    def test_subscription_without_payout_date_generates_entries(
        self, sample_config: AppConfig
    ) -> None:
        """SUBSCRIPTION + payout_date is None → écritures générées avec date de création."""
        creation_date = datetime.date(2025, 12, 11)
        tx = _make_transaction(
            special_type="SUBSCRIPTION",
            date=creation_date,
            payout_date=None,
            net_amount=-70.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert all(e.date == creation_date for e in entries)
        assert all(e.entry_type == "fee" for e in entries)


class TestSpecialTypes:
    """Tests des lignes spéciales."""

    def test_adjustment(self, sample_config: AppConfig) -> None:
        """ADJUSTMENT : 51200000 D, 51150002 C, date = payout_date."""
        payout_date = datetime.date(2024, 1, 20)
        tx = _make_transaction(
            special_type="ADJUSTMENT",
            net_amount=50.0,
            commission_ttc=0.0,
            commission_ht=None,
            payout_date=payout_date,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "51200000"
        assert entries[0].debit == 50.0
        assert entries[1].account == "51150002"
        assert entries[1].credit == 50.0
        # Non-régression : les types spéciaux non-SUBSCRIPTION utilisent payout_date
        assert all(e.date == payout_date for e in entries)

    def test_eco_contribution(self, sample_config: AppConfig) -> None:
        """ECO_CONTRIBUTION : net_amount=-30.00 → FMANO D, 51200000 C."""
        tx = _make_transaction(
            special_type="ECO_CONTRIBUTION",
            net_amount=-30.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "FMANO"
        assert entries[0].debit == 30.0
        assert entries[1].account == "51200000"
        assert entries[1].credit == 30.0

    def test_subscription_manomano(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION ManoMano : FMANO D, 411MANO C (compte client)."""
        tx = _make_transaction(
            channel="manomano",
            special_type="SUBSCRIPTION",
            net_amount=-100.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "FMANO"
        assert entries[0].debit == 100.0
        assert entries[1].account == "411MANO"
        assert entries[1].credit == 100.0
        # Vérifier que entry_type est "fee" pour les abonnements
        assert entries[0].entry_type == "fee"
        assert entries[1].entry_type == "fee"

    def test_subscription_decathlon(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION Décathlon : 61311112 D, CDECATHLON C (compte client)."""
        tx = _make_transaction(
            channel="decathlon",
            special_type="SUBSCRIPTION",
            net_amount=-70.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "61311112"
        assert entries[0].debit == 70.0
        assert entries[1].account == "CDECATHLON"
        assert entries[1].credit == 70.0
        # Vérifier que entry_type est "fee" pour les abonnements
        assert entries[0].entry_type == "fee"
        assert entries[1].entry_type == "fee"

    def test_subscription_leroy_merlin(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION Leroy Merlin : 61311113 D (HT) + 44566001 D (TVA) + 411LM C (TTC)."""
        tx = _make_transaction(
            channel="leroy_merlin",
            special_type="SUBSCRIPTION",
            net_amount=-39.00,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
        # Charge HT au débit
        assert entries[0].account == "61311113"
        assert entries[0].debit == 39.00
        assert entries[0].lettrage == ""
        # TVA déductible au débit
        assert entries[1].account == "44566001"
        assert entries[1].debit == 7.80
        assert entries[1].lettrage == ""
        # Client TTC au crédit
        assert entries[2].account == "411LM"
        assert entries[2].credit == 46.80
        # Vérifier que entry_type est "fee" pour les abonnements
        assert all(e.entry_type == "fee" for e in entries)

    def test_subscription_leroy_merlin_credit_note(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION Leroy Merlin avoir (net_amount > 0) : sens inversé.

        Remboursement d'abonnement : 411LM D (TTC) + 61311113 C (HT) + 44566001 C (TVA).
        Par symétrie avec le traitement des commissions (marketplace_entries.py),
        la branche 3 écritures doit respecter le signe de net_amount.
        """
        tx = _make_transaction(
            channel="leroy_merlin",
            special_type="SUBSCRIPTION",
            net_amount=39.00,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
        # Client TTC au débit (remboursement)
        assert entries[0].account == "411LM"
        assert entries[0].debit == 46.80
        assert entries[0].credit == 0.0
        # Charge HT au crédit (contrepassation)
        assert entries[1].account == "61311113"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 39.00
        # TVA déductible au crédit (contrepassation)
        assert entries[2].account == "44566001"
        assert entries[2].debit == 0.0
        assert entries[2].credit == 7.80
        # entry_type reste "fee"
        assert all(e.entry_type == "fee" for e in entries)

    def test_refund_penalty(self, sample_config: AppConfig) -> None:
        """REFUND_PENALTY : FMANO D, 51200000 C."""
        tx = _make_transaction(
            special_type="REFUND_PENALTY",
            net_amount=-20.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "FMANO"
        assert entries[0].debit == 20.0
        assert entries[1].account == "51200000"
        assert entries[1].credit == 20.0


class TestLabels:
    """Tests des libellés."""

    def test_label_regular(self, sample_config: AppConfig) -> None:
        """Libellé régulier : 'Reversement CMD-001 Manomano'."""
        tx = _make_transaction()
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label == "Reversement CMD-001 Manomano"

    def test_label_adjustment(self, sample_config: AppConfig) -> None:
        """Libellé ADJUSTMENT : 'Ajustement ...'."""
        tx = _make_transaction(special_type="ADJUSTMENT", net_amount=50.0)
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label.startswith("Ajustement")

    def test_label_subscription(self, sample_config: AppConfig) -> None:
        """Libellé SUBSCRIPTION : 'Abonnement ...'."""
        tx = _make_transaction(special_type="SUBSCRIPTION", net_amount=-100.0)
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label.startswith("Abonnement")

    def test_label_eco_contribution(self, sample_config: AppConfig) -> None:
        """Libellé ECO_CONTRIBUTION : 'Éco-contribution ...'."""
        tx = _make_transaction(special_type="ECO_CONTRIBUTION", net_amount=-30.0)
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label.startswith("Éco-contribution")

    def test_label_refund_penalty(self, sample_config: AppConfig) -> None:
        """Libellé REFUND_PENALTY : 'Pénalité remb. ...'."""
        tx = _make_transaction(special_type="REFUND_PENALTY", net_amount=-20.0)
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label.startswith("Pénalité remb.")

    def test_label_underscore_channel(self, sample_config: AppConfig) -> None:
        """Canal avec underscore → 'Leroy Merlin' dans le libellé."""
        tx = _make_transaction(channel="leroy_merlin", net_amount=500.0)
        entries = generate_marketplace_payout(tx, sample_config)
        assert "Leroy Merlin" in entries[0].label


class TestEntryMetadata:
    """Tests des métadonnées d'écriture."""

    def test_entry_type_payout(self, sample_config: AppConfig) -> None:
        """entry_type = 'payout' pour les deux lignes."""
        tx = _make_transaction()
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.entry_type == "payout" for e in entries)

    def test_journal_reglement(self, sample_config: AppConfig) -> None:
        """journal = 'RG'."""
        tx = _make_transaction()
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.journal == "RG" for e in entries)

    def test_date_is_payout_date(self, sample_config: AppConfig) -> None:
        """Date de l'écriture = payout_date pour les reversements classiques."""
        payout_date = datetime.date(2024, 2, 10)
        tx = _make_transaction(payout_date=payout_date)
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.date == payout_date for e in entries)

    def test_subscription_date_is_creation_date(self, sample_config: AppConfig) -> None:
        """Date de l'écriture SUBSCRIPTION = date de création (transaction.date), pas payout_date."""
        creation_date = datetime.date(2024, 1, 15)
        payout_date = datetime.date(2024, 2, 10)
        tx = _make_transaction(
            special_type="SUBSCRIPTION",
            date=creation_date,
            payout_date=payout_date,
            net_amount=-40.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.date == creation_date for e in entries)
        assert all(e.date != payout_date for e in entries)

    def test_piece_number_and_lettrage(self, sample_config: AppConfig) -> None:
        """piece_number et lettrage = reference."""
        tx = _make_transaction(reference="REF-XYZ")
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.piece_number == "REF-XYZ" for e in entries)
        assert all(e.lettrage == "REF-XYZ" for e in entries)


class TestBalanceVerification:
    """Tests de vérification d'équilibre."""

    def test_balance_error_on_imbalance(self, sample_config: AppConfig) -> None:
        """BalanceError si déséquilibre forcé (via monkey-patch)."""
        from unittest.mock import patch

        from compta_ecom.engine import marketplace_payout_entries as mod
        from compta_ecom.models import AccountingEntry as AE

        tx = _make_transaction(net_amount=100.0)

        def fake_verify(entries: list[AE]) -> None:
            # Simulate an imbalance
            raise BalanceError("Déséquilibre écriture: débit=100.0, crédit=99.0")

        with patch.object(mod, "verify_balance", side_effect=fake_verify):
            with pytest.raises(BalanceError, match="Déséquilibre"):
                generate_marketplace_payout(tx, sample_config)


class TestMarketplacePayoutFromSummary:
    """Tests pour generate_marketplace_payout_from_summary (lignes Paiement)."""

    def test_decathlon_payout_nominal(self, sample_config: AppConfig) -> None:
        """Payout Decathlon : 58000000 D, CDECATHLON C."""
        payout = PayoutSummary(
            payout_date=datetime.date(2024, 1, 25),
            channel="decathlon",
            total_amount=-56.70,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=["CMD-001"],
            psp_type=None,
            payout_reference="2024-01-25",
        )
        entries = generate_marketplace_payout_from_summary(payout, sample_config)

        assert len(entries) == 2
        # Transit (580) débité
        assert entries[0].account == "58000000"
        assert entries[0].debit == 56.70
        assert entries[0].credit == 0.0
        # Client (CDECATHLON) crédité
        assert entries[1].account == "CDECATHLON"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 56.70
        # entry_type = "payout"
        assert entries[0].entry_type == "payout"
        assert entries[1].entry_type == "payout"

    def test_manomano_payout_nominal(self, sample_config: AppConfig) -> None:
        """Payout ManoMano : 58000000 D, 411MANO C."""
        payout = PayoutSummary(
            payout_date=datetime.date(2024, 1, 20),
            channel="manomano",
            total_amount=-850.0,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=["CMD-002"],
            psp_type=None,
            payout_reference="2024-01-20",
        )
        entries = generate_marketplace_payout_from_summary(payout, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "58000000"
        assert entries[0].debit == 850.0
        assert entries[1].account == "411MANO"
        assert entries[1].credit == 850.0

    def test_leroy_merlin_payout_nominal(self, sample_config: AppConfig) -> None:
        """Payout Leroy Merlin : 58000000 D, 411LM C."""
        payout = PayoutSummary(
            payout_date=datetime.date(2024, 1, 15),
            channel="leroy_merlin",
            total_amount=-200.0,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=["CMD-003"],
            psp_type=None,
            payout_reference="2024-01-15",
        )
        entries = generate_marketplace_payout_from_summary(payout, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "58000000"
        assert entries[0].debit == 200.0
        assert entries[1].account == "411LM"
        assert entries[1].credit == 200.0

    def test_zero_amount_returns_empty(self, sample_config: AppConfig) -> None:
        """total_amount == 0.0 → liste vide."""
        payout = PayoutSummary(
            payout_date=datetime.date(2024, 1, 25),
            channel="decathlon",
            total_amount=0.0,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=[],
            psp_type=None,
            payout_reference="2024-01-25",
        )
        entries = generate_marketplace_payout_from_summary(payout, sample_config)
        assert entries == []

    def test_label_format(self, sample_config: AppConfig) -> None:
        """Libellé contient le canal et la date."""
        payout = PayoutSummary(
            payout_date=datetime.date(2024, 1, 25),
            channel="decathlon",
            total_amount=-100.0,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=[],
            psp_type=None,
            payout_reference="2024-01-25",
        )
        entries = generate_marketplace_payout_from_summary(payout, sample_config)
        assert "Decathlon" in entries[0].label
        assert "2024-01-25" in entries[0].label


class TestDecathlonSubscriptionLettrageByPayoutCycle:
    """Lettrage CDECATHLON subscription par cycle de paiement (AC-LETTRAGE-DEC)."""

    def test_subscription_decathlon_lettrage_split(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION Décathlon : seul CDECATHLON est lettré (payout_reference), compte charge vide."""
        tx = _make_transaction(
            channel="decathlon",
            reference="ABO-DEC-001",
            special_type="SUBSCRIPTION",
            net_amount=-40.0,
            commission_ttc=0.0,
            commission_ht=None,
            payout_date=datetime.date(2025, 7, 1),
            payout_reference="2025-07-01",
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        # 61311112 au débit → pas de lettrage (compte de charge)
        assert entries[0].account == "61311112"
        assert entries[0].lettrage == ""
        # CDECATHLON au crédit → lettrage = payout_reference
        assert entries[1].account == "CDECATHLON"
        assert entries[1].lettrage == "2025-07-01"

    def test_subscription_decathlon_without_payout_reference(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION Décathlon sans payout_reference → charge vide, client = reference."""
        tx = _make_transaction(
            channel="decathlon",
            reference="ABO-DEC-001",
            special_type="SUBSCRIPTION",
            net_amount=-40.0,
            commission_ttc=0.0,
            commission_ht=None,
            payout_date=None,
            payout_reference=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        # Compte de charge au débit → pas de lettrage
        assert entries[0].account == "61311112"
        assert entries[0].lettrage == ""
        # Client au crédit → lettrage = reference (fallback)
        assert entries[1].account == "CDECATHLON"
        assert entries[1].lettrage == "ABO-DEC-001"

    def test_subscription_manomano_unaffected(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION ManoMano : lettrage = reference pour tous (pas de split)."""
        tx = _make_transaction(
            channel="manomano",
            reference="ABO-MM-001",
            special_type="SUBSCRIPTION",
            net_amount=-100.0,
            commission_ttc=0.0,
            commission_ht=None,
            payout_reference="2025-07-01",
        )
        entries = generate_marketplace_payout(tx, sample_config)
        for e in entries:
            assert e.lettrage == "ABO-MM-001"
