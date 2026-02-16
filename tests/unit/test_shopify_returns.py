"""Tests pour le support du fichier Retours Shopify (Story 3.5)."""

from __future__ import annotations

import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from compta_ecom.config.loader import AppConfig, ChannelConfig, PspConfig
from compta_ecom.engine.accounting import generate_entries
from compta_ecom.models import NormalizedTransaction
from compta_ecom.parsers.shopify import ShopifyParser


@pytest.fixture
def shopify_config() -> AppConfig:
    """AppConfig minimale pour les tests retours Shopify."""
    return AppConfig(
        clients={"shopify": "411SHOPIFY"},
        fournisseurs={},
        psp={
            "card": PspConfig(compte="51150007", commission="62700002"),
        },
        transit="58000000",
        banque="51200000",
        comptes_speciaux={},
        comptes_vente_prefix="707",
        canal_codes={"shopify": "01"},
        comptes_tva_prefix="4457",
        comptes_port_prefix="7085",
        zones_port={"france": "00", "hors_ue": "01", "ue": "02"},
        vat_table={
            "250": {"name": "France", "rate": 20.0, "alpha2": "FR"},
        },
        alpha2_to_numeric={"FR": "250"},
        channels={
            "shopify": ChannelConfig(
                files={
                    "sales": "ventes.csv",
                    "transactions": "transactions.csv",
                    "returns": "returns.csv",
                },
                encoding="utf-8",
                separator=",",
                optional_files=["returns"],
            ),
        },
    )


@pytest.fixture
def sales_data() -> dict[str, dict[str, Any]]:
    """Données de vente simulées pour le lookup retours."""
    return {
        "#TEST_RET001": {
            "reference": "#TEST_RET001",
            "date": datetime.date(2026, 1, 15),
            "amount_ht": 100.0,
            "amount_tva": 20.0,
            "amount_ttc": 120.0,
            "shipping_ht": 0.0,
            "shipping_tva": 0.0,
            "tva_rate": 20.0,
            "country_code": "250",
        },
        "#TEST_RET002": {
            "reference": "#TEST_RET002",
            "date": datetime.date(2026, 1, 16),
            "amount_ht": 50.0,
            "amount_tva": 10.0,
            "amount_ttc": 60.0,
            "shipping_ht": 10.0,
            "shipping_tva": 2.0,
            "tva_rate": 20.0,
            "country_code": "250",
        },
        "#TEST_RET003": {
            "reference": "#TEST_RET003",
            "date": datetime.date(2026, 1, 17),
            "amount_ht": 80.0,
            "amount_tva": 16.0,
            "amount_ttc": 96.0,
            "shipping_ht": 5.0,
            "shipping_tva": 1.0,
            "tva_rate": 20.0,
            "country_code": "250",
        },
        "#TEST_RET005": {
            "reference": "#TEST_RET005",
            "date": datetime.date(2026, 1, 18),
            "amount_ht": 45.0,
            "amount_tva": 9.0,
            "amount_ttc": 54.0,
            "shipping_ht": 0.0,
            "shipping_tva": 0.0,
            "tva_rate": 20.0,
            "country_code": "250",
        },
    }


@pytest.fixture
def returns_path() -> Path:
    """Chemin vers la fixture returns.csv."""
    return Path(__file__).parent.parent / "fixtures" / "shopify" / "returns.csv"


class TestParseReturnsNominal:
    """Tests du parsing nominal des retours."""

    def test_parse_returns_count(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """4 commandes retournées (RET001, RET002, RET003 agrégé, RET005). RET004 filtré (Total=0)."""
        parser = ShopifyParser()
        txs, anomalies = parser._parse_returns(returns_path, sales_data, shopify_config)
        assert len(txs) == 4

    def test_parse_returns_type_and_special_type(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """Chaque retour est type=refund, special_type=returns_avoir."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        for tx in txs:
            assert tx.type == "refund"
            assert tx.special_type == "returns_avoir"
            assert tx.channel == "shopify"

    def test_parse_returns_simple_amounts(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """#TEST_RET001 : nets=100, shipping=0, taxes=20, TTC=120."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret001 = next(t for t in txs if t.reference == "#TEST_RET001")
        assert ret001.amount_ht == 100.0
        assert ret001.shipping_ht == 0.0
        assert ret001.amount_tva == 20.0
        assert ret001.shipping_tva == 0.0
        assert ret001.amount_ttc == 120.0

    def test_parse_returns_with_shipping(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """#TEST_RET002 : nets=50, shipping=10, taxes=12, TTC=72."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret002 = next(t for t in txs if t.reference == "#TEST_RET002")
        assert ret002.amount_ht == 50.0
        assert ret002.shipping_ht == 10.0
        assert ret002.amount_ttc == 72.0
        # TVA ventilée proportionnellement : shipping_ratio = 10/60 = 1/6
        assert ret002.shipping_tva == round(12.0 * (10.0 / 60.0), 2)
        assert ret002.amount_tva == round(12.0 - ret002.shipping_tva, 2)

    def test_parse_returns_date(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """La date est celle du fichier retours (min du groupe)."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret001 = next(t for t in txs if t.reference == "#TEST_RET001")
        assert ret001.date == datetime.date(2026, 1, 20)


class TestParseReturnsAggregation:
    """Tests de l'agrégation multi-lignes par commande."""

    def test_aggregation_by_order(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """#TEST_RET003 apparaît 2 fois → agrégé en 1 seule transaction."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret003_list = [t for t in txs if t.reference == "#TEST_RET003"]
        assert len(ret003_list) == 1

    def test_aggregation_amounts(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """#TEST_RET003 : nets=30+20=50, shipping=5+3=8, taxes=7+4.6=11.6."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret003 = next(t for t in txs if t.reference == "#TEST_RET003")
        assert ret003.amount_ht == 50.0
        assert ret003.shipping_ht == 8.0
        assert ret003.amount_ttc == round(50.0 + 8.0 + 11.6, 2)

    def test_aggregation_date_is_min(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """La date agrégée est le min du groupe (2026-01-22 pour les deux lignes)."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret003 = next(t for t in txs if t.reference == "#TEST_RET003")
        assert ret003.date == datetime.date(2026, 1, 22)


class TestParseReturnsFiltering:
    """Tests du filtrage des lignes Total=0."""

    def test_zero_total_filtered(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """#TEST_RET004 a Total=0 → pas de transaction générée."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        refs = [t.reference for t in txs]
        assert "#TEST_RET004" not in refs


class TestParseReturnsCountryLookup:
    """Tests du lookup country_code depuis sales_data."""

    def test_country_from_sale(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """Le country_code vient de la vente correspondante."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret001 = next(t for t in txs if t.reference == "#TEST_RET001")
        assert ret001.country_code == "250"

    def test_country_fallback_france(
        self, returns_path: Path, shopify_config: AppConfig
    ) -> None:
        """Sans vente correspondante, fallback à 250 (France) + anomalie warning."""
        parser = ShopifyParser()
        empty_sales: dict[str, dict[str, Any]] = {}
        txs, anomalies = parser._parse_returns(returns_path, empty_sales, shopify_config)
        for tx in txs:
            assert tx.country_code == "250"
        warnings = [a for a in anomalies if a.type == "return_no_matching_sale"]
        assert len(warnings) == len(txs)


class TestParseReturnsTvaRate:
    """Tests du calcul tva_rate depuis les montants."""

    def test_tva_rate_from_amounts(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """#TEST_RET001 : taxes=20, nets=100, shipping=0 → tva_rate = 20/100*100 = 20.0."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret001 = next(t for t in txs if t.reference == "#TEST_RET001")
        assert ret001.tva_rate == 20.0

    def test_tva_rate_with_shipping(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """#TEST_RET002 : taxes=12, base=50+10=60 → tva_rate = 12/60*100 = 20.0."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret002 = next(t for t in txs if t.reference == "#TEST_RET002")
        assert ret002.tva_rate == 20.0

    def test_tva_rate_partial_refund_uses_sale_rate(
        self, shopify_config: AppConfig
    ) -> None:
        """Issue #10 : remboursement partiel nets=1€, taxes=8.26€ → doit utiliser le taux de la vente (20%), pas 826%."""
        csv = (
            "Jour,Nom de la commande,Retours nets,Expédition retournée,"
            "Taxes retournées,Frais de retour,Total des retours\n"
            "2026-01-20,#1139,-1.00,0.00,-8.26,0.00,-9.26\n"
        )
        buf = BytesIO(csv.encode("utf-8"))
        sale_data: dict[str, dict[str, Any]] = {
            "#1139": {
                "reference": "#1139",
                "date": datetime.date(2026, 1, 10),
                "amount_ht": 100.0,
                "amount_tva": 20.0,
                "amount_ttc": 120.0,
                "shipping_ht": 0.0,
                "shipping_tva": 0.0,
                "tva_rate": 20.0,
                "country_code": "250",
            },
        }
        parser = ShopifyParser()
        txs, anomalies = parser._parse_returns(buf, sale_data, shopify_config)
        assert len(txs) == 1
        assert txs[0].tva_rate == 20.0
        assert not any(a.type == "return_tva_rate_aberrant" for a in anomalies)

    def test_tva_rate_orphan_return_aberrant_guard(
        self, shopify_config: AppConfig
    ) -> None:
        """Issue #10 : retour orphelin avec taux calculé > 30% → fallback + anomalie."""
        csv = (
            "Jour,Nom de la commande,Retours nets,Expédition retournée,"
            "Taxes retournées,Frais de retour,Total des retours\n"
            "2026-01-20,#9999,-1.00,0.00,-8.26,0.00,-9.26\n"
        )
        buf = BytesIO(csv.encode("utf-8"))
        parser = ShopifyParser()
        txs, anomalies = parser._parse_returns(buf, {}, shopify_config)
        assert len(txs) == 1
        # Fallback to default 20% (no matching sale → country 250, rate 20)
        assert txs[0].tva_rate == 20.0
        aberrant = [a for a in anomalies if a.type == "return_tva_rate_aberrant"]
        assert len(aberrant) == 1
        assert "826" in aberrant[0].detail


class TestParseReturnsTvaVentilation:
    """Tests de la ventilation TVA produit/port."""

    def test_tva_ventilation_no_shipping(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """Sans shipping, toute la TVA va au produit."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret001 = next(t for t in txs if t.reference == "#TEST_RET001")
        assert ret001.amount_tva == 20.0
        assert ret001.shipping_tva == 0.0

    def test_tva_ventilation_with_shipping(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """Avec shipping, TVA ventilée proportionnellement."""
        parser = ShopifyParser()
        txs, _ = parser._parse_returns(returns_path, sales_data, shopify_config)
        ret002 = next(t for t in txs if t.reference == "#TEST_RET002")
        total_tva = ret002.amount_tva + ret002.shipping_tva
        assert total_tva == 12.0


class TestParseReturnsAnomalies:
    """Tests des anomalies spécifiques aux retours."""

    def test_return_fee_nonzero_anomaly(
        self, returns_path: Path, sales_data: dict[str, dict[str, Any]], shopify_config: AppConfig
    ) -> None:
        """#TEST_RET005 a Frais de retour=5 → anomalie info."""
        parser = ShopifyParser()
        _, anomalies = parser._parse_returns(returns_path, sales_data, shopify_config)
        fee_anomalies = [a for a in anomalies if a.type == "return_fee_nonzero"]
        assert len(fee_anomalies) == 1
        assert fee_anomalies[0].reference == "#TEST_RET005"
        assert fee_anomalies[0].severity == "info"

    def test_missing_columns_raises_parse_error(
        self, shopify_config: AppConfig
    ) -> None:
        """CSV avec colonnes manquantes → ParseError."""
        from compta_ecom.models import ParseError

        bad_csv = BytesIO(b"Jour,Nom de la commande\n2026-01-20,#REF\n")
        parser = ShopifyParser()
        with pytest.raises(ParseError):
            parser._parse_returns(bad_csv, {}, shopify_config)


class TestAccountingRoutingReturnsAvoir:
    """Tests du routing accounting pour returns_avoir → sale_entries only."""

    def test_returns_avoir_generates_sale_entries(self, shopify_config: AppConfig) -> None:
        """returns_avoir doit générer uniquement des écritures de vente inversées (avoir)."""
        tx = NormalizedTransaction(
            reference="#RET_TEST",
            channel="shopify",
            date=datetime.date(2026, 1, 20),
            type="refund",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=120.0,
            shipping_ht=0.0,
            shipping_tva=0.0,
            tva_rate=20.0,
            country_code="250",
            commission_ttc=0.0,
            commission_ht=0.0,
            net_amount=0.0,
            payout_date=None,
            payout_reference=None,
            payment_method=None,
            special_type="returns_avoir",
        )
        entries, anomalies = generate_entries([tx], [], shopify_config)
        assert len(entries) > 0
        # Avoir : 411 CREDIT, 707 DEBIT, 4457 DEBIT
        entry_types = {e.entry_type for e in entries}
        assert "refund" in entry_types
        assert "settlement" not in entry_types
        assert "commission" not in entry_types
        # 411 en credit
        client_entry = next(e for e in entries if e.account == "411SHOPIFY")
        assert client_entry.credit == 120.0
        assert client_entry.debit == 0.0
        # 707 en debit
        vente_entry = next(e for e in entries if e.account.startswith("707"))
        assert vente_entry.debit == 100.0
        # piece_number avec suffixe "A" (avoir Shopify)
        for e in entries:
            assert e.piece_number == "#RET_TESTA"

    def test_returns_avoir_with_shipping(self, shopify_config: AppConfig) -> None:
        """returns_avoir avec port → 7085 DEBIT en plus."""
        tx = NormalizedTransaction(
            reference="#RET_SHIP",
            channel="shopify",
            date=datetime.date(2026, 1, 21),
            type="refund",
            amount_ht=50.0,
            amount_tva=10.0,
            amount_ttc=72.0,
            shipping_ht=10.0,
            shipping_tva=2.0,
            tva_rate=20.0,
            country_code="250",
            commission_ttc=0.0,
            commission_ht=0.0,
            net_amount=0.0,
            payout_date=None,
            payout_reference=None,
            payment_method=None,
            special_type="returns_avoir",
        )
        entries, _ = generate_entries([tx], [], shopify_config)
        port_entries = [e for e in entries if e.account.startswith("7085")]
        assert len(port_entries) == 1
        assert port_entries[0].debit == 10.0
        # piece_number avec suffixe "A" (avoir Shopify)
        for e in entries:
            assert e.piece_number == "#RET_SHIPA"


class TestAccountingRoutingRefundSettlement:
    """Tests du routing accounting pour refund_settlement → settlement_entries only."""

    def test_refund_settlement_generates_settlement_only(self, shopify_config: AppConfig) -> None:
        """refund_settlement ne génère que des écritures PSP (pas d'écritures de vente)."""
        tx = NormalizedTransaction(
            reference="#RET_TEST",
            channel="shopify",
            date=datetime.date(2026, 1, 20),
            type="refund",
            amount_ht=100.0,
            amount_tva=20.0,
            amount_ttc=120.0,
            shipping_ht=0.0,
            shipping_tva=0.0,
            tva_rate=20.0,
            country_code="250",
            commission_ttc=-3.50,
            commission_ht=0.0,
            net_amount=-116.50,
            payout_date=datetime.date(2026, 1, 25),
            payout_reference="P999",
            payment_method="card",
            special_type="refund_settlement",
        )
        entries, anomalies = generate_entries([tx], [], shopify_config)
        assert len(entries) > 0
        entry_types = {e.entry_type for e in entries}
        assert "settlement" in entry_types or "commission" in entry_types
        assert "refund" not in entry_types
        assert "sale" not in entry_types


class TestRetrocompatibilityWithoutReturns:
    """Sans fichier retours, le comportement existant est préservé."""

    def test_parse_without_returns_file(self, shopify_config: AppConfig) -> None:
        """Le parser fonctionne sans le fichier returns dans files dict."""
        sales_csv = (
            "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country\n"
            "#SALE001,2026-01-15,100.00,10.00,22.00,132.00,FR TVA 20%,22.00,Shopify Payments,FR\n"
        )
        tx_csv = (
            "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
            "#SALE001,charge,card,132.00,3.84,128.16,2026-01-23,P001\n"
        )
        files: dict[str, BytesIO] = {
            "sales": BytesIO(sales_csv.encode()),
            "transactions": BytesIO(tx_csv.encode()),
        }
        parser = ShopifyParser()
        result = parser.parse(files, shopify_config)  # type: ignore[arg-type]
        assert len(result.transactions) == 1
        assert result.transactions[0].type == "sale"
        assert result.transactions[0].special_type is None

    def test_refund_without_returns_keeps_original_behavior(self, shopify_config: AppConfig) -> None:
        """Sans fichier retours, les refunds du fichier Transactions gardent special_type=None."""
        sales_csv = (
            "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country\n"
            "#SALE001,2026-01-15,100.00,0.00,20.00,120.00,FR TVA 20%,20.00,Shopify Payments,FR\n"
        )
        tx_csv = (
            "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
            "#SALE001,charge,card,120.00,3.50,116.50,2026-01-23,P001\n"
            "#SALE001,refund,card,-120.00,-3.50,-116.50,2026-01-24,P002\n"
        )
        files: dict[str, BytesIO] = {
            "sales": BytesIO(sales_csv.encode()),
            "transactions": BytesIO(tx_csv.encode()),
        }
        parser = ShopifyParser()
        result = parser.parse(files, shopify_config)  # type: ignore[arg-type]
        refunds = [t for t in result.transactions if t.type == "refund"]
        assert len(refunds) == 1
        assert refunds[0].special_type is None


class TestParseIntegrationWithReturns:
    """Tests d'intégration : parse() avec fichier retours."""

    def test_parse_with_returns_retags_refunds(self, shopify_config: AppConfig) -> None:
        """Quand le fichier retours est présent, les refunds Transactions couverts deviennent refund_settlement."""
        sales_csv = (
            "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country\n"
            "#ORDER1,2026-01-15,100.00,0.00,20.00,120.00,FR TVA 20%,20.00,Shopify Payments,FR\n"
        )
        tx_csv = (
            "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
            "#ORDER1,charge,card,120.00,3.50,116.50,2026-01-23,P001\n"
            "#ORDER1,refund,card,-120.00,-3.50,-116.50,2026-01-24,P002\n"
        )
        returns_csv = (
            "Jour,ID de vente,Nom de la commande,Titre du produit au moment de la vente,"
            "Retours bruts,Réductions retournées,Retours nets,Expédition retournée,"
            "Taxes retournées,Frais de retour,Total des retours\n"
            "2026-01-20,S001,#ORDER1,Produit A,-120.00,0.00,-100.00,0.00,-20.00,0.00,-120.00\n"
        )
        files: dict[str, BytesIO] = {
            "sales": BytesIO(sales_csv.encode()),
            "transactions": BytesIO(tx_csv.encode()),
            "returns": BytesIO(returns_csv.encode()),
        }
        parser = ShopifyParser()
        result = parser.parse(files, shopify_config)  # type: ignore[arg-type]

        # 1 sale + 1 refund_settlement (retagué) + 1 returns_avoir
        refund_settlements = [t for t in result.transactions if t.special_type == "refund_settlement"]
        returns_avoirs = [t for t in result.transactions if t.special_type == "returns_avoir"]
        assert len(refund_settlements) == 1
        assert len(returns_avoirs) == 1

    def test_uncovered_refund_keeps_original(self, shopify_config: AppConfig) -> None:
        """Un refund non couvert par le fichier retours garde special_type=None."""
        sales_csv = (
            "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country\n"
            "#ORDER1,2026-01-15,100.00,0.00,20.00,120.00,FR TVA 20%,20.00,Shopify Payments,FR\n"
            "#ORDER2,2026-01-16,50.00,0.00,10.00,60.00,FR TVA 20%,10.00,Shopify Payments,FR\n"
        )
        tx_csv = (
            "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
            "#ORDER1,charge,card,120.00,3.50,116.50,2026-01-23,P001\n"
            "#ORDER1,refund,card,-120.00,-3.50,-116.50,2026-01-24,P002\n"
            "#ORDER2,charge,card,60.00,2.00,58.00,2026-01-23,P001\n"
            "#ORDER2,refund,card,-60.00,-2.00,-58.00,2026-01-24,P002\n"
        )
        # Retours only covers #ORDER1
        returns_csv = (
            "Jour,ID de vente,Nom de la commande,Titre du produit au moment de la vente,"
            "Retours bruts,Réductions retournées,Retours nets,Expédition retournée,"
            "Taxes retournées,Frais de retour,Total des retours\n"
            "2026-01-20,S001,#ORDER1,Produit A,-120.00,0.00,-100.00,0.00,-20.00,0.00,-120.00\n"
        )
        files: dict[str, BytesIO] = {
            "sales": BytesIO(sales_csv.encode()),
            "transactions": BytesIO(tx_csv.encode()),
            "returns": BytesIO(returns_csv.encode()),
        }
        parser = ShopifyParser()
        result = parser.parse(files, shopify_config)  # type: ignore[arg-type]

        # ORDER1 refund → refund_settlement, ORDER2 refund → None (unchanged)
        order2_refunds = [
            t for t in result.transactions
            if t.reference == "#ORDER2" and t.type == "refund"
        ]
        assert len(order2_refunds) == 1
        assert order2_refunds[0].special_type is None
