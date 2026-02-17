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
            net_amount=-60.0,
            amount_ht=50.0,
            amount_tva=10.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
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
        """ECO_CONTRIBUTION : 60730000 D HT + 44566001 D TVA + 411MANO C TTC."""
        tx = _make_transaction(
            special_type="ECO_CONTRIBUTION",
            net_amount=-30.0,
            amount_ht=25.0,
            amount_tva=5.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
        # Charge HT au débit
        assert entries[0].account == "60730000"
        assert entries[0].debit == 25.0
        assert entries[0].lettrage == ""
        # TVA déductible au débit
        assert entries[1].account == "44566001"
        assert entries[1].debit == 5.0
        assert entries[1].lettrage == ""
        # Client TTC au crédit
        assert entries[2].account == "411MANO"
        assert entries[2].credit == 30.0
        assert all(e.entry_type == "fee" for e in entries)

    def test_eco_contribution_service_same_as_eco_contribution(
        self, sample_config: AppConfig
    ) -> None:
        """ECO_CONTRIBUTION_SERVICE produit les mêmes comptes qu'ECO_CONTRIBUTION (pas de 512)."""
        tx = _make_transaction(
            special_type="ECO_CONTRIBUTION_SERVICE",
            net_amount=-30.0,
            amount_ht=25.0,
            amount_tva=5.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
        # Charge HT au débit — même compte que ECO_CONTRIBUTION
        assert entries[0].account == "60730000"
        assert entries[0].debit == 25.0
        assert entries[0].lettrage == ""
        # TVA déductible au débit
        assert entries[1].account == "44566001"
        assert entries[1].debit == 5.0
        assert entries[1].lettrage == ""
        # Client TTC au crédit — pas de 512
        assert entries[2].account == "411MANO"
        assert entries[2].credit == 30.0
        assert all(e.entry_type == "fee" for e in entries)
        # Aucun compte 512
        assert not any("512" in e.account for e in entries)

    def test_subscription_manomano(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION ManoMano : 61311111 D HT + 44566001 D TVA + 411MANO C TTC."""
        tx = _make_transaction(
            channel="manomano",
            special_type="SUBSCRIPTION",
            net_amount=-60.0,
            amount_ht=50.0,
            amount_tva=10.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
        # Charge HT au débit
        assert entries[0].account == "61311111"
        assert entries[0].debit == 50.0
        assert entries[0].lettrage == ""
        # TVA déductible au débit
        assert entries[1].account == "44566001"
        assert entries[1].debit == 10.0
        assert entries[1].lettrage == ""
        # Client TTC au crédit
        assert entries[2].account == "411MANO"
        assert entries[2].credit == 60.0
        # Vérifier que entry_type est "fee" pour les abonnements
        assert all(e.entry_type == "fee" for e in entries)

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
            amount_ht=0.0,
            amount_tva=0.0,
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
            amount_ht=0.0,
            amount_tva=0.0,
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
        """REFUND_PENALTY : 62220300 D HT + 44566001 D TVA + 411MANO C TTC."""
        tx = _make_transaction(
            special_type="REFUND_PENALTY",
            net_amount=-24.0,
            amount_ht=20.0,
            amount_tva=4.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
        # Charge HT au débit
        assert entries[0].account == "62220300"
        assert entries[0].debit == 20.0
        assert entries[0].lettrage == ""
        # TVA déductible au débit
        assert entries[1].account == "44566001"
        assert entries[1].debit == 4.0
        assert entries[1].lettrage == ""
        # Client TTC au crédit
        assert entries[2].account == "411MANO"
        assert entries[2].credit == 24.0
        assert all(e.entry_type == "fee" for e in entries)


class TestLabels:
    """Tests des libellés."""

    def test_label_regular(self, sample_config: AppConfig) -> None:
        """Libellé régulier : 'Reversement CMD-001 ManoMano'."""
        tx = _make_transaction()
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label == "Reversement CMD-001 ManoMano"

    def test_label_adjustment(self, sample_config: AppConfig) -> None:
        """Libellé ADJUSTMENT : 'Ajustement ...'."""
        tx = _make_transaction(special_type="ADJUSTMENT", net_amount=50.0)
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label.startswith("Ajustement")

    def test_label_subscription(self, sample_config: AppConfig) -> None:
        """Libellé SUBSCRIPTION : 'Abonnement ...'."""
        tx = _make_transaction(
            special_type="SUBSCRIPTION", net_amount=-60.0,
            amount_ht=50.0, amount_tva=10.0,
        )
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label.startswith("Abonnement")

    def test_label_eco_contribution(self, sample_config: AppConfig) -> None:
        """Libellé ECO_CONTRIBUTION : 'Éco-contribution ...'."""
        tx = _make_transaction(
            special_type="ECO_CONTRIBUTION", net_amount=-30.0,
            amount_ht=25.0, amount_tva=5.0,
        )
        entries = generate_marketplace_payout(tx, sample_config)
        assert entries[0].label.startswith("Éco-contribution")

    def test_label_refund_penalty(self, sample_config: AppConfig) -> None:
        """Libellé REFUND_PENALTY : 'Pénalité remb. ...'."""
        tx = _make_transaction(
            special_type="REFUND_PENALTY", net_amount=-24.0,
            amount_ht=20.0, amount_tva=4.0,
        )
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
        """journal = 'RG' pour les canaux sans compte de charge (ManoMano)."""
        tx = _make_transaction()
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.journal == "RG" for e in entries)

    def test_journal_achats_subscription_decathlon(self, sample_config: AppConfig) -> None:
        """journal = 'AC' pour les abonnements Decathlon (compte de charge configuré)."""
        tx = _make_transaction(
            channel="decathlon",
            special_type="SUBSCRIPTION",
            net_amount=-70.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.journal == "AC" for e in entries)

    def test_journal_achats_subscription_leroy_merlin(self, sample_config: AppConfig) -> None:
        """journal = 'AC' pour les abonnements Leroy Merlin (compte de charge configuré)."""
        tx = _make_transaction(
            channel="leroy_merlin",
            special_type="SUBSCRIPTION",
            net_amount=-39.00,
            amount_ht=0.0,
            amount_tva=0.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.journal == "AC" for e in entries)

    def test_journal_reglement_payout_decathlon(self, sample_config: AppConfig) -> None:
        """journal = 'RG' pour les reversements Decathlon (pas un abonnement)."""
        tx = _make_transaction(channel="decathlon", net_amount=500.0)
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
            net_amount=-60.0,
            amount_ht=50.0,
            amount_tva=10.0,
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

    def test_subscription_manomano_lettrage(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION ManoMano : charge/TVA sans lettrage, 411MANO lettré par payout_reference."""
        tx = _make_transaction(
            channel="manomano",
            reference="ABO-MM-001",
            special_type="SUBSCRIPTION",
            net_amount=-60.0,
            amount_ht=50.0,
            amount_tva=10.0,
            commission_ttc=0.0,
            commission_ht=None,
            payout_reference="2025-07-01",
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
        # Charge : pas de lettrage
        assert entries[0].lettrage == ""
        # TVA : pas de lettrage
        assert entries[1].lettrage == ""
        # Client 411MANO : lettrage = payout_reference
        assert entries[2].lettrage == "2025-07-01"


class TestManoManoSpecialTypesThreeEntries:
    """Tests des 3 types spéciaux ManoMano avec écritures HT + TVA + 411MANO."""

    @pytest.mark.parametrize(
        "special_type,charge_account,ht,tva,ttc",
        [
            ("SUBSCRIPTION", "61311111", 50.0, 10.0, 60.0),
            ("ECO_CONTRIBUTION", "60730000", 25.0, 5.0, 30.0),
            ("ECO_CONTRIBUTION_SERVICE", "60730000", 25.0, 5.0, 30.0),
            ("REFUND_PENALTY", "62220300", 20.0, 4.0, 24.0),
        ],
    )
    def test_three_entries_balance(
        self,
        sample_config: AppConfig,
        special_type: str,
        charge_account: str,
        ht: float,
        tva: float,
        ttc: float,
    ) -> None:
        """Chaque type spécial produit 3 écritures équilibrées D/C."""
        tx = _make_transaction(
            special_type=special_type,
            net_amount=-ttc,
            amount_ht=ht,
            amount_tva=tva,
            commission_ttc=0.0,
            commission_ht=None,
            payout_reference="PAY-BATCH-001",
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 3
        # Charge HT
        assert entries[0].account == charge_account
        assert entries[0].debit == ht
        assert entries[0].credit == 0.0
        # TVA déductible
        assert entries[1].account == "44566001"
        assert entries[1].debit == tva
        assert entries[1].credit == 0.0
        # Client TTC
        assert entries[2].account == "411MANO"
        assert entries[2].debit == 0.0
        assert entries[2].credit == ttc
        # Équilibre D/C
        total_debit = sum(e.debit for e in entries)
        total_credit = sum(e.credit for e in entries)
        assert total_debit == total_credit
        # Lettrage : seul le client est lettré
        assert entries[0].lettrage == ""
        assert entries[1].lettrage == ""
        assert entries[2].lettrage == "PAY-BATCH-001"
        # Métadonnées
        assert all(e.entry_type == "fee" for e in entries)
        assert all(e.journal == "AC" for e in entries)


class TestManoManoVersementLettrageBalance:
    """Lettrage 411MANO cohérent sur un versement complet (#23).

    Un versement ManoMano contient ORDER + REFUND + ECO_CONTRIBUTION + SUBSCRIPTION.
    Toutes les écritures 411MANO doivent avoir lettrage = payout_reference.
    La somme D/C sur 411MANO pour ce payout_reference doit être équilibrée
    avec l'écriture agrégée du PayoutSummary.
    """

    PAYOUT_REF = "PAY-2025-01"

    def _order_tx(self) -> NormalizedTransaction:
        return _make_transaction(
            reference="M260200001",
            channel="manomano",
            type="sale",
            amount_ht=1000.0,
            amount_tva=200.0,
            amount_ttc=1200.0,
            commission_ttc=-18.0,
            commission_ht=-15.0,
            net_amount=1182.0,
            payout_date=datetime.date(2025, 1, 31),
            payout_reference=self.PAYOUT_REF,
        )

    def _refund_tx(self) -> NormalizedTransaction:
        return _make_transaction(
            reference="M260200002",
            channel="manomano",
            type="refund",
            amount_ht=50.0,
            amount_tva=10.0,
            amount_ttc=60.0,
            commission_ttc=1.8,
            commission_ht=1.5,
            net_amount=-58.2,
            payout_date=datetime.date(2025, 1, 31),
            payout_reference=self.PAYOUT_REF,
        )

    def _eco_tx(self) -> NormalizedTransaction:
        return _make_transaction(
            reference="ECO001",
            channel="manomano",
            special_type="ECO_CONTRIBUTION",
            net_amount=-30.0,
            amount_ht=25.0,
            amount_tva=5.0,
            commission_ttc=0.0,
            commission_ht=None,
            payout_date=datetime.date(2025, 1, 31),
            payout_reference=self.PAYOUT_REF,
        )

    def _sub_tx(self) -> NormalizedTransaction:
        return _make_transaction(
            reference="ABO001",
            channel="manomano",
            special_type="SUBSCRIPTION",
            net_amount=-60.0,
            amount_ht=50.0,
            amount_tva=10.0,
            commission_ttc=0.0,
            commission_ht=None,
            date=datetime.date(2025, 1, 15),
            payout_date=datetime.date(2025, 1, 31),
            payout_reference=self.PAYOUT_REF,
        )

    def test_all_411mano_entries_share_payout_reference(
        self, sample_config: AppConfig
    ) -> None:
        """Toutes les écritures 411MANO d'un versement ont lettrage = payout_reference."""
        from compta_ecom.engine.marketplace_entries import generate_marketplace_commission
        from compta_ecom.engine.sale_entries import generate_sale_entries

        all_entries = []

        # ORDER: vente + commission
        order = self._order_tx()
        all_entries.extend(generate_sale_entries(order, sample_config))
        all_entries.extend(generate_marketplace_commission(order, sample_config))

        # REFUND: avoir + remb. commission
        refund = self._refund_tx()
        all_entries.extend(generate_sale_entries(refund, sample_config))
        all_entries.extend(generate_marketplace_commission(refund, sample_config))

        # ECO_CONTRIBUTION: special type
        all_entries.extend(generate_marketplace_payout(self._eco_tx(), sample_config))

        # SUBSCRIPTION: special type
        all_entries.extend(generate_marketplace_payout(self._sub_tx(), sample_config))

        # PayoutSummary (580 ↔ 411MANO)
        payout_total = -(1182.0 - 58.2 - 30.0 - 60.0)  # négatif = sortie
        payout_summary = PayoutSummary(
            payout_date=datetime.date(2025, 1, 31),
            channel="manomano",
            total_amount=payout_total,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=["M260200001", "M260200002", "ECO001", "ABO001"],
            psp_type=None,
            payout_reference=self.PAYOUT_REF,
        )
        all_entries.extend(
            generate_marketplace_payout_from_summary(payout_summary, sample_config)
        )

        # Filtrer les écritures 411MANO
        entries_411 = [e for e in all_entries if e.account == "411MANO"]

        # Toutes les écritures 411MANO ont lettrage = PAYOUT_REF
        for entry in entries_411:
            assert entry.lettrage == self.PAYOUT_REF, (
                f"411MANO entry '{entry.label}' has lettrage='{entry.lettrage}', "
                f"expected '{self.PAYOUT_REF}'"
            )

    def test_411mano_lettrage_balanced(self, sample_config: AppConfig) -> None:
        """Somme D = somme C sur 411MANO pour un même payout_reference."""
        from compta_ecom.engine.marketplace_entries import generate_marketplace_commission
        from compta_ecom.engine.sale_entries import generate_sale_entries

        all_entries = []

        order = self._order_tx()
        all_entries.extend(generate_sale_entries(order, sample_config))
        all_entries.extend(generate_marketplace_commission(order, sample_config))

        refund = self._refund_tx()
        all_entries.extend(generate_sale_entries(refund, sample_config))
        all_entries.extend(generate_marketplace_commission(refund, sample_config))

        all_entries.extend(generate_marketplace_payout(self._eco_tx(), sample_config))
        all_entries.extend(generate_marketplace_payout(self._sub_tx(), sample_config))

        payout_total = -(1182.0 - 58.2 - 30.0 - 60.0)
        payout_summary = PayoutSummary(
            payout_date=datetime.date(2025, 1, 31),
            channel="manomano",
            total_amount=payout_total,
            charges=0.0,
            refunds=0.0,
            fees=0.0,
            transaction_references=["M260200001", "M260200002", "ECO001", "ABO001"],
            psp_type=None,
            payout_reference=self.PAYOUT_REF,
        )
        all_entries.extend(
            generate_marketplace_payout_from_summary(payout_summary, sample_config)
        )

        entries_411 = [e for e in all_entries if e.account == "411MANO"]
        total_debit = round(sum(e.debit for e in entries_411), 2)
        total_credit = round(sum(e.credit for e in entries_411), 2)

        assert total_debit == total_credit, (
            f"411MANO lettrage déséquilibré: D={total_debit}, C={total_credit}"
        )
