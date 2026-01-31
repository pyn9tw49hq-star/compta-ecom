"""Tests unitaires pour ShopifyParser."""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from compta_ecom.config.loader import AppConfig, ChannelConfig, PspConfig
from compta_ecom.models import ParseError
from compta_ecom.parsers.shopify import ShopifyParser, _extract_vat_rate


@pytest.fixture
def shopify_config() -> AppConfig:
    """AppConfig avec mapping alpha2 pour les tests Shopify."""
    return AppConfig(
        clients={"shopify": "411SHOPIFY"},
        fournisseurs={"manomano": "FMANO"},
        psp={"card": PspConfig(compte="51150007", commission="62700002")},
        transit="58000000",
        banque="51200000",
        comptes_speciaux={"ADJUSTMENT": "51150002"},
        comptes_vente_prefix="707",
        canal_codes={"shopify": "01"},
        comptes_tva_prefix="4457",
        vat_table={
            "250": {"name": "France", "rate": 20.0, "alpha2": "FR"},
            "056": {"name": "Belgique", "rate": 21.0, "alpha2": "BE"},
        },
        alpha2_to_numeric={"FR": "250", "BE": "056"},
        channels={
            "shopify": ChannelConfig(
                files={"sales": "Ventes Shopify*.csv"},
                encoding="utf-8",
                separator=",",
            ),
        },
    )


def _make_csv(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    """Crée un fichier CSV à partir d'une liste de dicts."""
    df = pd.DataFrame(rows)
    path = tmp_path / "sales.csv"
    df.to_csv(path, index=False)
    return path


def _base_row(**overrides: object) -> dict[str, object]:
    """Retourne une ligne CSV de base avec des valeurs par défaut."""
    row: dict[str, object] = {
        "Name": "#1001",
        "Created at": "2025-01-15",
        "Subtotal": 100.0,
        "Shipping": 10.0,
        "Taxes": 22.0,
        "Total": 132.0,
        "Tax 1 Name": "FR TVA 20%",
        "Tax 1 Value": 22.0,
        "Payment Method": "Carte",
        "Shipping Country": "FR",
    }
    row.update(overrides)
    return row


class TestExtractVatRate:
    def test_fr_tva_20(self) -> None:
        assert _extract_vat_rate("FR TVA 20%") == 20.0

    def test_be_tva_21(self) -> None:
        assert _extract_vat_rate("BE TVA 21%") == 21.0

    def test_empty_string(self) -> None:
        assert _extract_vat_rate("") == 0.0

    def test_none(self) -> None:
        assert _extract_vat_rate(None) == 0.0

    def test_no_percentage(self) -> None:
        assert _extract_vat_rate("No tax") == 0.0

    def test_decimal_rate(self) -> None:
        assert _extract_vat_rate("TVA 5.5%") == 5.5


class TestShopifyParserNominal:
    def test_single_order(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        csv_path = _make_csv(tmp_path, [_base_row()])
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        assert len(result.transactions) == 1
        assert result.payouts == []
        assert result.channel == "shopify"

        tx = result.transactions[0]
        assert tx.reference == "#1001"
        assert tx.channel == "shopify"
        assert tx.type == "sale"
        assert tx.date == datetime.date(2025, 1, 15)
        assert tx.amount_ht == 100.0
        assert tx.shipping_ht == 10.0
        assert tx.shipping_tva == 2.0  # 10 * 20 / 100
        assert tx.amount_tva == 20.0  # 22 - 2
        assert tx.amount_ttc == 132.0
        assert tx.tva_rate == 20.0
        assert tx.country_code == "250"
        assert tx.commission_ttc == 0.0
        assert tx.commission_ht == 0.0
        assert tx.net_amount == 132.0
        assert tx.payout_date is None
        assert tx.payout_reference is None
        assert tx.payment_method is None
        assert tx.special_type is None


class TestShopifyParserMultiLine:
    def test_aggregate_same_name(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        rows = [
            _base_row(Subtotal=50.0, Shipping=5.0, Taxes=11.0, Total=66.0),
            _base_row(Subtotal=50.0, Shipping=5.0, Taxes=11.0, Total=66.0),
        ]
        csv_path = _make_csv(tmp_path, rows)
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        assert len(result.transactions) == 1
        tx = result.transactions[0]
        assert tx.amount_ht == 100.0
        assert tx.shipping_ht == 10.0
        assert tx.amount_ttc == 132.0

    def test_divergent_country(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        rows = [
            _base_row(**{"Shipping Country": "FR"}),
            _base_row(**{"Shipping Country": "BE"}),
        ]
        csv_path = _make_csv(tmp_path, rows)
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        anomalies = [a for a in result.anomalies if a.detail == "Pays de livraison divergent entre les lignes de la commande"]
        assert len(anomalies) == 1
        assert anomalies[0].type == "parse_warning"


class TestShopifyParserMissingColumns:
    def test_missing_column(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        df = pd.DataFrame({"Name": ["#1001"], "Created at": ["2025-01-15"]})
        path = tmp_path / "sales.csv"
        df.to_csv(path, index=False)

        parser = ShopifyParser()
        with pytest.raises(ParseError, match="Colonnes manquantes"):
            parser.parse({"sales": path}, shopify_config)


class TestShopifyParserCountryConversion:
    def test_known_country(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        csv_path = _make_csv(tmp_path, [_base_row(**{"Shipping Country": "FR"})])
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)
        assert result.transactions[0].country_code == "250"

    def test_unknown_country(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        csv_path = _make_csv(tmp_path, [_base_row(**{"Shipping Country": "XX"})])
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        assert result.transactions[0].country_code == "000"
        anomalies = [a for a in result.anomalies if a.type == "unknown_country"]
        assert len(anomalies) == 1
        assert "XX" in anomalies[0].detail


class TestShopifyParserShippingVat:
    def test_shipping_vat_rounding(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Shipping=7.33, taux 20% -> shipping_tva=1.47 (arrondi)."""
        csv_path = _make_csv(tmp_path, [_base_row(Shipping=7.33, Taxes=21.47, Total=128.80, Subtotal=100.0)])
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        tx = result.transactions[0]
        assert tx.shipping_ht == 7.33
        assert tx.shipping_tva == 1.47  # round(7.33 * 20 / 100, 2)
        assert tx.amount_tva == 20.0  # round(21.47 - 1.47, 2)


class TestShopifyParserZeroVat:
    def test_zero_taxes_no_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Taxes=0 et Shipping>0 → amount_tva=0, pas d'anomalie TVA négative."""
        csv_path = _make_csv(tmp_path, [_base_row(Taxes=0.0, Shipping=10.0)])
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        tx = result.transactions[0]
        assert tx.amount_tva == 0.0
        assert tx.shipping_tva == 0.0
        anomalies = [a for a in result.anomalies if a.detail == "TVA produit négative après ventilation port"]
        assert len(anomalies) == 0


class TestShopifyParserNonParsable:
    def test_non_parsable_value(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Valeur non parsable -> Anomaly, ligne ignorée."""
        csv_path = _make_csv(tmp_path, [_base_row(Subtotal="abc")])
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        assert len(result.transactions) == 0
        anomalies = [a for a in result.anomalies if a.type == "parse_warning" and "non parsable" in a.detail]
        assert len(anomalies) == 1


class TestShopifyParserMultipleDistinctOrders:
    def test_two_distinct_orders(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Deux commandes distinctes dans le même CSV -> 2 NormalizedTransaction."""
        rows = [
            _base_row(Name="#1001", Subtotal=100.0, Shipping=10.0, Taxes=22.0, Total=132.0),
            _base_row(Name="#1002", Subtotal=50.0, Shipping=5.0, Taxes=11.0, Total=66.0),
        ]
        csv_path = _make_csv(tmp_path, rows)
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        assert len(result.transactions) == 2
        refs = {tx.reference for tx in result.transactions}
        assert refs == {"#1001", "#1002"}

        tx1 = next(tx for tx in result.transactions if tx.reference == "#1001")
        tx2 = next(tx for tx in result.transactions if tx.reference == "#1002")
        assert tx1.amount_ht == 100.0
        assert tx2.amount_ht == 50.0
        assert tx2.amount_ttc == 66.0


class TestShopifyParserDateParsing:
    def test_invalid_date(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Date non parsable -> Anomaly, ligne ignorée."""
        csv_path = _make_csv(tmp_path, [_base_row(**{"Created at": "not-a-date"})])
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)

        assert len(result.transactions) == 0
        anomalies = [a for a in result.anomalies if a.type == "parse_warning"]
        assert len(anomalies) == 1


class TestShopifyParserPayoutsEmpty:
    def test_payouts_empty(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        csv_path = _make_csv(tmp_path, [_base_row()])
        parser = ShopifyParser()
        result = parser.parse({"sales": csv_path}, shopify_config)
        assert result.payouts == []
