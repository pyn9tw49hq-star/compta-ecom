"""Tests unitaires pour ShopifyParser."""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from compta_ecom.config.loader import AppConfig, ChannelConfig, PspConfig
from compta_ecom.models import ParseError, PayoutDetail
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


def _make_detail_csv(tmp_path: Path, rows: list[dict[str, object]], name: str = "detail.csv") -> Path:
    """Crée un fichier CSV detail à partir d'une liste de dicts."""
    df = pd.DataFrame(rows)
    path = tmp_path / name
    df.to_csv(path, index=False)
    return path


def _detail_row(**overrides: object) -> dict[str, object]:
    """Ligne CSV detail par défaut."""
    row: dict[str, object] = {
        "Transaction Date": "2026-01-15",
        "Type": "charge",
        "Order": "#1001",
        "Amount": 120.0,
        "Fee": 3.6,
        "Net": 116.4,
        "Payout Date": "2026-01-20",
        "Payout ID": "144387047761",
        "Payment Method Name": "card",
    }
    row.update(overrides)
    return row


class TestParsePayoutDetailsNominal:
    def test_nominal_3_charges_1_refund(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange
        rows = [
            _detail_row(Order="#1001", Type="charge", Amount=120.0, Fee=3.6, Net=116.4),
            _detail_row(Order="#1002", Type="charge", Amount=60.0, Fee=1.8, Net=58.2),
            _detail_row(Order="#1003", Type="charge", Amount=80.0, Fee=2.4, Net=77.6),
            _detail_row(Order="#1004", Type="refund", Amount=-60.0, Fee=0.0, Net=-60.0),
        ]
        path = _make_detail_csv(tmp_path, rows)
        parser = ShopifyParser()

        # Act
        details_by_id, anomalies = parser._parse_payout_details([path], shopify_config)

        # Assert
        assert len(anomalies) == 0
        assert "144387047761" in details_by_id
        details = details_by_id["144387047761"]
        assert len(details) == 4
        assert all(isinstance(d, PayoutDetail) for d in details)
        assert details[0].order_reference == "#1001"
        assert details[0].transaction_type == "charge"
        assert details[3].transaction_type == "refund"
        assert details[3].net == -60.0

    def test_grouping_by_payout_id(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange
        rows_a = [_detail_row(Order="#1001", **{"Payout ID": "AAA"})]
        rows_b = [_detail_row(Order="#1002", **{"Payout ID": "BBB"})]
        path_a = _make_detail_csv(tmp_path, rows_a, "a.csv")
        path_b = _make_detail_csv(tmp_path, rows_b, "b.csv")
        parser = ShopifyParser()

        # Act
        details_by_id, anomalies = parser._parse_payout_details([path_a, path_b], shopify_config)

        # Assert
        assert len(details_by_id) == 2
        assert "AAA" in details_by_id
        assert "BBB" in details_by_id

    def test_psp_mapping(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange
        rows = [_detail_row(**{"Payment Method Name": "card"})]
        path = _make_detail_csv(tmp_path, rows)
        parser = ShopifyParser()

        # Act
        details_by_id, _ = parser._parse_payout_details([path], shopify_config)

        # Assert
        assert details_by_id["144387047761"][0].payment_method == "card"

    def test_unknown_psp_returns_none_with_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — "paypal" is not in config.psp
        rows = [_detail_row(**{"Payment Method Name": "paypal"})]
        path = _make_detail_csv(tmp_path, rows)
        parser = ShopifyParser()

        # Act
        details_by_id, anomalies = parser._parse_payout_details([path], shopify_config)

        # Assert
        assert details_by_id["144387047761"][0].payment_method is None
        unknown_psp = [a for a in anomalies if a.type == "unknown_psp"]
        assert len(unknown_psp) == 1
        assert "paypal" in unknown_psp[0].detail

    def test_unreadable_file_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — binary/corrupted file
        path = tmp_path / "corrupted.csv"
        path.write_bytes(b"\x80\x81\x82\x00\xff\xfe")
        parser = ShopifyParser()

        # Act
        details_by_id, anomalies = parser._parse_payout_details([path], shopify_config)

        # Assert
        assert len(details_by_id) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "parse_warning"
        assert "illisible" in anomalies[0].detail

    def test_unparseable_payout_date_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — row with bad Payout Date
        rows = [_detail_row(**{"Payout Date": "not-a-date"})]
        path = _make_detail_csv(tmp_path, rows)
        parser = ShopifyParser()

        # Act
        details_by_id, anomalies = parser._parse_payout_details([path], shopify_config)

        # Assert
        assert len(details_by_id) == 0
        date_anomalies = [a for a in anomalies if "Payout Date" in a.detail]
        assert len(date_anomalies) == 1
        assert date_anomalies[0].type == "parse_warning"

    def test_missing_columns_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — CSV with missing columns
        df = pd.DataFrame({"Order": ["#1001"], "Type": ["charge"]})
        path = tmp_path / "bad.csv"
        df.to_csv(path, index=False)
        parser = ShopifyParser()

        # Act
        details_by_id, anomalies = parser._parse_payout_details([path], shopify_config)

        # Assert
        assert len(details_by_id) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "parse_warning"
        assert "Colonnes manquantes" in anomalies[0].detail

    def test_empty_file_headers_only(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — CSV with headers but no data rows
        df = pd.DataFrame(columns=[
            "Transaction Date", "Type", "Order", "Amount", "Fee", "Net",
            "Payout Date", "Payout ID", "Payment Method Name",
        ])
        path = tmp_path / "empty.csv"
        df.to_csv(path, index=False)
        parser = ShopifyParser()

        # Act
        details_by_id, anomalies = parser._parse_payout_details([path], shopify_config)

        # Assert
        assert len(details_by_id) == 0
        assert len(anomalies) == 0


def _make_payouts_csv(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    """Crée un fichier CSV versements."""
    df = pd.DataFrame(rows)
    path = tmp_path / "payouts.csv"
    df.to_csv(path, index=False)
    return path


def _payout_row(**overrides: object) -> dict[str, object]:
    """Ligne CSV versement par défaut."""
    row: dict[str, object] = {
        "Payout Date": "2026-01-20",
        "Charges": 200.0,
        "Refunds": -60.0,
        "Fees": 7.8,
        "Total": 132.2,
    }
    row.update(overrides)
    return row


class TestPayoutDetailAttachment:
    def test_details_attached_by_payout_reference(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange
        payouts_path = _make_payouts_csv(tmp_path, [_payout_row(Total=116.4)])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 120.0, "fee": 3.6, "net": 116.4,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}]
        }
        details = [
            PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                         order_reference="#1001", transaction_type="charge",
                         amount=120.0, fee=3.6, net=116.4, payment_method="card", channel="shopify"),
        ]
        payout_details_by_id = {"P001": details}
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        assert len(payouts) == 1
        assert payouts[0].details is not None
        assert len(payouts[0].details) == 1
        assert payouts[0].details[0].order_reference == "#1001"

    def test_no_detail_for_payout_reference(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange
        payouts_path = _make_payouts_csv(tmp_path, [_payout_row()])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 120.0, "fee": 3.6, "net": 116.4,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}]
        }
        payout_details_by_id = {"OTHER_ID": []}
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        assert len(payouts) == 1
        assert payouts[0].details is None


class TestPayoutDetailSumValidation:
    def test_sum_matches_no_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — sum of net == total_amount
        payouts_path = _make_payouts_csv(tmp_path, [_payout_row(Total=116.4)])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 120.0, "fee": 3.6, "net": 116.4,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}]
        }
        details = [
            PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                         order_reference="#1001", transaction_type="charge",
                         amount=120.0, fee=3.6, net=116.4, payment_method="card", channel="shopify"),
        ]
        payout_details_by_id = {"P001": details}
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        assert len(anomalies) == 0

    def test_sum_mismatch_over_tolerance_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — sum of net (116.4) != total_amount (100.0), écart > 0.01
        payouts_path = _make_payouts_csv(tmp_path, [_payout_row(Total=100.0)])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 120.0, "fee": 3.6, "net": 116.4,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}]
        }
        details = [
            PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                         order_reference="#1001", transaction_type="charge",
                         amount=120.0, fee=3.6, net=116.4, payment_method="card", channel="shopify"),
        ]
        payout_details_by_id = {"P001": details}
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        assert len(anomalies) == 1
        assert anomalies[0].type == "payout_detail_mismatch"
        assert anomalies[0].severity == "error"
        assert "116.4" in anomalies[0].detail
        assert "100.0" in anomalies[0].detail

    def test_sum_mismatch_within_tolerance_no_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — écart = 0.01 == tolerance → not > tolerance → no anomaly
        payouts_path = _make_payouts_csv(tmp_path, [_payout_row(Total=116.41)])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 120.0, "fee": 3.6, "net": 116.4,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}]
        }
        details = [
            PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                         order_reference="#1001", transaction_type="charge",
                         amount=120.0, fee=3.6, net=116.4, payment_method="card", channel="shopify"),
        ]
        payout_details_by_id = {"P001": details}
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        assert len(anomalies) == 0


class TestPayoutMissingDetails:
    """Story 4.3 — contrôle payout_missing_details."""

    def test_one_payout_without_detail(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """3 versements, details pour 2 → 1 anomalie payout_missing_details (AC#9)."""
        # Arrange — 3 payouts with different dates, details only for P001 and P002
        payouts_path = _make_payouts_csv(tmp_path, [
            _payout_row(**{"Payout Date": "2026-01-20", "Total": 100.0}),
            _payout_row(**{"Payout Date": "2026-01-21", "Total": 200.0}),
            _payout_row(**{"Payout Date": "2026-01-22", "Total": 300.0}),
        ])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 100.0, "fee": 0.0, "net": 100.0,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}],
            "#1002": [{"order": "#1002", "type": "charge", "payment_method": "card",
                        "amount": 200.0, "fee": 0.0, "net": 200.0,
                        "payout_date": datetime.date(2026, 1, 21), "payout_reference": "P002"}],
            "#1003": [{"order": "#1003", "type": "charge", "payment_method": "card",
                        "amount": 300.0, "fee": 0.0, "net": 300.0,
                        "payout_date": datetime.date(2026, 1, 22), "payout_reference": "P003"}],
        }
        payout_details_by_id = {
            "P001": [PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                                  order_reference="#1001", transaction_type="charge",
                                  amount=100.0, fee=0.0, net=100.0, payment_method="card", channel="shopify")],
            "P002": [PayoutDetail(payout_date=datetime.date(2026, 1, 21), payout_id="P002",
                                  order_reference="#1002", transaction_type="charge",
                                  amount=200.0, fee=0.0, net=200.0, payment_method="card", channel="shopify")],
        }
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        missing = [a for a in anomalies if a.type == "payout_missing_details"]
        assert len(missing) == 1
        assert missing[0].severity == "warning"
        assert missing[0].reference == "P003"

    def test_no_detail_files_no_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """3 versements, payout_details_by_id=None → 0 anomalies (AC#10)."""
        # Arrange
        payouts_path = _make_payouts_csv(tmp_path, [
            _payout_row(**{"Payout Date": "2026-01-20", "Total": 100.0}),
            _payout_row(**{"Payout Date": "2026-01-21", "Total": 200.0}),
            _payout_row(**{"Payout Date": "2026-01-22", "Total": 300.0}),
        ])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 100.0, "fee": 0.0, "net": 100.0,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}],
            "#1002": [{"order": "#1002", "type": "charge", "payment_method": "card",
                        "amount": 200.0, "fee": 0.0, "net": 200.0,
                        "payout_date": datetime.date(2026, 1, 21), "payout_reference": "P002"}],
            "#1003": [{"order": "#1003", "type": "charge", "payment_method": "card",
                        "amount": 300.0, "fee": 0.0, "net": 300.0,
                        "payout_date": datetime.date(2026, 1, 22), "payout_reference": "P003"}],
        }
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, None)

        # Assert
        missing = [a for a in anomalies if a.type == "payout_missing_details"]
        assert len(missing) == 0

    def test_all_payouts_with_details_no_anomaly(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """3 versements, details pour 3 → 0 anomalies (AC#11)."""
        # Arrange
        payouts_path = _make_payouts_csv(tmp_path, [
            _payout_row(**{"Payout Date": "2026-01-20", "Total": 100.0}),
            _payout_row(**{"Payout Date": "2026-01-21", "Total": 200.0}),
            _payout_row(**{"Payout Date": "2026-01-22", "Total": 300.0}),
        ])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 100.0, "fee": 0.0, "net": 100.0,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}],
            "#1002": [{"order": "#1002", "type": "charge", "payment_method": "card",
                        "amount": 200.0, "fee": 0.0, "net": 200.0,
                        "payout_date": datetime.date(2026, 1, 21), "payout_reference": "P002"}],
            "#1003": [{"order": "#1003", "type": "charge", "payment_method": "card",
                        "amount": 300.0, "fee": 0.0, "net": 300.0,
                        "payout_date": datetime.date(2026, 1, 22), "payout_reference": "P003"}],
        }
        payout_details_by_id = {
            "P001": [PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                                  order_reference="#1001", transaction_type="charge",
                                  amount=100.0, fee=0.0, net=100.0, payment_method="card", channel="shopify")],
            "P002": [PayoutDetail(payout_date=datetime.date(2026, 1, 21), payout_id="P002",
                                  order_reference="#1002", transaction_type="charge",
                                  amount=200.0, fee=0.0, net=200.0, payment_method="card", channel="shopify")],
            "P003": [PayoutDetail(payout_date=datetime.date(2026, 1, 22), payout_id="P003",
                                  order_reference="#1003", transaction_type="charge",
                                  amount=300.0, fee=0.0, net=300.0, payment_method="card", channel="shopify")],
        }
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        missing = [a for a in anomalies if a.type == "payout_missing_details"]
        assert len(missing) == 0


class TestOrphanPayoutDetail:
    """Story 4.3 — contrôle orphan_payout_detail."""

    def test_orphan_detail(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Detail avec Payout ID '999999' absent des versements → 1 anomalie (AC#12)."""
        # Arrange — 1 payout with P001, detail for P001 + orphan "999999"
        payouts_path = _make_payouts_csv(tmp_path, [_payout_row(**{"Payout Date": "2026-01-20", "Total": 100.0})])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 100.0, "fee": 0.0, "net": 100.0,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}],
        }
        payout_details_by_id = {
            "P001": [PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                                  order_reference="#1001", transaction_type="charge",
                                  amount=100.0, fee=0.0, net=100.0, payment_method="card", channel="shopify")],
            "999999": [PayoutDetail(payout_date=datetime.date(2026, 1, 25), payout_id="999999",
                                    order_reference="#9999", transaction_type="charge",
                                    amount=50.0, fee=0.0, net=50.0, payment_method="card", channel="shopify")],
        }
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        orphans = [a for a in anomalies if a.type == "orphan_payout_detail"]
        assert len(orphans) == 1
        assert orphans[0].severity == "warning"
        assert orphans[0].reference == "999999"

    def test_no_orphan(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """Tous les Payout ID matchent → 0 anomalies orphan (AC#13)."""
        # Arrange
        payouts_path = _make_payouts_csv(tmp_path, [_payout_row(**{"Payout Date": "2026-01-20", "Total": 100.0})])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 100.0, "fee": 0.0, "net": 100.0,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}],
        }
        payout_details_by_id = {
            "P001": [PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                                  order_reference="#1001", transaction_type="charge",
                                  amount=100.0, fee=0.0, net=100.0, payment_method="card", channel="shopify")],
        }
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        orphans = [a for a in anomalies if a.type == "orphan_payout_detail"]
        assert len(orphans) == 0

    def test_combined_missing_and_orphan(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        """1 versement sans detail + 1 detail orphelin → 2 anomalies (AC#14)."""
        # Arrange — 2 payouts (P001, P002), detail only for P001 + orphan "ORPHAN1"
        payouts_path = _make_payouts_csv(tmp_path, [
            _payout_row(**{"Payout Date": "2026-01-20", "Total": 100.0}),
            _payout_row(**{"Payout Date": "2026-01-21", "Total": 200.0}),
        ])
        tx_data: dict[str, list[dict[str, object]]] = {
            "#1001": [{"order": "#1001", "type": "charge", "payment_method": "card",
                        "amount": 100.0, "fee": 0.0, "net": 100.0,
                        "payout_date": datetime.date(2026, 1, 20), "payout_reference": "P001"}],
            "#1002": [{"order": "#1002", "type": "charge", "payment_method": "card",
                        "amount": 200.0, "fee": 0.0, "net": 200.0,
                        "payout_date": datetime.date(2026, 1, 21), "payout_reference": "P002"}],
        }
        payout_details_by_id = {
            "P001": [PayoutDetail(payout_date=datetime.date(2026, 1, 20), payout_id="P001",
                                  order_reference="#1001", transaction_type="charge",
                                  amount=100.0, fee=0.0, net=100.0, payment_method="card", channel="shopify")],
            "ORPHAN1": [PayoutDetail(payout_date=datetime.date(2026, 1, 25), payout_id="ORPHAN1",
                                     order_reference="#9999", transaction_type="charge",
                                     amount=50.0, fee=0.0, net=50.0, payment_method="card", channel="shopify")],
        }
        parser = ShopifyParser()

        # Act
        payouts, anomalies = parser._parse_payouts(payouts_path, tx_data, shopify_config, payout_details_by_id)

        # Assert
        missing = [a for a in anomalies if a.type == "payout_missing_details"]
        orphans = [a for a in anomalies if a.type == "orphan_payout_detail"]
        assert len(missing) == 1
        assert missing[0].reference == "P002"
        assert len(orphans) == 1
        assert orphans[0].reference == "ORPHAN1"


class TestPayoutRetrocompatibility:
    def test_no_payout_details_all_none(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — parse without payout_details in files
        sales_path = _make_csv(tmp_path, [_base_row()])
        payouts_path = _make_payouts_csv(tmp_path, [_payout_row()])
        parser = ShopifyParser()

        # Act
        result = parser.parse({"sales": sales_path, "payouts": payouts_path}, shopify_config)

        # Assert
        for p in result.payouts:
            assert p.details is None

    def test_existing_tests_unaffected(self, tmp_path: Path, shopify_config: AppConfig) -> None:
        # Arrange — basic parse without detail files
        sales_path = _make_csv(tmp_path, [_base_row()])
        parser = ShopifyParser()

        # Act
        result = parser.parse({"sales": sales_path}, shopify_config)

        # Assert
        assert len(result.transactions) == 1
        assert result.payouts == []
