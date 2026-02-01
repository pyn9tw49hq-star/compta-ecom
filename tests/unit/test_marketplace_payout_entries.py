"""Tests pour engine/marketplace_payout_entries.py — reversements marketplace."""

from __future__ import annotations

import datetime
import logging

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.marketplace_payout_entries import generate_marketplace_payout
from compta_ecom.models import BalanceError, NormalizedTransaction


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
        """special_type is not None + payout_date is None → [] + logger.warning."""
        tx = _make_transaction(
            special_type="SUBSCRIPTION",
            payout_date=None,
        )
        with caplog.at_level(logging.WARNING):
            entries = generate_marketplace_payout(tx, sample_config)

        assert entries == []
        assert "sans payout_date" in caplog.text


class TestSpecialTypes:
    """Tests des lignes spéciales."""

    def test_adjustment(self, sample_config: AppConfig) -> None:
        """ADJUSTMENT : 51200000 D, 51150002 C."""
        tx = _make_transaction(
            special_type="ADJUSTMENT",
            net_amount=50.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "51200000"
        assert entries[0].debit == 50.0
        assert entries[1].account == "51150002"
        assert entries[1].credit == 50.0

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
        """SUBSCRIPTION ManoMano : FMANO D, 51200000 C."""
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
        assert entries[1].account == "51200000"
        assert entries[1].credit == 100.0

    def test_subscription_decathlon(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION Décathlon : FDECATHLON D, 51200000 C."""
        tx = _make_transaction(
            channel="decathlon",
            special_type="SUBSCRIPTION",
            net_amount=-70.0,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "FDECATHLON"
        assert entries[0].debit == 70.0
        assert entries[1].account == "51200000"
        assert entries[1].credit == 70.0

    def test_subscription_leroy_merlin(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION Leroy Merlin : FADEO D, 51200000 C."""
        tx = _make_transaction(
            channel="leroy_merlin",
            special_type="SUBSCRIPTION",
            net_amount=-46.80,
            commission_ttc=0.0,
            commission_ht=None,
        )
        entries = generate_marketplace_payout(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "FADEO"
        assert entries[0].debit == 46.80
        assert entries[1].account == "51200000"
        assert entries[1].credit == 46.80

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
        """Date de l'écriture = payout_date."""
        payout_date = datetime.date(2024, 2, 10)
        tx = _make_transaction(payout_date=payout_date)
        entries = generate_marketplace_payout(tx, sample_config)
        assert all(e.date == payout_date for e in entries)

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
