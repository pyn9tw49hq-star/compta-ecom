"""Tests unitaires pour le module controls/vat_checker."""

from __future__ import annotations

import datetime
import logging

import pytest

from compta_ecom.config.loader import AppConfig, PspConfig
from compta_ecom.controls.vat_checker import VatChecker
from compta_ecom.models import NormalizedTransaction


# --- Helpers ---


def _make_tx(
    *,
    reference: str = "REF001",
    channel: str = "shopify",
    amount_ht: float = 100.0,
    amount_tva: float = 20.0,
    amount_ttc: float = 120.0,
    shipping_ht: float = 0.0,
    shipping_tva: float = 0.0,
    tva_rate: float = 20.0,
    country_code: str = "250",
    special_type: str | None = None,
) -> NormalizedTransaction:
    """Construit une NormalizedTransaction de test."""
    return NormalizedTransaction(
        reference=reference,
        channel=channel,
        date=datetime.date(2024, 1, 15),
        type="sale",
        amount_ht=amount_ht,
        amount_tva=amount_tva,
        amount_ttc=amount_ttc,
        shipping_ht=shipping_ht,
        shipping_tva=shipping_tva,
        tva_rate=tva_rate,
        country_code=country_code,
        commission_ttc=10.0,
        commission_ht=8.33,
        net_amount=110.0,
        payout_date=None,
        payout_reference=None,
        payment_method="card",
        special_type=special_type,
    )


def _make_config(
    vat_table: dict[str, dict[str, object]] | None = None,
) -> AppConfig:
    """Construit un AppConfig de test avec une vat_table."""
    if vat_table is None:
        vat_table = {
            "250": {"name": "France", "rate": 20.0, "alpha2": "FR"},
            "056": {"name": "Belgique", "rate": 21.0, "alpha2": "BE"},
            "974": {"name": "La Réunion", "rate": 0.0, "alpha2": "RE"},
        }
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
        vat_table=vat_table,
    )


# ============================================================
# Tests _check_rate (AC 13)
# ============================================================


class TestCheckRate:
    """Tests pour le contrôle taux TVA vs pays."""

    def test_taux_correct_france(self) -> None:
        """Taux correct France (20.0 vs 20.0) → pas d'anomalie."""
        tx = _make_tx(tva_rate=20.0, country_code="250")
        config = _make_config()
        anomalies = VatChecker._check_rate(tx, config)
        assert anomalies == []

    def test_taux_incorrect_dom_tom(self) -> None:
        """Taux incorrect DOM-TOM (20.0 appliqué, 0.0 attendu) → tva_mismatch."""
        tx = _make_tx(tva_rate=20.0, country_code="974")
        config = _make_config()
        anomalies = VatChecker._check_rate(tx, config)
        assert len(anomalies) == 1
        assert anomalies[0].type == "tva_mismatch"
        assert anomalies[0].severity == "warning"
        assert "974" in anomalies[0].detail

    def test_pays_inconnu(self) -> None:
        """Pays inconnu (country_code='999') → unknown_country avec severity='error'."""
        tx = _make_tx(country_code="999")
        config = _make_config()
        anomalies = VatChecker._check_rate(tx, config)
        assert len(anomalies) == 1
        assert anomalies[0].type == "unknown_country"
        assert anomalies[0].severity == "error"
        assert "999" in anomalies[0].detail

    def test_taux_dans_tolerance(self) -> None:
        """Taux dans la tolérance (20.05 vs 20.0, écart 0.05 < 0.1) → pas d'anomalie."""
        tx = _make_tx(tva_rate=20.05, country_code="250")
        config = _make_config()
        anomalies = VatChecker._check_rate(tx, config)
        assert anomalies == []

    def test_taux_ecart_juste_sous_tolerance(self) -> None:
        """Taux juste sous la tolérance (20.09 vs 20.0, écart = 0.09 < 0.1) → pas d'anomalie."""
        tx = _make_tx(tva_rate=20.09, country_code="250")
        config = _make_config()
        anomalies = VatChecker._check_rate(tx, config)
        assert anomalies == []

    def test_taux_ecart_juste_au_dessus_tolerance(self) -> None:
        """Taux juste au-dessus de la tolérance (20.2 vs 20.0, écart = 0.2 > 0.1) → anomalie."""
        tx = _make_tx(tva_rate=20.2, country_code="250")
        config = _make_config()
        anomalies = VatChecker._check_rate(tx, config)
        assert len(anomalies) == 1
        assert anomalies[0].type == "tva_mismatch"

    def test_special_type_exclu(self) -> None:
        """special_type is not None → exclu par check(), pas d'anomalie."""
        tx = _make_tx(special_type="ADJUSTMENT", tva_rate=99.0, country_code="250")
        config = _make_config()
        # Via check() — la transaction est filtrée
        anomalies = VatChecker.check([tx], config)
        assert anomalies == []

    def test_vat_table_vide(self, caplog: pytest.LogCaptureFixture) -> None:
        """vat_table vide → logger.warning, [] retourné."""
        tx = _make_tx()
        config = _make_config(vat_table={})
        with caplog.at_level(logging.WARNING):
            anomalies = VatChecker.check([tx], config)
        assert anomalies == []
        assert "Table TVA vide" in caplog.text


# ============================================================
# Tests _check_tva_amounts (AC 14)
# ============================================================


class TestCheckTvaAmounts:
    """Tests pour le contrôle montants TVA (TTC × taux / (100 + taux))."""

    def test_tva_correcte(self) -> None:
        """TTC=120, taux=20% → TVA attendue = 120×20/120 = 20€, réelle = 20€ → pas d'anomalie."""
        tx = _make_tx(amount_ttc=120.0, amount_tva=20.0, tva_rate=20.0, shipping_tva=0.0)
        anomalies = VatChecker._check_tva_amounts(tx)
        assert anomalies == []

    def test_tva_incorrecte_article_non_taxable(self) -> None:
        """TTC=108, taux=20% → TVA attendue = 108×20/120 = 18€, réelle = 12.30€ → anomalie."""
        tx = _make_tx(amount_ttc=108.0, amount_tva=12.30, tva_rate=20.0, shipping_tva=0.0)
        anomalies = VatChecker._check_tva_amounts(tx)
        assert len(anomalies) == 1
        assert anomalies[0].type == "tva_amount_mismatch"
        assert "12,30€ constaté" in anomalies[0].detail
        assert "18,00€ attendu" in anomalies[0].detail
        assert "108,00€ TTC / 1,20 × 20%" in anomalies[0].detail

    def test_tva_taux_zero_skip(self) -> None:
        """Taux=0% → pas de vérification, pas d'anomalie."""
        tx = _make_tx(tva_rate=0.0, amount_tva=0.0, shipping_tva=0.0, amount_ttc=100.0)
        anomalies = VatChecker._check_tva_amounts(tx)
        assert anomalies == []

    def test_arrondi_acceptable(self) -> None:
        """TTC=99.99, taux=20% → tolérance 0.01€ respectée → pas d'anomalie.

        expected = round(99.99 × 20 / 120, 2) = 16.67
        actual = 16.66 → |diff| = 0.01 ≤ AMOUNT_TOLERANCE → OK
        """
        tx = _make_tx(amount_ttc=99.99, amount_tva=16.66, tva_rate=20.0, shipping_tva=0.0)
        anomalies = VatChecker._check_tva_amounts(tx)
        assert anomalies == []


# ============================================================
# Tests _check_ttc_coherence (AC 15)
# ============================================================


class TestCheckTtcCoherence:
    """Tests pour le contrôle cohérence TTC."""

    def test_ttc_coherent(self) -> None:
        """amount_ttc = somme composants → pas d'anomalie."""
        tx = _make_tx(amount_ht=100.0, amount_tva=20.0, shipping_ht=10.0, shipping_tva=2.0, amount_ttc=132.0)
        anomalies = VatChecker._check_ttc_coherence(tx)
        assert anomalies == []

    def test_ecart_dans_tolerance(self) -> None:
        """Écart ≤ 0.01€ → dans la tolérance."""
        # expected = 100 + 0 + 20 + 0 = 120.0, actual = 120.005 → |diff| = 0.005 < AMOUNT_TOLERANCE
        tx = _make_tx(amount_ht=100.0, amount_tva=20.0, shipping_ht=0.0, shipping_tva=0.0, amount_ttc=120.005)
        anomalies = VatChecker._check_ttc_coherence(tx)
        assert anomalies == []

    def test_ecart_0_02(self) -> None:
        """Écart 0.02€ → ttc_coherence_mismatch avec detail incluant l'écart."""
        tx = _make_tx(amount_ht=100.0, amount_tva=20.0, shipping_ht=0.0, shipping_tva=0.0, amount_ttc=120.02)
        anomalies = VatChecker._check_ttc_coherence(tx)
        assert len(anomalies) == 1
        assert anomalies[0].type == "ttc_coherence_mismatch"
        assert anomalies[0].severity == "warning"
        assert "écart" in anomalies[0].detail

    def test_sans_shipping(self) -> None:
        """Transaction produit uniquement (shipping=0) → contrôle OK."""
        tx = _make_tx(amount_ht=80.0, amount_tva=16.0, shipping_ht=0.0, shipping_tva=0.0, amount_ttc=96.0)
        anomalies = VatChecker._check_ttc_coherence(tx)
        assert anomalies == []


# ============================================================
# Test multi-canal (AC 16)
# ============================================================


class TestMultiCanal:
    """Test multi-canal avec mix de transactions."""

    def test_mix_canaux_une_seule_anomalie(self) -> None:
        """Mix Shopify FR + Shopify DOM-TOM + ManoMano FR + Décathlon FR.

        Seul Shopify DOM-TOM a un taux incorrect → une seule anomalie.
        """
        config = _make_config()

        transactions = [
            _make_tx(reference="SHOP-FR-001", channel="shopify", tva_rate=20.0, country_code="250"),
            _make_tx(
                reference="SHOP-DOM-001",
                channel="shopify",
                tva_rate=20.0,
                country_code="974",
                amount_ht=100.0,
                amount_tva=20.0,
                amount_ttc=120.0,
            ),
            _make_tx(reference="MANO-FR-001", channel="manomano", tva_rate=20.0, country_code="250"),
            _make_tx(reference="DECA-FR-001", channel="decathlon", tva_rate=20.0, country_code="250"),
        ]

        anomalies = VatChecker.check(transactions, config)

        # Only DOM-TOM has tva_mismatch (20.0 vs expected 0.0)
        assert len(anomalies) == 1
        assert anomalies[0].type == "tva_mismatch"
        assert anomalies[0].channel == "shopify"
        assert anomalies[0].reference == "SHOP-DOM-001"


# ============================================================
# Test refund identique à sale (AC 9)
# ============================================================


class TestRefundIdentique:
    """Test que les refunds sont traités identiquement aux ventes."""

    def test_refund_meme_controle_que_sale(self) -> None:
        """Un refund avec taux incorrect produit la même anomalie qu'une vente."""
        config = _make_config()
        tx_sale = NormalizedTransaction(
            reference="SALE-001",
            channel="shopify",
            date=datetime.date(2024, 1, 15),
            type="sale",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=120.0,
            shipping_ht=0.0,
            shipping_tva=0.0,
            tva_rate=20.0,
            country_code="974",
            commission_ttc=10.0,
            commission_ht=8.33,
            net_amount=110.0,
            payout_date=None,
            payout_reference=None,
            payment_method="card",
            special_type=None,
        )
        tx_refund = NormalizedTransaction(
            reference="REFUND-001",
            channel="shopify",
            date=datetime.date(2024, 1, 15),
            type="refund",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=120.0,
            shipping_ht=0.0,
            shipping_tva=0.0,
            tva_rate=20.0,
            country_code="974",
            commission_ttc=10.0,
            commission_ht=8.33,
            net_amount=110.0,
            payout_date=None,
            payout_reference=None,
            payment_method="card",
            special_type=None,
        )

        anomalies_sale = VatChecker.check([tx_sale], config)
        anomalies_refund = VatChecker.check([tx_refund], config)

        assert len(anomalies_sale) == len(anomalies_refund) == 1
        assert anomalies_sale[0].type == anomalies_refund[0].type == "tva_mismatch"


# ============================================================
# Tests paramétrés (AC 17)
# ============================================================


@pytest.mark.parametrize(
    ("country_code", "tva_rate", "expected_anomaly_type"),
    [
        ("250", 20.0, None),  # FR 20% — correct
        ("056", 21.0, None),  # BE 21% — correct
        ("974", 0.0, None),  # DOM-TOM 0% — correct
        ("999", 20.0, "unknown_country"),  # Pays inconnu
    ],
    ids=["FR-20%", "BE-21%", "DOM-TOM-0%", "pays-inconnu"],
)
def test_parametrize_pays_taux(
    country_code: str,
    tva_rate: float,
    expected_anomaly_type: str | None,
) -> None:
    """Tests paramétrés : variations de pays/taux."""
    tx = _make_tx(
        tva_rate=tva_rate,
        country_code=country_code,
        amount_ht=100.0,
        amount_tva=round(100.0 * tva_rate / 100, 2),
        amount_ttc=round(100.0 + 100.0 * tva_rate / 100, 2),
    )
    config = _make_config()
    anomalies = VatChecker.check([tx], config)

    if expected_anomaly_type is None:
        assert anomalies == []
    else:
        assert len(anomalies) == 1
        assert anomalies[0].type == expected_anomaly_type
