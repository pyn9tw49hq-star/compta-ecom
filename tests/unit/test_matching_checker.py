"""Tests unitaires pour le module controls/matching_checker."""

from __future__ import annotations

import datetime

import pytest

from compta_ecom.config.loader import AppConfig, PspConfig
from compta_ecom.controls.matching_checker import MatchingChecker
from compta_ecom.models import NormalizedTransaction


# --- Helpers ---


def _make_tx(
    *,
    reference: str = "#1118",
    channel: str = "shopify",
    tx_type: str = "sale",
    amount_ht: float = 100.0,
    amount_tva: float = 20.0,
    amount_ttc: float = 120.0,
    shipping_ht: float = 5.0,
    shipping_tva: float = 1.0,
    tva_rate: float = 20.0,
    country_code: str = "250",
    commission_ttc: float = 3.50,
    commission_ht: float | None = None,
    net_amount: float = 116.50,
    payout_date: datetime.date | None = datetime.date(2026, 1, 17),
    payout_reference: str | None = "PAY-001",
    payment_method: str | None = "card",
    special_type: str | None = None,
) -> NormalizedTransaction:
    """Construit une NormalizedTransaction de test pour le MatchingChecker."""
    return NormalizedTransaction(
        reference=reference,
        channel=channel,
        date=datetime.date(2026, 1, 15),
        type=tx_type,
        amount_ht=amount_ht,
        amount_tva=amount_tva,
        amount_ttc=amount_ttc,
        shipping_ht=shipping_ht,
        shipping_tva=shipping_tva,
        tva_rate=tva_rate,
        country_code=country_code,
        commission_ttc=commission_ttc,
        commission_ht=commission_ht,
        net_amount=net_amount,
        payout_date=payout_date,
        payout_reference=payout_reference,
        payment_method=payment_method,
        special_type=special_type,
    )


def _make_config(
    *,
    matching_tolerance: float = 0.01,
) -> AppConfig:
    """Construit un AppConfig de test."""
    return AppConfig(
        clients={"shopify": "411SHOPIFY"},
        fournisseurs={"manomano": "FMANO"},
        psp={"card": PspConfig(compte="51150007")},
        transit="58000000",
        banque="512",
        comptes_speciaux={},
        comptes_vente_prefix="707",
        canal_codes={"shopify": "01"},
        comptes_tva_prefix="4457",
        vat_table={"250": {"name": "France", "rate": 20.0, "alpha2": "FR"}},
        matching_tolerance=matching_tolerance,
    )


# --- Happy path ---


class TestHappyPath:
    def test_valid_transactions_no_anomalies(self) -> None:
        """Liste de transactions valides → check() retourne []."""
        config = _make_config()
        # Sale cohérente, payout présent
        sale = _make_tx()
        # Refund cohérent avec vente correspondante
        refund = _make_tx(
            reference="#1118",
            tx_type="refund",
            commission_ttc=-3.50,
            net_amount=-116.50,
            amount_ttc=120.0,
        )
        result = MatchingChecker.check([sale, refund], config)
        assert result == []

    def test_empty_list(self) -> None:
        """Liste vide → retourne []."""
        config = _make_config()
        assert MatchingChecker.check([], config) == []


# --- Tests cohérence montant (contrôle 1) ---


class TestAmountCoherence:
    def test_sale_coherente(self) -> None:
        """Sale: abs(3.50 + 116.50) = 120.0 = amount_ttc → pas d'anomalie."""
        config = _make_config()
        tx = _make_tx()
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert result == []

    def test_refund_commission_restituee(self) -> None:
        """Refund commission restituée: abs(-3.50 + -116.50) = 120.0 = amount_ttc."""
        config = _make_config()
        tx = _make_tx(
            tx_type="refund",
            commission_ttc=-3.50,
            net_amount=-116.50,
            amount_ttc=120.0,
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert result == []

    def test_refund_commission_non_restituee(self) -> None:
        """Refund commission non restituée: abs(3.50 + -120.0) = 116.50 = amount_ttc."""
        config = _make_config()
        tx = _make_tx(
            tx_type="refund",
            commission_ttc=3.50,
            net_amount=-120.0,
            amount_ttc=116.50,
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert result == []

    def test_detail_format_refund_montants_negatifs(self) -> None:
        """Vérifier le format detail pour refund avec montants négatifs et écart."""
        config = _make_config()
        tx = _make_tx(
            tx_type="refund",
            commission_ttc=-3.50,
            net_amount=-115.50,
            amount_ttc=120.0,  # expected = abs(-3.50 + -115.50) = 119.0 → écart 1.0
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert len(result) == 1
        assert "commission (-3.5€)" in result[0].detail
        assert "net (-115.5€)" in result[0].detail
        assert "119.0€" in result[0].detail
        assert "écart de 1.0€" in result[0].detail

    def test_ecart_superieur_tolerance(self) -> None:
        """Écart > tolérance → amount_mismatch."""
        config = _make_config()
        tx = _make_tx(
            commission_ttc=3.50,
            net_amount=115.50,
            amount_ttc=120.0,  # expected = 119.0, écart = 1.0
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert len(result) == 1
        assert result[0].type == "amount_mismatch"
        assert result[0].severity == "warning"
        assert result[0].reference == "#1118"
        assert result[0].channel == "shopify"
        assert result[0].expected_value == "119.0"
        assert result[0].actual_value == "120.0"

    def test_ecart_exactement_tolerance(self) -> None:
        """Écart exactement 0.01€ = tolérance par défaut → dans la tolérance."""
        config = _make_config()
        tx = _make_tx(
            commission_ttc=3.50,
            net_amount=116.49,
            amount_ttc=120.0,  # expected = 119.99, diff = 0.01
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert result == []

    def test_ecart_juste_au_dessus_tolerance(self) -> None:
        """Écart 0.02€ > tolérance 0.01€ → anomalie détectée."""
        config = _make_config()
        tx = _make_tx(
            commission_ttc=3.50,
            net_amount=116.48,
            amount_ttc=120.0,  # expected = 119.98, diff = 0.02
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert len(result) == 1
        assert result[0].type == "amount_mismatch"

    def test_transaction_nulle(self) -> None:
        """Transaction nulle (tous à 0.0) → pas d'anomalie."""
        config = _make_config()
        tx = _make_tx(
            amount_ttc=0.0,
            commission_ttc=0.0,
            net_amount=0.0,
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert result == []

    def test_transaction_orpheline_parser(self) -> None:
        """Shopify mode dégradé: commission=0, net=ttc → pas de fausse anomalie."""
        config = _make_config()
        tx = _make_tx(
            commission_ttc=0.0,
            net_amount=120.0,
            amount_ttc=120.0,
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert result == []

    def test_special_type_exclu(self) -> None:
        """special_type is not None → exclu du contrôle (via check())."""
        config = _make_config()
        tx = _make_tx(
            special_type="ADJUSTMENT",
            commission_ttc=0.0,
            net_amount=50.0,
            amount_ttc=0.0,  # incohérent mais exclu
        )
        result = MatchingChecker.check([tx], config)
        assert result == []

    def test_tolerance_custom(self) -> None:
        """matching_tolerance=0.05 → écart 0.03€ toléré."""
        config = _make_config(matching_tolerance=0.05)
        tx = _make_tx(
            commission_ttc=3.50,
            net_amount=116.47,
            amount_ttc=120.0,  # expected = 119.97, diff = 0.03
        )
        result = MatchingChecker._check_amount_coherence(tx, config)
        assert result == []


@pytest.mark.parametrize(
    "commission_ttc,net_amount,amount_ttc,expected_anomalies",
    [
        # Sale cohérente
        (3.50, 116.50, 120.0, 0),
        # Refund commission restituée
        (-3.50, -116.50, 120.0, 0),
        # Refund commission non restituée
        (3.50, -120.0, 116.50, 0),
        # Écart toléré (exactement 0.01)
        (3.50, 116.49, 120.0, 0),
        # Écart hors tolérance
        (3.50, 115.50, 120.0, 1),
        # Montant nul
        (0.0, 0.0, 0.0, 0),
    ],
    ids=[
        "sale-coherente",
        "refund-commission-restituee",
        "refund-commission-non-restituee",
        "ecart-tolere",
        "ecart-hors-tolerance",
        "montant-nul",
    ],
)
def test_parametrize_coherence_montant(
    commission_ttc: float,
    net_amount: float,
    amount_ttc: float,
    expected_anomalies: int,
) -> None:
    config = _make_config()
    tx = _make_tx(
        commission_ttc=commission_ttc,
        net_amount=net_amount,
        amount_ttc=amount_ttc,
    )
    result = MatchingChecker._check_amount_coherence(tx, config)
    assert len(result) == expected_anomalies


# --- Tests couverture payout (contrôle 2) ---


class TestPayoutCoverage:
    def test_payout_date_present(self) -> None:
        """Transaction avec payout_date peuplé → pas d'anomalie."""
        tx = _make_tx(payout_date=datetime.date(2026, 1, 17))
        result = MatchingChecker._check_payout_coverage(tx)
        assert result == []

    def test_payout_date_none(self) -> None:
        """Transaction avec payout_date=None → missing_payout severity=info."""
        tx = _make_tx(payout_date=None)
        result = MatchingChecker._check_payout_coverage(tx)
        assert len(result) == 1
        assert result[0].type == "missing_payout"
        assert result[0].severity == "info"
        assert result[0].reference == "#1118"

    def test_special_type_exclu(self) -> None:
        """special_type is not None → exclu (via check())."""
        config = _make_config()
        tx = _make_tx(
            special_type="ADJUSTMENT",
            payout_date=None,
        )
        result = MatchingChecker.check([tx], config)
        missing_payouts = [a for a in result if a.type == "missing_payout"]
        assert len(missing_payouts) == 0

    def test_sale_et_refund_sans_payout(self) -> None:
        """Sale et refund sans payout → les deux signalés."""
        config = _make_config()
        sale = _make_tx(payout_date=None, reference="#1001")
        refund = _make_tx(
            tx_type="refund",
            payout_date=None,
            reference="#1001",
            commission_ttc=-3.50,
            net_amount=-116.50,
        )
        result = MatchingChecker.check([sale, refund], config)
        missing_payouts = [a for a in result if a.type == "missing_payout"]
        assert len(missing_payouts) == 2


# --- Tests matching refund ↔ vente (contrôle 3) ---


class TestRefundMatching:
    def test_refund_avec_vente(self) -> None:
        """Refund avec vente correspondante → pas d'anomalie."""
        sale = _make_tx(reference="#1001")
        refund = _make_tx(
            reference="#1001",
            tx_type="refund",
            commission_ttc=-3.50,
            net_amount=-116.50,
        )
        result = MatchingChecker._check_refund_matching([sale, refund])
        assert result == []

    def test_refund_sans_vente(self) -> None:
        """Refund sans vente correspondante → orphan_refund."""
        refund = _make_tx(
            reference="#9999",
            tx_type="refund",
            commission_ttc=-3.50,
            net_amount=-116.50,
        )
        result = MatchingChecker._check_refund_matching([refund])
        assert len(result) == 1
        assert result[0].type == "orphan_refund"
        assert result[0].severity == "warning"
        assert result[0].reference == "#9999"
        assert "#9999" in result[0].detail

    def test_sale_sans_refund(self) -> None:
        """Sale sans refund → pas d'anomalie (normal)."""
        sale = _make_tx(reference="#1001")
        result = MatchingChecker._check_refund_matching([sale])
        assert result == []

    def test_special_type_refund_sans_vente(self) -> None:
        """Refund avec special_type sans vente → orphan_refund (inclus)."""
        refund = _make_tx(
            reference="#8888",
            tx_type="refund",
            special_type="ADJUSTMENT",
        )
        result = MatchingChecker._check_refund_matching([refund])
        assert len(result) == 1
        assert result[0].type == "orphan_refund"

    def test_plusieurs_refunds_meme_vente(self) -> None:
        """Plusieurs refunds pour la même vente → pas d'anomalie."""
        sale = _make_tx(reference="#1001")
        refund1 = _make_tx(
            reference="#1001",
            tx_type="refund",
            commission_ttc=-1.50,
            net_amount=-50.0,
            amount_ttc=51.50,
        )
        refund2 = _make_tx(
            reference="#1001",
            tx_type="refund",
            commission_ttc=-2.00,
            net_amount=-66.50,
            amount_ttc=68.50,
        )
        result = MatchingChecker._check_refund_matching([sale, refund1, refund2])
        assert result == []

    def test_refund_canal_sans_vente_ce_canal(self) -> None:
        """Refund d'un canal sans aucune vente de ce canal → orphan_refund."""
        sale_shopify = _make_tx(reference="#1001", channel="shopify")
        refund_manomano = _make_tx(
            reference="#2001",
            channel="manomano",
            tx_type="refund",
            commission_ttc=-5.0,
            net_amount=-95.0,
            amount_ttc=100.0,
        )
        result = MatchingChecker._check_refund_matching([sale_shopify, refund_manomano])
        assert len(result) == 1
        assert result[0].channel == "manomano"


# --- Test d'orchestration et multi-canal ---


class TestOrchestration:
    def test_trois_types_anomalies_simultanement(self) -> None:
        """Liste déclenchant les 3 types d'anomalies → vérifier présence et nombre exact."""
        config = _make_config()

        # amount_mismatch: incohérence montant
        tx_mismatch = _make_tx(
            reference="#2001",
            commission_ttc=3.50,
            net_amount=115.50,
            amount_ttc=120.0,  # expected = 119.0 → écart 1.0
        )
        # missing_payout: payout_date=None
        tx_no_payout = _make_tx(
            reference="#2002",
            payout_date=None,
        )
        # orphan_refund: refund sans vente correspondante
        tx_orphan_refund = _make_tx(
            reference="#9999",
            tx_type="refund",
            commission_ttc=-3.50,
            net_amount=-116.50,
            amount_ttc=120.0,
            payout_date=None,
        )

        result = MatchingChecker.check(
            [tx_mismatch, tx_no_payout, tx_orphan_refund], config
        )

        types = {a.type for a in result}
        assert "amount_mismatch" in types
        assert "missing_payout" in types
        assert "orphan_refund" in types

        # Nombre exact: 1 amount_mismatch + 2 missing_payout (tx_no_payout + tx_orphan_refund)
        # + 1 orphan_refund = 4
        # tx_orphan_refund also has amount_mismatch? abs(-3.50 + -116.50) = 120.0 = amount_ttc → coherent
        # tx_no_payout: abs(3.50 + 116.50) = 120.0 → coherent, but missing payout
        assert len(result) == 4

    def test_multi_canal(self) -> None:
        """Transactions multi-canal → vérifier channel et reference corrects."""
        config = _make_config()

        shopify_sale = _make_tx(reference="#S001", channel="shopify")
        manomano_sale = _make_tx(
            reference="#M001",
            channel="manomano",
            payout_date=None,
        )
        mirakl_refund = _make_tx(
            reference="#K001",
            channel="mirakl",
            tx_type="refund",
            commission_ttc=-3.50,
            net_amount=-116.50,
            amount_ttc=120.0,
        )

        result = MatchingChecker.check(
            [shopify_sale, manomano_sale, mirakl_refund], config
        )

        # manomano_sale → missing_payout
        missing = [a for a in result if a.type == "missing_payout"]
        assert len(missing) == 1
        assert missing[0].channel == "manomano"
        assert missing[0].reference == "#M001"

        # mirakl_refund → orphan_refund (no sale with #K001)
        orphans = [a for a in result if a.type == "orphan_refund"]
        assert len(orphans) == 1
        assert orphans[0].channel == "mirakl"
        assert orphans[0].reference == "#K001"
