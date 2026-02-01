"""Tests pour engine/marketplace_entries.py — écritures de commission marketplace."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.marketplace_entries import generate_marketplace_commission
from compta_ecom.models import BalanceError, NormalizedTransaction


def _make_transaction(**overrides: object) -> NormalizedTransaction:
    """Helper pour construire une NormalizedTransaction avec des valeurs par défaut."""
    defaults: dict[str, object] = {
        "reference": "#MM001",
        "channel": "manomano",
        "date": datetime.date(2024, 3, 15),
        "type": "sale",
        "amount_ht": 100.0,
        "amount_tva": 20.0,
        "amount_ttc": 120.0,
        "shipping_ht": 0.0,
        "shipping_tva": 0.0,
        "tva_rate": 20.0,
        "country_code": "250",
        "commission_ttc": -18.00,
        "commission_ht": 15.00,
        "net_amount": 102.0,
        "payout_date": None,
        "payout_reference": None,
        "payment_method": None,
        "special_type": None,
    }
    defaults.update(overrides)
    return NormalizedTransaction(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("channel", "fournisseur_account", "client_account"),
    [
        ("manomano", "FMANO", "411MANO"),
        ("decathlon", "FDECATHLON", "411DECA"),
        ("leroy_merlin", "FADEO", "411LM"),
    ],
)
class TestMarketplaceCommissionSaleParametrized:
    """Vente nominale paramétrée par marketplace."""

    def test_sale_produces_two_entries(
        self,
        sample_config: AppConfig,
        channel: str,
        fournisseur_account: str,
        client_account: str,
    ) -> None:
        """Vente nominale : 2 lignes, 401 D + 411 C, équilibre."""
        tx = _make_transaction(
            channel=channel,
            commission_ttc=-18.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == fournisseur_account
        assert entries[0].debit == 18.00
        assert entries[0].credit == 0.0
        assert entries[1].account == client_account
        assert entries[1].debit == 0.0
        assert entries[1].credit == 18.00

    def test_sale_balance(
        self,
        sample_config: AppConfig,
        channel: str,
        fournisseur_account: str,
        client_account: str,
    ) -> None:
        """Équilibre débit/crédit vérifié."""
        tx = _make_transaction(channel=channel, commission_ttc=-18.00)
        entries = generate_marketplace_commission(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )


class TestMarketplaceCommissionRefund:
    """Tests des 3 cas refund (AC21)."""

    def test_refund_commission_restituee(self, sample_config: AppConfig) -> None:
        """commission_ttc > 0 (restituée) → 411 D, 401 C."""
        tx = _make_transaction(
            type="refund",
            commission_ttc=15.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "411MANO"
        assert entries[0].debit == 15.00
        assert entries[0].credit == 0.0
        assert entries[1].account == "FMANO"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 15.00

    def test_refund_commission_non_restituee(self, sample_config: AppConfig) -> None:
        """commission_ttc < 0 + type=refund → 401 D, 411 C (même sens que vente)."""
        tx = _make_transaction(
            type="refund",
            commission_ttc=-12.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "FMANO"
        assert entries[0].debit == 12.00
        assert entries[0].credit == 0.0
        assert entries[1].account == "411MANO"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 12.00

    def test_refund_commission_zero(self, sample_config: AppConfig) -> None:
        """commission_ttc == 0.0 → liste vide."""
        tx = _make_transaction(
            type="refund",
            commission_ttc=0.0,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert entries == []

    def test_refund_balance(self, sample_config: AppConfig) -> None:
        """Équilibre vérifié sur refund commission restituée."""
        tx = _make_transaction(type="refund", commission_ttc=15.00)
        entries = generate_marketplace_commission(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )

    def test_refund_non_restituee_balance(self, sample_config: AppConfig) -> None:
        """Équilibre vérifié sur refund commission non restituée."""
        tx = _make_transaction(type="refund", commission_ttc=-12.00)
        entries = generate_marketplace_commission(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )


class TestMarketplaceCommissionZero:
    """commission_ttc == 0 → liste vide."""

    def test_zero_commission_empty(self, sample_config: AppConfig) -> None:
        """commission_ttc == 0.0 → aucune écriture."""
        tx = _make_transaction(commission_ttc=0.0)
        entries = generate_marketplace_commission(tx, sample_config)
        assert entries == []


class TestMarketplaceCommissionBalanceError:
    """BalanceError si déséquilibre forcé."""

    def test_balance_error_on_forced_imbalance(self, sample_config: AppConfig) -> None:
        """Monkey-patch verify_balance pour vérifier qu'il est appelé."""
        tx = _make_transaction(commission_ttc=-18.00)

        with patch(
            "compta_ecom.engine.marketplace_entries.verify_balance",
            side_effect=BalanceError("forced"),
        ):
            with pytest.raises(BalanceError, match="forced"):
                generate_marketplace_commission(tx, sample_config)


class TestMarketplaceCommissionLabels:
    """Vérification des libellés."""

    def test_label_sale(self, sample_config: AppConfig) -> None:
        """Libellé vente : 'Commission #MM001 Manomano'."""
        tx = _make_transaction(reference="#MM001", channel="manomano")
        entries = generate_marketplace_commission(tx, sample_config)
        assert entries[0].label == "Commission #MM001 Manomano"

    def test_label_refund(self, sample_config: AppConfig) -> None:
        """Libellé refund : 'Remb. commission #R001 Manomano'."""
        tx = _make_transaction(reference="#R001", type="refund", commission_ttc=10.0)
        entries = generate_marketplace_commission(tx, sample_config)
        assert entries[0].label == "Remb. commission #R001 Manomano"

    def test_label_refund_non_restituee(self, sample_config: AppConfig) -> None:
        """Refund non restituée : libellé 'Remb. commission' même si commission > 0."""
        tx = _make_transaction(reference="#R002", type="refund", commission_ttc=-12.0)
        entries = generate_marketplace_commission(tx, sample_config)
        assert entries[0].label == "Remb. commission #R002 Manomano"

    def test_label_multiword_channel(self, sample_config: AppConfig) -> None:
        """Canal multi-mots : 'leroy_merlin' → 'Leroy Merlin'."""
        tx = _make_transaction(
            channel="leroy_merlin", commission_ttc=-20.0, reference="#LM001"
        )
        entries = generate_marketplace_commission(tx, sample_config)
        assert entries[0].label == "Commission #LM001 Leroy Merlin"


class TestMarketplaceCommissionMetadata:
    """Vérification des métadonnées d'écriture."""

    def test_entry_type_commission(self, sample_config: AppConfig) -> None:
        """entry_type='commission' sur les deux lignes."""
        tx = _make_transaction(commission_ttc=-18.00)
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.entry_type == "commission"

    def test_journal_reglement(self, sample_config: AppConfig) -> None:
        """Journal = 'RG'."""
        tx = _make_transaction(commission_ttc=-18.00)
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.journal == "RG"

    def test_date(self, sample_config: AppConfig) -> None:
        """Date = date de la transaction."""
        tx = _make_transaction(
            date=datetime.date(2024, 6, 1), commission_ttc=-18.00
        )
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.date == datetime.date(2024, 6, 1)

    def test_piece_number_and_lettrage(self, sample_config: AppConfig) -> None:
        """piece_number et lettrage = reference."""
        tx = _make_transaction(reference="#9999", commission_ttc=-18.00)
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.piece_number == "#9999"
            assert e.lettrage == "#9999"
