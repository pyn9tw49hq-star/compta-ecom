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
        ("decathlon", "62220800", "CDECATHLON"),
    ],
)
class TestMarketplaceCommissionSaleParametrized:
    """Vente nominale paramétrée par marketplace (sans TVA déductible)."""

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


class TestLeroyMerlinCommissionWithTVA:
    """Leroy Merlin : commissions éclatées en HT + TVA déductible + client TTC."""

    def test_sale_produces_three_entries(self, sample_config: AppConfig) -> None:
        """Vente Leroy Merlin : 3 lignes — charge HT + TVA déductible + client TTC."""
        tx = _make_transaction(
            channel="leroy_merlin",
            commission_ttc=-18.00,
            commission_ht=-15.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 3
        # Charge HT au débit
        assert entries[0].account == "62220900"
        assert entries[0].debit == 15.00
        assert entries[0].credit == 0.0
        # TVA déductible au débit
        assert entries[1].account == "44566001"
        assert entries[1].debit == 3.00
        assert entries[1].credit == 0.0
        # Client TTC au crédit
        assert entries[2].account == "411LM"
        assert entries[2].debit == 0.0
        assert entries[2].credit == 18.00

    def test_refund_commission_restituee(self, sample_config: AppConfig) -> None:
        """Remboursement commission Leroy Merlin : client D TTC, charge C HT, TVA C."""
        tx = _make_transaction(
            channel="leroy_merlin",
            type="refund",
            commission_ttc=18.00,
            commission_ht=15.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 3
        # Client TTC au débit
        assert entries[0].account == "411LM"
        assert entries[0].debit == 18.00
        # Charge HT au crédit
        assert entries[1].account == "62220900"
        assert entries[1].credit == 15.00
        # TVA déductible au crédit
        assert entries[2].account == "44566001"
        assert entries[2].credit == 3.00

    def test_sale_balance(self, sample_config: AppConfig) -> None:
        """Équilibre débit/crédit vérifié (vente)."""
        tx = _make_transaction(
            channel="leroy_merlin",
            commission_ttc=-18.00,
            commission_ht=-15.00,
        )
        entries = generate_marketplace_commission(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )

    def test_refund_balance(self, sample_config: AppConfig) -> None:
        """Équilibre débit/crédit vérifié (remboursement)."""
        tx = _make_transaction(
            channel="leroy_merlin",
            type="refund",
            commission_ttc=18.00,
            commission_ht=15.00,
        )
        entries = generate_marketplace_commission(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )

    def test_sale_exact_spec_amounts(self, sample_config: AppConfig) -> None:
        """Vente Leroy Merlin avec montants exacts de la spec : HT=1.02, TTC=1.22."""
        tx = _make_transaction(
            channel="leroy_merlin",
            commission_ttc=-1.22,
            commission_ht=-1.02,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 3
        # Charge HT au débit
        assert entries[0].account == "62220900"
        assert entries[0].debit == 1.02
        assert entries[0].credit == 0.0
        # TVA déductible au débit (1.22 - 1.02 = 0.20)
        assert entries[1].account == "44566001"
        assert entries[1].debit == 0.20
        assert entries[1].credit == 0.0
        # Client TTC au crédit
        assert entries[2].account == "411LM"
        assert entries[2].debit == 0.0
        assert entries[2].credit == 1.22

    def test_lettrage_split(self, sample_config: AppConfig) -> None:
        """Leroy Merlin : charge et TVA sans lettrage, client lettré par payout_reference."""
        tx = _make_transaction(
            channel="leroy_merlin",
            reference="LM-001",
            commission_ttc=-18.00,
            commission_ht=-15.00,
            payout_reference="2025-07-01",
        )
        entries = generate_marketplace_commission(tx, sample_config)

        # Charge au débit → pas de lettrage
        assert entries[0].account == "62220900"
        assert entries[0].lettrage == ""
        # TVA au débit → pas de lettrage
        assert entries[1].account == "44566001"
        assert entries[1].lettrage == ""
        # Client au crédit → lettrage = payout_reference
        assert entries[2].account == "411LM"
        assert entries[2].lettrage == "2025-07-01"


class TestManoManoCommissionWithTVA:
    """ManoMano : commissions éclatées en HT + TVA déductible + client TTC (#14)."""

    def test_sale_produces_three_entries(self, sample_config: AppConfig) -> None:
        """Vente ManoMano : 3 lignes — charge HT + TVA déductible + client TTC."""
        tx = _make_transaction(
            channel="manomano",
            commission_ttc=-18.00,
            commission_ht=-15.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 3
        # Charge HT au débit
        assert entries[0].account == "62220300"
        assert entries[0].debit == 15.00
        assert entries[0].credit == 0.0
        # TVA déductible au débit
        assert entries[1].account == "44566001"
        assert entries[1].debit == 3.00
        assert entries[1].credit == 0.0
        # Client TTC au crédit
        assert entries[2].account == "411MANO"
        assert entries[2].debit == 0.0
        assert entries[2].credit == 18.00

    def test_refund_commission_restituee(self, sample_config: AppConfig) -> None:
        """Remboursement commission ManoMano : client D TTC, charge C HT, TVA C."""
        tx = _make_transaction(
            channel="manomano",
            type="refund",
            commission_ttc=18.00,
            commission_ht=15.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 3
        # Client TTC au débit
        assert entries[0].account == "411MANO"
        assert entries[0].debit == 18.00
        # Charge HT au crédit
        assert entries[1].account == "62220300"
        assert entries[1].credit == 15.00
        # TVA déductible au crédit
        assert entries[2].account == "44566001"
        assert entries[2].credit == 3.00

    def test_sale_balance(self, sample_config: AppConfig) -> None:
        """Équilibre débit/crédit vérifié (vente)."""
        tx = _make_transaction(
            channel="manomano",
            commission_ttc=-18.00,
            commission_ht=-15.00,
        )
        entries = generate_marketplace_commission(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )

    def test_refund_balance(self, sample_config: AppConfig) -> None:
        """Équilibre débit/crédit vérifié (remboursement)."""
        tx = _make_transaction(
            channel="manomano",
            type="refund",
            commission_ttc=18.00,
            commission_ht=15.00,
        )
        entries = generate_marketplace_commission(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )

    def test_sale_exact_spec_amounts(self, sample_config: AppConfig) -> None:
        """Vente ManoMano avec montants exacts : HT=1.02, TTC=1.22."""
        tx = _make_transaction(
            channel="manomano",
            commission_ttc=-1.22,
            commission_ht=-1.02,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 3
        assert entries[0].account == "62220300"
        assert entries[0].debit == 1.02
        assert entries[1].account == "44566001"
        assert entries[1].debit == 0.20
        assert entries[2].account == "411MANO"
        assert entries[2].credit == 1.22

    def test_lettrage_split(self, sample_config: AppConfig) -> None:
        """ManoMano : charge et TVA sans lettrage, client lettré par payout_reference."""
        tx = _make_transaction(
            channel="manomano",
            reference="MM-001",
            commission_ttc=-18.00,
            commission_ht=-15.00,
            payout_reference="PAY-2025-01",
        )
        entries = generate_marketplace_commission(tx, sample_config)

        # Charge au débit → pas de lettrage
        assert entries[0].account == "62220300"
        assert entries[0].lettrage == ""
        # TVA au débit → pas de lettrage
        assert entries[1].account == "44566001"
        assert entries[1].lettrage == ""
        # Client au crédit → lettrage = payout_reference
        assert entries[2].account == "411MANO"
        assert entries[2].lettrage == "PAY-2025-01"

    def test_journal_achats(self, sample_config: AppConfig) -> None:
        """Journal = 'AC' pour les commissions ManoMano (compte de charge configuré)."""
        tx = _make_transaction(commission_ttc=-18.00, commission_ht=-15.00)
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.journal == "AC"


class TestMarketplaceCommissionRefund:
    """Tests des 3 cas refund (AC21) — canal Décathlon (2 écritures, sans TVA déductible)."""

    def test_refund_commission_restituee(self, sample_config: AppConfig) -> None:
        """commission_ttc > 0 (restituée) → client D, charge C."""
        tx = _make_transaction(
            channel="decathlon",
            type="refund",
            commission_ttc=15.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "CDECATHLON"
        assert entries[0].debit == 15.00
        assert entries[0].credit == 0.0
        assert entries[1].account == "62220800"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 15.00

    def test_refund_commission_non_restituee(self, sample_config: AppConfig) -> None:
        """commission_ttc < 0 + type=refund → charge D, client C (même sens que vente)."""
        tx = _make_transaction(
            channel="decathlon",
            type="refund",
            commission_ttc=-12.00,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 2
        assert entries[0].account == "62220800"
        assert entries[0].debit == 12.00
        assert entries[0].credit == 0.0
        assert entries[1].account == "CDECATHLON"
        assert entries[1].debit == 0.0
        assert entries[1].credit == 12.00

    def test_refund_commission_zero(self, sample_config: AppConfig) -> None:
        """commission_ttc == 0.0 → liste vide."""
        tx = _make_transaction(
            channel="decathlon",
            type="refund",
            commission_ttc=0.0,
        )

        entries = generate_marketplace_commission(tx, sample_config)

        assert entries == []

    def test_refund_balance(self, sample_config: AppConfig) -> None:
        """Équilibre vérifié sur refund commission restituée."""
        tx = _make_transaction(channel="decathlon", type="refund", commission_ttc=15.00)
        entries = generate_marketplace_commission(tx, sample_config)
        assert round(sum(e.debit for e in entries), 2) == round(
            sum(e.credit for e in entries), 2
        )

    def test_refund_non_restituee_balance(self, sample_config: AppConfig) -> None:
        """Équilibre vérifié sur refund commission non restituée."""
        tx = _make_transaction(channel="decathlon", type="refund", commission_ttc=-12.00)
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
        """Libellé vente : 'Commission #MM001 ManoMano'."""
        tx = _make_transaction(reference="#MM001", channel="manomano")
        entries = generate_marketplace_commission(tx, sample_config)
        assert entries[0].label == "Commission #MM001 ManoMano"

    def test_label_refund(self, sample_config: AppConfig) -> None:
        """Libellé refund : 'Remb. commission #R001 ManoMano'."""
        tx = _make_transaction(reference="#R001", type="refund", commission_ttc=18.0, commission_ht=15.0)
        entries = generate_marketplace_commission(tx, sample_config)
        assert entries[0].label == "Remb. commission #R001 ManoMano"

    def test_label_refund_non_restituee(self, sample_config: AppConfig) -> None:
        """Refund non restituée : libellé 'Remb. commission' même si commission < 0."""
        tx = _make_transaction(reference="#R002", type="refund", commission_ttc=-18.0, commission_ht=-15.0)
        entries = generate_marketplace_commission(tx, sample_config)
        assert entries[0].label == "Remb. commission #R002 ManoMano"

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

    def test_journal_achats_manomano(self, sample_config: AppConfig) -> None:
        """Journal = 'AC' pour les commissions ManoMano (compte de charge configuré)."""
        tx = _make_transaction(commission_ttc=-18.00)
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.journal == "AC"

    def test_journal_achats_decathlon(self, sample_config: AppConfig) -> None:
        """Journal = 'AC' pour les commissions Decathlon (compte de charge configuré)."""
        tx = _make_transaction(channel="decathlon", commission_ttc=-18.00)
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.journal == "AC"

    def test_journal_achats_leroy_merlin(self, sample_config: AppConfig) -> None:
        """Journal = 'AC' pour les commissions Leroy Merlin (compte de charge configuré)."""
        tx = _make_transaction(
            channel="leroy_merlin", commission_ttc=-18.00, commission_ht=-15.00
        )
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.journal == "AC"

    def test_date(self, sample_config: AppConfig) -> None:
        """Date = date de la transaction."""
        tx = _make_transaction(
            date=datetime.date(2024, 6, 1), commission_ttc=-18.00
        )
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.date == datetime.date(2024, 6, 1)

    def test_piece_number_and_lettrage(self, sample_config: AppConfig) -> None:
        """piece_number = reference ; lettrage par type de compte (charge/TVA vide, client = reference)."""
        tx = _make_transaction(reference="#9999", commission_ttc=-18.00, commission_ht=-15.00)
        entries = generate_marketplace_commission(tx, sample_config)
        for e in entries:
            assert e.piece_number == "#9999"
        # Charge account → pas de lettrage
        assert entries[0].account == "62220300"
        assert entries[0].lettrage == ""
        # TVA → pas de lettrage
        assert entries[1].account == "44566001"
        assert entries[1].lettrage == ""
        # Client → lettrage = reference (fallback, payout_reference is None)
        assert entries[2].account == "411MANO"
        assert entries[2].lettrage == "#9999"


class TestDecathlonLettrageByPayoutCycle:
    """Lettrage CDECATHLON par cycle de paiement (AC-LETTRAGE-DEC)."""

    def test_decathlon_commission_lettrage_split(self, sample_config: AppConfig) -> None:
        """Décathlon : seul CDECATHLON est lettré (payout_reference), compte charge vide."""
        tx = _make_transaction(
            channel="decathlon",
            reference="fr12345-A",
            commission_ttc=-18.00,
            payout_reference="2025-07-01",
            payout_date=datetime.date(2025, 7, 1),
        )
        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 2
        # Compte de charge (62220800) au débit → pas de lettrage
        assert entries[0].account == "62220800"
        assert entries[0].lettrage == ""
        # Client (CDECATHLON) au crédit → lettrage = payout_reference
        assert entries[1].account == "CDECATHLON"
        assert entries[1].lettrage == "2025-07-01"

    def test_decathlon_refund_commission_lettrage_split(self, sample_config: AppConfig) -> None:
        """Décathlon refund : seul CDECATHLON est lettré (payout_reference), compte charge vide."""
        tx = _make_transaction(
            channel="decathlon",
            reference="fr12345-A",
            type="refund",
            commission_ttc=15.00,
            payout_reference="2025-07-01",
            payout_date=datetime.date(2025, 7, 1),
        )
        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 2
        # Client (CDECATHLON) au débit → lettrage = payout_reference
        assert entries[0].account == "CDECATHLON"
        assert entries[0].lettrage == "2025-07-01"
        # Compte de charge (62220800) au crédit → pas de lettrage
        assert entries[1].account == "62220800"
        assert entries[1].lettrage == ""

    def test_decathlon_without_payout_reference(self, sample_config: AppConfig) -> None:
        """Décathlon sans payout_reference → charge vide, client = reference."""
        tx = _make_transaction(
            channel="decathlon",
            reference="fr12345-A",
            commission_ttc=-18.00,
            payout_reference=None,
        )
        entries = generate_marketplace_commission(tx, sample_config)
        # Compte de charge au débit → pas de lettrage
        assert entries[0].account == "62220800"
        assert entries[0].lettrage == ""
        # Client au crédit → lettrage = reference (fallback)
        assert entries[1].account == "CDECATHLON"
        assert entries[1].lettrage == "fr12345-A"

    def test_leroy_merlin_lettrage_split(self, sample_config: AppConfig) -> None:
        """Leroy Merlin : charge/TVA sans lettrage, client lettré par payout_reference."""
        tx = _make_transaction(
            channel="leroy_merlin",
            reference="LM-001",
            commission_ttc=-20.00,
            commission_ht=-16.67,
            payout_reference="2025-07-01",
            payout_date=datetime.date(2025, 7, 1),
        )
        entries = generate_marketplace_commission(tx, sample_config)

        assert len(entries) == 3
        # Charge et TVA sans lettrage
        assert entries[0].account == "62220900"
        assert entries[0].lettrage == ""
        assert entries[1].account == "44566001"
        assert entries[1].lettrage == ""
        # Client avec payout_reference
        assert entries[2].account == "411LM"
        assert entries[2].lettrage == "2025-07-01"
