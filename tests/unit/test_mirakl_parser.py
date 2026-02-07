"""Tests pour le parser Mirakl (Décathlon & Leroy Merlin)."""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest

from compta_ecom.parsers.mirakl import MiraklParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Table TVA simplifiée pour les tests
_TEST_VAT_TABLE: dict[str, dict[str, Any]] = {
    "250": {"name": "France", "rate": 20.0, "alpha2": "FR"},
    "056": {"name": "Belgique", "rate": 21.0, "alpha2": "BE"},
}

_TEST_ALPHA2_TO_NUMERIC: dict[str, str] = {
    "FR": "250",
    "BE": "056",
}


def _make_order_df(rows: list[dict]) -> pd.DataFrame:
    """Construit un DataFrame pré-filtré ORDER_LINE_TYPES avec dates parsées."""
    df = pd.DataFrame(rows)
    df["Montant"] = pd.to_numeric(df["Montant"], errors="coerce")
    df["Date de commande"] = pd.to_datetime(df["Date de commande"], format="%Y-%m-%d", errors="coerce")
    df["Date du cycle de paiement"] = pd.to_datetime(
        df.get("Date du cycle de paiement", pd.Series(dtype="object")),
        format="%Y-%m-%d",
        errors="coerce",
    )
    return df


def _aggregate_orders_helper(
    parser: MiraklParser,
    df: pd.DataFrame,
    tva_rate: float = 20.0,
    country_code: str = "250",
    amounts_are_ttc: bool = False,
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Helper pour appeler _aggregate_orders avec les paramètres par défaut."""
    return parser._aggregate_orders(
        df,
        default_tva_rate=tva_rate,
        default_country_code=country_code,
        vat_table=_TEST_VAT_TABLE,
        alpha2_to_numeric=_TEST_ALPHA2_TO_NUMERIC,
        amounts_are_ttc=amounts_are_ttc,
    )


# ---------------------------------------------------------------------------
# TestMiraklAggregation
# ---------------------------------------------------------------------------


class TestMiraklAggregation:
    """Tests pour _aggregate_orders()."""

    def test_complete_order_4_lines(self) -> None:
        """Commande complète avec 4 types de lignes."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD001", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD001", "Type": "Frais de port", "Date de commande": "2026-01-15",
             "Montant": 10.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD001", "Type": "Commission", "Date de commande": "2026-01-15",
             "Montant": -15.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD001", "Type": "Taxe sur la commission", "Date de commande": "2026-01-15",
             "Montant": -3.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert len(orders) == 1
        assert len(anomalies) == 0
        o = orders[0]
        assert o["reference"] == "CMD001"
        assert o["type"] == "sale"
        assert o["amount_ht"] == 100.00
        assert o["shipping_ht"] == 10.00
        assert o["commission_ht"] == -15.00
        assert o["commission_ttc"] == -18.00  # -15 + -3
        assert o["amount_tva"] == 20.00  # 100 * 20/100
        assert o["shipping_tva"] == 2.00  # 10 * 20/100
        assert o["amount_ttc"] == 132.00  # 100 + 10 + 20 + 2
        assert o["net_amount"] == 150.00  # 132 - (-18)
        assert o["country_code"] == "250"
        assert o["tva_rate"] == 20.0
        # Payout date extraite des lignes commande
        assert o["payout_date"] == datetime.date(2026, 1, 20)
        assert o["payout_reference"] == "2026-01-20"

    def test_payout_date_missing_returns_none(self) -> None:
        """Commande sans Date du cycle de paiement → payout_date=None."""
        df = _make_order_df([
            {"Numéro de commande": "CMD-NOPAY", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 50.00},
        ])
        parser = MiraklParser(channel="decathlon")
        orders, _ = _aggregate_orders_helper(parser, df)
        assert orders[0]["payout_date"] is None
        assert orders[0]["payout_reference"] is None

    def test_multi_article_same_order(self) -> None:
        """2 lignes Montant pour la même commande → somme correcte."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD002", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 50.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD002", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 30.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert len(orders) == 1
        assert orders[0]["amount_ht"] == 80.00

    def test_two_distinct_orders(self) -> None:
        """2 commandes distinctes → 2 dicts."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD003", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD004", "Type": "Montant", "Date de commande": "2026-01-16",
             "Montant": 200.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert len(orders) == 2
        refs = {o["reference"] for o in orders}
        assert refs == {"CMD003", "CMD004"}

    def test_order_without_shipping(self) -> None:
        """Commande sans frais de port → shipping_ht=0.00, shipping_tva=0.00."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD005", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert orders[0]["shipping_ht"] == 0.00
        assert orders[0]["shipping_tva"] == 0.00

    def test_order_without_commission(self) -> None:
        """Commande sans commission → commission_ht=0.00, commission_ttc=0.00."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD006", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert orders[0]["commission_ht"] == 0.00
        assert orders[0]["commission_ttc"] == 0.00

    def test_refund_negative_montant(self) -> None:
        """Refund (montant négatif) → type=refund, montants positifs (abs), net négatif."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD007", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": -100.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD007", "Type": "Commission", "Date de commande": "2026-01-15",
             "Montant": 15.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD007", "Type": "Taxe sur la commission", "Date de commande": "2026-01-15",
             "Montant": 3.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        o = orders[0]
        assert o["type"] == "refund"
        assert o["amount_ht"] == 100.00  # abs
        assert o["commission_ht"] == 15.00  # signé positif (refund, commission non restituée)
        assert o["commission_ttc"] == 18.00
        # signed_ttc = -120, net = -120 - 18 = -138
        assert o["net_amount"] == -138.00

    def test_refund_commission_not_refunded(self) -> None:
        """Refund avec commission non restituée → net encore plus négatif."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD008", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": -50.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD008", "Type": "Commission", "Date de commande": "2026-01-15",
             "Montant": 5.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        o = orders[0]
        assert o["type"] == "refund"
        # amount_ttc = 50 + 0 + 10 + 0 = 60
        # signed_ttc = -60, commission_ttc = 5
        # net = -60 - 5 = -65
        assert o["net_amount"] == -65.00

    def test_montant_zero_shipping_positive(self) -> None:
        """montant_sum=0, frais_port > 0 → type=sale."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD009", "Type": "Frais de port", "Date de commande": "2026-01-15",
             "Montant": 10.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert orders[0]["type"] == "sale"

    def test_montant_zero_shipping_negative(self) -> None:
        """montant_sum=0, frais_port < 0 → type=refund."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD010", "Type": "Frais de port", "Date de commande": "2026-01-15",
             "Montant": -10.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert orders[0]["type"] == "refund"

    def test_montant_zero_shipping_zero_anomaly(self) -> None:
        """montant_sum=0, frais_port=0 → Anomaly(type=zero_amount_order)."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD011", "Type": "Commission", "Date de commande": "2026-01-15",
             "Montant": -5.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert len(orders) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "zero_amount_order"

    def test_tva_calculation(self) -> None:
        """TVA calculée : amount_ht=100, tva_rate=20 → amount_tva=20.00."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD012", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert orders[0]["amount_tva"] == 20.00

    def test_net_amount_sale(self) -> None:
        """net_amount sale : amount_ttc=120, commission_ttc=10 → net=110."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD013", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD013", "Type": "Commission", "Date de commande": "2026-01-15",
             "Montant": -10.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        o = orders[0]
        # amount_ttc = 100 + 0 + 20 + 0 = 120
        # commission_ttc = -10 + 0 = -10
        # net = 120 - (-10) = 130
        assert o["amount_ttc"] == 120.00
        assert o["commission_ttc"] == -10.00
        assert o["net_amount"] == 130.00

    def test_net_amount_refund(self) -> None:
        """net_amount refund : signed_ttc=-120, commission_ttc=-10 → net=-110."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD014", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": -100.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD014", "Type": "Commission", "Date de commande": "2026-01-15",
             "Montant": 10.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, _ = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        o = orders[0]
        # amount_ttc = 100 + 0 + 20 + 0 = 120
        # signed_ttc = -120
        # commission_ttc = 10
        # net = -120 - 10 = -130
        assert o["net_amount"] == -130.00

    def test_missing_date_anomaly(self) -> None:
        """Date manquante → Anomaly(type=missing_date)."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD015", "Type": "Montant", "Date de commande": None,
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250")

        # Assert
        assert len(orders) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "missing_date"


# ---------------------------------------------------------------------------
# Helpers for payments/subscriptions
# ---------------------------------------------------------------------------


def _make_payment_df(rows: list[dict]) -> pd.DataFrame:
    """Construit un DataFrame pré-filtré Type=Paiement avec dates parsées."""
    df = pd.DataFrame(rows)
    df["Montant"] = pd.to_numeric(df["Montant"], errors="coerce")
    df["Date du cycle de paiement"] = pd.to_datetime(
        df["Date du cycle de paiement"], format="%Y-%m-%d", errors="coerce"
    )
    return df


def _make_subscription_df(rows: list[dict]) -> pd.DataFrame:
    """Construit un DataFrame pré-filtré Type=Abonnement avec dates parsées."""
    for row in rows:
        row.setdefault("Date de commande", "2026-01-15")
    df = pd.DataFrame(rows)
    df["Montant"] = pd.to_numeric(df["Montant"], errors="coerce")
    df["Date du cycle de paiement"] = pd.to_datetime(
        df["Date du cycle de paiement"], format="%Y-%m-%d", errors="coerce"
    )
    df["Date de commande"] = pd.to_datetime(
        df["Date de commande"], format="%Y-%m-%d", errors="coerce"
    )
    return df


# ---------------------------------------------------------------------------
# TestMiraklPayments
# ---------------------------------------------------------------------------


class TestMiraklPayments:
    """Tests pour _build_payment_lookup() et _aggregate_payment_summaries()."""

    def test_payment_with_order_ref(self) -> None:
        """Paiement avec Numéro de commande présent → lookup_dict peuplé."""
        # Arrange
        df = _make_payment_df([
            {"Numéro de commande": "CMD001", "Type": "Paiement",
             "Date du cycle de paiement": "2026-01-20", "Montant": 150.00},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        lookup, anomalies = parser._build_payment_lookup(df)

        # Assert
        assert len(anomalies) == 0
        assert "CMD001" in lookup
        assert lookup["CMD001"][0] == datetime.date(2026, 1, 20)
        assert lookup["CMD001"][1] == "2026-01-20"

    def test_payment_without_order_ref(self) -> None:
        """Paiement sans Numéro de commande → pas dans le lookup_dict."""
        # Arrange
        df = _make_payment_df([
            {"Numéro de commande": "", "Type": "Paiement",
             "Date du cycle de paiement": "2026-01-20", "Montant": 150.00},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        lookup, anomalies = parser._build_payment_lookup(df)

        # Assert
        assert len(lookup) == 0
        assert len(anomalies) == 0

    def test_payment_invalid_date(self) -> None:
        """Date du cycle invalide → Anomaly(type=invalid_date)."""
        # Arrange
        df = _make_payment_df([
            {"Numéro de commande": "CMD001", "Type": "Paiement",
             "Date du cycle de paiement": "invalid", "Montant": 150.00},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        lookup, anomalies = parser._build_payment_lookup(df)

        # Assert
        assert len(lookup) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "invalid_date"

    def test_payout_summary_same_cycle(self) -> None:
        """2 lignes Paiement même cycle → 1 PayoutSummary, total correct."""
        # Arrange
        df = _make_payment_df([
            {"Numéro de commande": "CMD001", "Type": "Paiement",
             "Date du cycle de paiement": "2026-01-20", "Montant": 100.00},
            {"Numéro de commande": "CMD002", "Type": "Paiement",
             "Date du cycle de paiement": "2026-01-20", "Montant": 50.00},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        summaries = parser._aggregate_payment_summaries(df)

        # Assert
        assert len(summaries) == 1
        s = summaries[0]
        assert s.total_amount == 150.00
        assert s.payout_date == datetime.date(2026, 1, 20)
        assert s.payout_reference == "2026-01-20"
        assert set(s.transaction_references) == {"CMD001", "CMD002"}
        assert s.channel == "decathlon"

    def test_payout_summary_distinct_cycles(self) -> None:
        """2 cycles distincts → 2 PayoutSummary."""
        # Arrange
        df = _make_payment_df([
            {"Numéro de commande": "CMD001", "Type": "Paiement",
             "Date du cycle de paiement": "2026-01-20", "Montant": 100.00},
            {"Numéro de commande": "CMD002", "Type": "Paiement",
             "Date du cycle de paiement": "2026-01-27", "Montant": 200.00},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        summaries = parser._aggregate_payment_summaries(df)

        # Assert
        assert len(summaries) == 2
        dates = {s.payout_date for s in summaries}
        assert dates == {datetime.date(2026, 1, 20), datetime.date(2026, 1, 27)}


# ---------------------------------------------------------------------------
# TestMiraklSubscriptions
# ---------------------------------------------------------------------------


class TestMiraklSubscriptions:
    """Tests pour _parse_subscriptions()."""

    def test_subscription_nominal(self) -> None:
        """Abonnement nominal → special_type=SUBSCRIPTION, date=Date de commande."""
        # Arrange
        df = _make_subscription_df([
            {"Numéro de commande": "ABO001", "Type": "Abonnement",
             "Date de commande": "2026-01-10",
             "Date du cycle de paiement": "2026-01-31", "Montant": -39.99},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        subs, anomalies = parser._parse_subscriptions(df, country_code="250")

        # Assert
        assert len(subs) == 1
        assert len(anomalies) == 0
        s = subs[0]
        assert s["special_type"] == "SUBSCRIPTION"
        assert s["type"] == "sale"
        assert s["reference"] == "ABO001"
        assert s["date"] == datetime.date(2026, 1, 10)  # Date de commande, pas payout
        assert s["net_amount"] == -39.99
        assert s["payout_date"] == datetime.date(2026, 1, 31)
        assert s["payout_reference"] == "2026-01-31"

    def test_subscription_without_order_ref(self) -> None:
        """Abonnement sans Numéro de commande → référence générée avec date de création."""
        # Arrange
        df = _make_subscription_df([
            {"Numéro de commande": "", "Type": "Abonnement",
             "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "2026-01-31", "Montant": -39.99},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        subs, _ = parser._parse_subscriptions(df, country_code="250")

        # Assert
        assert subs[0]["reference"] == "ABO-decathlon-20260115"

    def test_subscription_without_payout_date(self) -> None:
        """Abonnement Payable (sans Date du cycle) → payout_date=None, écriture générée."""
        # Arrange
        df = _make_subscription_df([
            {"Numéro de commande": "", "Type": "Abonnement",
             "Date de commande": "2025-12-11",
             "Date du cycle de paiement": None, "Montant": -70.00},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        subs, anomalies = parser._parse_subscriptions(df, country_code="250")

        # Assert
        assert len(subs) == 1
        assert len(anomalies) == 0
        s = subs[0]
        assert s["date"] == datetime.date(2025, 12, 11)
        assert s["payout_date"] is None
        assert s["payout_reference"] is None
        assert s["net_amount"] == -70.00
        assert s["reference"] == "ABO-decathlon-20251211"

    def test_subscription_missing_creation_date(self) -> None:
        """Date de commande absente → Anomaly(type=invalid_date), abonnement ignoré."""
        # Arrange
        df = _make_subscription_df([
            {"Numéro de commande": "ABO002", "Type": "Abonnement",
             "Date de commande": None,
             "Date du cycle de paiement": "2026-01-31", "Montant": -39.99},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        subs, anomalies = parser._parse_subscriptions(df, country_code="250")

        # Assert
        assert len(subs) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "invalid_date"
        assert "Date de commande invalide" in anomalies[0].detail

    def test_subscription_decathlon_vs_leroy_merlin(self) -> None:
        """Abonnement Décathlon vs Leroy Merlin — montant lu du CSV."""
        # Arrange
        df_deca = _make_subscription_df([
            {"Numéro de commande": "", "Type": "Abonnement",
             "Date du cycle de paiement": "2026-01-31", "Montant": -39.99},
        ])
        df_lm = _make_subscription_df([
            {"Numéro de commande": "", "Type": "Abonnement",
             "Date du cycle de paiement": "2026-01-31", "Montant": -49.99},
        ])
        parser_deca = MiraklParser(channel="decathlon")
        parser_lm = MiraklParser(channel="leroy_merlin")

        # Act
        subs_deca, _ = parser_deca._parse_subscriptions(df_deca, country_code="250")
        subs_lm, _ = parser_lm._parse_subscriptions(df_lm, country_code="250")

        # Assert — référence basée sur Date de commande (défaut 2026-01-15)
        assert subs_deca[0]["net_amount"] == -39.99
        assert subs_deca[0]["reference"] == "ABO-decathlon-20260115"
        assert subs_lm[0]["net_amount"] == -49.99
        assert subs_lm[0]["reference"] == "ABO-leroy_merlin-20260115"


# ---------------------------------------------------------------------------
# Helpers for parse() integration tests
# ---------------------------------------------------------------------------


def _write_csv(tmp_path, filename: str, rows: list[dict]):  # type: ignore[no-untyped-def]
    """Écrit un CSV avec séparateur ';' et retourne le Path."""
    if not rows:
        # Empty CSV with headers
        content = ";".join(["Numéro de commande", "Type", "Date de commande",
                           "Date du cycle de paiement", "Montant"])
        filepath = tmp_path / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    import csv
    import io

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys(), delimiter=";")
    writer.writeheader()
    writer.writerows(rows)

    filepath = tmp_path / filename
    filepath.write_text(output.getvalue(), encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# TestMiraklParseDecathlon
# ---------------------------------------------------------------------------


class TestMiraklParseDecathlon:
    """Tests parse() avec channel=decathlon."""

    def test_parse_complete(self, tmp_path, sample_config) -> None:
        """Parse Décathlon complet : commandes + Paiement + Abonnement."""
        # Arrange
        csv_path = _write_csv(tmp_path, "Decathlon_test.csv", [
            {"Numéro de commande": "CMD001", "Type": "Montant", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "2026-01-20", "Montant": "100.00"},
            {"Numéro de commande": "CMD001", "Type": "Frais de port", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "2026-01-20", "Montant": "10.00"},
            {"Numéro de commande": "CMD001", "Type": "Commission", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "2026-01-20", "Montant": "-15.00"},
            {"Numéro de commande": "CMD001", "Type": "Taxe sur la commission", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "2026-01-20", "Montant": "0.00"},
            {"Numéro de commande": "CMD001", "Type": "Paiement", "Date de commande": "",
             "Date du cycle de paiement": "2026-01-20", "Montant": "95.00"},
            {"Numéro de commande": "", "Type": "Abonnement", "Date de commande": "2026-01-10",
             "Date du cycle de paiement": "2026-01-20", "Montant": "-39.99"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        assert result.channel == "decathlon"
        assert len(result.transactions) == 2  # 1 order + 1 subscription
        order_txs = [t for t in result.transactions if t.special_type is None]
        sub_txs = [t for t in result.transactions if t.special_type == "SUBSCRIPTION"]
        assert len(order_txs) == 1
        assert len(sub_txs) == 1
        assert order_txs[0].reference == "CMD001"
        assert order_txs[0].payout_date == datetime.date(2026, 1, 20)
        assert order_txs[0].payout_reference == "2026-01-20"
        assert order_txs[0].commission_ht == -15.00
        assert order_txs[0].commission_ttc == -15.00  # -15 + 0 taxe (decathlon 0%)
        assert order_txs[0].payment_method is None
        assert sub_txs[0].special_type == "SUBSCRIPTION"
        assert sub_txs[0].net_amount == -39.99
        assert len(result.payouts) == 1
        assert result.payouts[0].total_amount == 95.00

    def test_parse_payment_enrichment(self, tmp_path, sample_config) -> None:
        """Matching Paiement → commande enrichie avec payout_date/payout_reference."""
        # Arrange
        csv_path = _write_csv(tmp_path, "Decathlon_test.csv", [
            {"Numéro de commande": "CMD010", "Type": "Montant", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "", "Montant": "200.00"},
            {"Numéro de commande": "CMD010", "Type": "Paiement", "Date de commande": "",
             "Date du cycle de paiement": "2026-01-25", "Montant": "200.00"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        order_tx = [t for t in result.transactions if t.special_type is None][0]
        assert order_tx.payout_date == datetime.date(2026, 1, 25)
        assert order_tx.payout_reference == "2026-01-25"

    def test_parse_no_payment_match(self, tmp_path, sample_config) -> None:
        """Commande sans Paiement → payout_date=None."""
        # Arrange
        csv_path = _write_csv(tmp_path, "Decathlon_test.csv", [
            {"Numéro de commande": "CMD020", "Type": "Montant", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "", "Montant": "100.00"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        assert result.transactions[0].payout_date is None
        assert result.transactions[0].payout_reference is None

    def test_parse_subscription_payable_sans_payout_date(self, tmp_path, sample_config) -> None:
        """Abonnement Payable sans Date du cycle → payout_date/payout_reference = None."""
        # Arrange
        csv_path = _write_csv(tmp_path, "Decathlon_test.csv", [
            {"Numéro de commande": "", "Type": "Abonnement", "Date de commande": "11/12/2025",
             "Date du cycle de paiement": "", "Montant": "-70.00"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        sub_txs = [t for t in result.transactions if t.special_type == "SUBSCRIPTION"]
        assert len(sub_txs) == 1
        tx = sub_txs[0]
        assert tx.special_type == "SUBSCRIPTION"
        assert tx.date == datetime.date(2025, 12, 11)
        assert tx.payout_date is None
        assert tx.payout_reference is None  # pas "None"
        assert tx.net_amount == -70.00


# ---------------------------------------------------------------------------
# TestMiraklParseLeroyMerlin
# ---------------------------------------------------------------------------


class TestMiraklParseLeroyMerlin:
    """Tests parse() avec channel=leroy_merlin."""

    def test_parse_complete(self, tmp_path, sample_config) -> None:
        """Parse Leroy Merlin complet."""
        # Arrange
        csv_path = _write_csv(tmp_path, "LM_test.csv", [
            {"Numéro de commande": "LM001", "Type": "Montant", "Date de commande": "2026-01-10",
             "Date du cycle de paiement": "2026-01-15", "Montant": "500.00"},
            {"Numéro de commande": "LM001", "Type": "Commission", "Date de commande": "2026-01-10",
             "Date du cycle de paiement": "2026-01-15", "Montant": "-75.00"},
            {"Numéro de commande": "LM001", "Type": "Taxe sur la commission", "Date de commande": "2026-01-10",
             "Date du cycle de paiement": "2026-01-15", "Montant": "-15.00"},
            {"Numéro de commande": "LM001", "Type": "Paiement", "Date de commande": "",
             "Date du cycle de paiement": "2026-01-15", "Montant": "410.00"},
            {"Numéro de commande": "", "Type": "Abonnement", "Date de commande": "2026-01-05",
             "Date du cycle de paiement": "2026-01-15", "Montant": "-49.99"},
        ])
        parser = MiraklParser(channel="leroy_merlin")

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        assert result.channel == "leroy_merlin"
        order_txs = [t for t in result.transactions if t.special_type is None]
        sub_txs = [t for t in result.transactions if t.special_type == "SUBSCRIPTION"]
        assert len(order_txs) == 1
        assert len(sub_txs) == 1
        assert order_txs[0].commission_ht == -75.00
        assert order_txs[0].commission_ttc == -90.00  # -75 + -15
        assert sub_txs[0].net_amount == -49.99


# ---------------------------------------------------------------------------
# TestMiraklCommon
# ---------------------------------------------------------------------------


class TestMiraklCommon:
    """Tests paramétrés sur les deux canaux."""

    @pytest.mark.parametrize("channel", ["decathlon", "leroy_merlin"])
    def test_parse_basic(self, tmp_path, sample_config, channel: str) -> None:
        """Parsing basique — une commande simple."""
        # Arrange
        csv_path = _write_csv(tmp_path, "test.csv", [
            {"Numéro de commande": "CMD100", "Type": "Montant", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "", "Montant": "100.00"},
        ])
        parser = MiraklParser(channel=channel)

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        assert result.channel == channel
        assert len(result.transactions) == 1
        assert result.transactions[0].channel == channel

    @pytest.mark.parametrize("channel", ["decathlon", "leroy_merlin"])
    def test_parse_missing_column(self, tmp_path, sample_config, channel: str) -> None:
        """Colonne manquante → ParseError."""
        # Arrange
        from compta_ecom.models import ParseError

        filepath = tmp_path / "bad.csv"
        filepath.write_text("Col1;Col2\na;b\n", encoding="utf-8")
        parser = MiraklParser(channel=channel)

        # Act & Assert
        with pytest.raises(ParseError, match="Colonnes manquantes"):
            parser.parse(files={"data": filepath}, config=sample_config)

    @pytest.mark.parametrize("channel", ["decathlon", "leroy_merlin"])
    def test_parse_empty_csv(self, tmp_path, sample_config, channel: str) -> None:
        """CSV vide → ParseResult vide."""
        # Arrange
        csv_path = _write_csv(tmp_path, "empty.csv", [])
        parser = MiraklParser(channel=channel)

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        assert len(result.transactions) == 0
        assert len(result.payouts) == 0

    @pytest.mark.parametrize("channel", ["decathlon", "leroy_merlin"])
    def test_parse_no_country_code(self, tmp_path, sample_config, channel: str) -> None:
        """default_country_code=None → ParseError."""
        # Arrange
        from compta_ecom.models import ParseError

        csv_path = _write_csv(tmp_path, "test.csv", [
            {"Numéro de commande": "CMD100", "Type": "Montant", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "", "Montant": "100.00"},
        ])
        sample_config.channels[channel].default_country_code = None
        parser = MiraklParser(channel=channel)

        # Act & Assert
        with pytest.raises(ParseError, match="default_country_code"):
            parser.parse(files={"data": csv_path}, config=sample_config)

    @pytest.mark.parametrize("channel", ["decathlon", "leroy_merlin"])
    def test_parse_unknown_line_type(self, tmp_path, sample_config, channel: str) -> None:
        """Type de ligne inconnu → Anomaly(type=unknown_line_type)."""
        # Arrange
        csv_path = _write_csv(tmp_path, "test.csv", [
            {"Numéro de commande": "CMD100", "Type": "Montant", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "", "Montant": "100.00"},
            {"Numéro de commande": "CMD100", "Type": "TypeInconnu", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "", "Montant": "5.00"},
        ])
        parser = MiraklParser(channel=channel)

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        unknown_anomalies = [a for a in result.anomalies if a.type == "unknown_line_type"]
        assert len(unknown_anomalies) == 1
        assert unknown_anomalies[0].actual_value == "TypeInconnu"

    @pytest.mark.parametrize("channel", ["decathlon", "leroy_merlin"])
    def test_parse_non_numeric_montant(self, tmp_path, sample_config, channel: str) -> None:
        """Valeur non-numérique dans Montant → parse_warning anomaly, ligne ignorée (AC20)."""
        # Arrange
        csv_path = _write_csv(tmp_path, "test.csv", [
            {"Numéro de commande": "CMD200", "Type": "Montant", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "", "Montant": "abc"},
            {"Numéro de commande": "CMD201", "Type": "Montant", "Date de commande": "2026-01-15",
             "Date du cycle de paiement": "", "Montant": "100.00"},
        ])
        parser = MiraklParser(channel=channel)

        # Act
        result = parser.parse(files={"data": csv_path}, config=sample_config)

        # Assert
        parse_warnings = [a for a in result.anomalies if a.type == "parse_warning"]
        assert len(parse_warnings) == 1
        assert parse_warnings[0].reference == "CMD200"
        assert "non-numérique" in parse_warnings[0].detail
        # CMD200 ignored, CMD201 parsed
        order_txs = [t for t in result.transactions if t.special_type is None]
        assert len(order_txs) == 1
        assert order_txs[0].reference == "CMD201"


class TestMiraklPaymentEdgeCases:
    """Tests pour les cas limites des paiements."""

    def test_duplicate_payment_ref_last_wins(self) -> None:
        """Duplicate Numéro de commande dans Paiement → dernier écrase (TEST-002)."""
        # Arrange
        df = _make_payment_df([
            {"Numéro de commande": "CMD001", "Type": "Paiement",
             "Date du cycle de paiement": "2026-01-20", "Montant": 100.00},
            {"Numéro de commande": "CMD001", "Type": "Paiement",
             "Date du cycle de paiement": "2026-01-27", "Montant": 150.00},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        lookup, anomalies = parser._build_payment_lookup(df)

        # Assert — last write wins
        assert len(lookup) == 1
        assert lookup["CMD001"][0] == datetime.date(2026, 1, 27)
        assert lookup["CMD001"][1] == "2026-01-27"


# ---------------------------------------------------------------------------
# TestMiraklAmountsTTC
# ---------------------------------------------------------------------------


class TestMiraklAmountsTTC:
    """Tests pour amounts_are_ttc=True (Decathlon)."""

    def test_ttc_basic_sale(self) -> None:
        """TTC 120€, TVA 20% → HT=100€, TVA=20€."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD-TTC-001", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 120.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250", amounts_are_ttc=True)

        # Assert
        assert len(orders) == 1
        assert len(anomalies) == 0
        o = orders[0]
        assert o["amount_ht"] == 100.00
        assert o["amount_tva"] == 20.00
        assert o["amount_ttc"] == 120.00

    def test_ttc_with_shipping(self) -> None:
        """TTC produit + port → HT et TVA calculés séparément."""
        # Arrange: Montant=60.00 TTC, Frais de port=12.00 TTC
        df = _make_order_df([
            {"Numéro de commande": "CMD-TTC-002", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 60.00, "Date du cycle de paiement": "2026-01-20"},
            {"Numéro de commande": "CMD-TTC-002", "Type": "Frais de port", "Date de commande": "2026-01-15",
             "Montant": 12.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250", amounts_are_ttc=True)

        # Assert
        assert len(orders) == 1
        o = orders[0]
        assert o["amount_ht"] == 50.00  # 60 / 1.20
        assert o["shipping_ht"] == 10.00  # 12 / 1.20
        assert o["amount_tva"] == 10.00  # 60 - 50
        assert o["shipping_tva"] == 2.00  # 12 - 10
        assert o["amount_ttc"] == 72.00  # 60 + 12

    def test_ttc_refund(self) -> None:
        """Remboursement TTC → type=refund, montants abs positifs."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD-TTC-003", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": -120.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250", amounts_are_ttc=True)

        # Assert
        assert len(orders) == 1
        o = orders[0]
        assert o["type"] == "refund"
        assert o["amount_ht"] == 100.00  # abs(-120 / 1.20)
        assert o["amount_tva"] == 20.00
        assert o["net_amount"] < 0  # net_amount négatif

    def test_ttc_zero_rate(self) -> None:
        """TVA 0% → HT = TTC."""
        # Arrange
        df = _make_order_df([
            {"Numéro de commande": "CMD-TTC-004", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=0.0, country_code="250", amounts_are_ttc=True)

        # Assert
        assert len(orders) == 1
        o = orders[0]
        assert o["amount_ht"] == 100.00
        assert o["amount_tva"] == 0.00

    def test_ttc_country_from_canal_diffusion(self) -> None:
        """Canal de diffusion=Belgique → taux 21% utilisé."""
        # Arrange: 121€ TTC avec TVA Belgique 21%
        df = _make_order_df([
            {"Numéro de commande": "CMD-TTC-005", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 121.00, "Date du cycle de paiement": "2026-01-20", "Canal de diffusion": "Belgique"},
        ])
        parser = MiraklParser(channel="decathlon")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250", amounts_are_ttc=True)

        # Assert
        assert len(orders) == 1
        o = orders[0]
        assert o["tva_rate"] == 21.0
        assert o["country_code"] == "056"
        assert o["amount_ht"] == 100.00  # 121 / 1.21
        assert o["amount_tva"] == 21.00


# ---------------------------------------------------------------------------
# TestMiraklLeroyMerlinNonRegression
# ---------------------------------------------------------------------------


class TestMiraklLeroyMerlinNonRegression:
    """Tests de non-régression Leroy Merlin (amounts_are_ttc=False)."""

    def test_leroy_merlin_amounts_remain_ht(self) -> None:
        """Leroy Merlin : amounts_are_ttc=False → montants = HT."""
        # Arrange: Montant=100.00 (HT)
        df = _make_order_df([
            {"Numéro de commande": "LM-NR-001", "Type": "Montant", "Date de commande": "2026-01-15",
             "Montant": 100.00, "Date du cycle de paiement": "2026-01-20"},
        ])
        parser = MiraklParser(channel="leroy_merlin")

        # Act
        orders, anomalies = _aggregate_orders_helper(parser, df, tva_rate=20.0, country_code="250", amounts_are_ttc=False)

        # Assert
        assert len(orders) == 1
        o = orders[0]
        assert o["amount_ht"] == 100.00
        assert o["amount_tva"] == 20.00  # TVA calculée sur HT
        assert o["amount_ttc"] == 120.00  # HT + TVA
