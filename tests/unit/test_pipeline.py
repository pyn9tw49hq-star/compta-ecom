"""Tests unitaires pour pipeline.py — branchement contrôles."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from compta_ecom.config.loader import AppConfig, ChannelConfig, PspConfig
from compta_ecom.models import (
    AccountingEntry,
    Anomaly,
    NormalizedTransaction,
    ParseResult,
)
from compta_ecom.pipeline import PipelineOrchestrator


def _make_tx(**overrides: object) -> NormalizedTransaction:
    defaults: dict[str, object] = {
        "reference": "#001",
        "channel": "shopify",
        "date": datetime.date(2026, 1, 15),
        "type": "sale",
        "amount_ht": 100.0,
        "amount_tva": 20.0,
        "amount_ttc": 120.0,
        "shipping_ht": 0.0,
        "shipping_tva": 0.0,
        "tva_rate": 20.0,
        "country_code": "250",
        "commission_ttc": 3.6,
        "commission_ht": 3.0,
        "net_amount": 116.4,
        "payout_date": datetime.date(2026, 1, 20),
        "payout_reference": "P001",
        "payment_method": "card",
        "special_type": None,
    }
    defaults.update(overrides)
    return NormalizedTransaction(**defaults)  # type: ignore[arg-type]


def _make_entry(**overrides: object) -> AccountingEntry:
    defaults: dict[str, object] = {
        "date": datetime.date(2026, 1, 15),
        "journal": "VE",
        "account": "70701250",
        "label": "Vente #001 Shopify",
        "debit": 0.0,
        "credit": 120.0,
        "piece_number": "#001",
        "lettrage": "#001",
        "channel": "shopify",
        "entry_type": "sale",
    }
    defaults.update(overrides)
    return AccountingEntry(**defaults)  # type: ignore[arg-type]


def _make_anomaly(**overrides: object) -> Anomaly:
    defaults: dict[str, object] = {
        "type": "orphan_sale",
        "severity": "warning",
        "reference": "#999",
        "channel": "shopify",
        "detail": "Vente sans transaction",
        "expected_value": None,
        "actual_value": None,
    }
    defaults.update(overrides)
    return Anomaly(**defaults)  # type: ignore[arg-type]


def _make_config() -> AppConfig:
    return AppConfig(
        clients={"shopify": "411SHOPIFY"},
        fournisseurs={},
        psp={"card": PspConfig(compte="51150007", commission="62700002")},
        transit="58000000",
        banque="51200000",
        comptes_speciaux={},
        comptes_vente_prefix="707",
        canal_codes={"shopify": "01"},
        comptes_tva_prefix="4457",
        vat_table={"250": {"name": "France", "rate": 20.0, "alpha2": "FR"}},
        alpha2_to_numeric={"FR": "250"},
        channels={
            "shopify": ChannelConfig(
                files={"sales": "Ventes Shopify*.csv"},
                encoding="utf-8",
                separator=",",
            ),
        },
    )



def _run_pipeline_with_mocks(
    tmp_path: Path,
    config: AppConfig,
    parse_result: ParseResult,
    entries: list[AccountingEntry],
    engine_anomalies: list[Anomaly],
    vat_anomalies: list[Anomaly],
    matching_anomalies: list[Anomaly],
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Run the pipeline with all dependencies mocked. Returns (mock_vat, mock_matching, mock_export)."""
    mock_parser = MagicMock()
    mock_parser.parse.return_value = parse_result

    mock_vat = MagicMock()
    mock_vat.check.return_value = vat_anomalies

    mock_matching = MagicMock()
    mock_matching.check.return_value = matching_anomalies

    mock_export = MagicMock()

    # Create a fake CSV so _detect_files finds something
    sales_file = tmp_path / "Ventes Shopify 2026.csv"
    sales_file.write_text("dummy")

    orchestrator = PipelineOrchestrator()

    with (
        patch("compta_ecom.pipeline.PARSER_REGISTRY", {"shopify": lambda: mock_parser}),
        patch("compta_ecom.pipeline.generate_entries", return_value=(entries, engine_anomalies)),
        patch("compta_ecom.pipeline.VatChecker", mock_vat),
        patch("compta_ecom.pipeline.MatchingChecker", mock_matching),
        patch("compta_ecom.pipeline.export", mock_export),
        patch("compta_ecom.pipeline.print_summary"),
    ):
        orchestrator.run(tmp_path, tmp_path / "out.xlsx", config)

    return mock_vat, mock_matching, mock_export


class TestDetectFilesMultiFiles:
    """Tests _detect_files avec support multi-fichiers."""

    def test_multi_files_returns_list(self, tmp_path: Path) -> None:
        # Arrange
        sub = tmp_path / "Detail transactions par versements"
        sub.mkdir()
        (sub / "payout1.csv").write_text("dummy")
        (sub / "payout2.csv").write_text("dummy")
        (sub / "payout3.csv").write_text("dummy")
        patterns = {
            "sales": "Ventes Shopify*.csv",
            "payout_details": "Detail transactions par versements/*.csv",
        }
        (tmp_path / "Ventes Shopify 2026.csv").write_text("dummy")

        # Act
        result = PipelineOrchestrator._detect_files(tmp_path, patterns, ["payout_details"])

        # Assert
        assert isinstance(result["payout_details"], list)
        assert len(result["payout_details"]) == 3
        assert isinstance(result["sales"], Path)

    def test_multi_files_no_match_key_absent(self, tmp_path: Path) -> None:
        # Arrange
        patterns = {
            "sales": "Ventes Shopify*.csv",
            "payout_details": "Detail transactions par versements/*.csv",
        }
        (tmp_path / "Ventes Shopify 2026.csv").write_text("dummy")

        # Act
        result = PipelineOrchestrator._detect_files(tmp_path, patterns, ["payout_details"])

        # Assert
        assert "payout_details" not in result
        assert "sales" in result

    def test_multi_files_empty_list_standard_behavior(self, tmp_path: Path) -> None:
        # Arrange
        patterns = {"sales": "Ventes Shopify*.csv"}
        (tmp_path / "Ventes Shopify 2026.csv").write_text("dummy")

        # Act
        result = PipelineOrchestrator._detect_files(tmp_path, patterns, [])

        # Assert
        assert isinstance(result["sales"], Path)


class TestPipelineCheckersIntegration:
    """Vérifie que VatChecker et MatchingChecker sont appelés dans run()."""

    def test_vat_checker_called(self, tmp_path: Path) -> None:
        """VatChecker.check() est appelé avec les transactions agrégées."""
        tx = _make_tx()
        config = _make_config()
        parse_result = ParseResult(transactions=[tx], payouts=[], anomalies=[], channel="shopify")

        mock_vat, _, _ = _run_pipeline_with_mocks(
            tmp_path, config, parse_result,
            entries=[_make_entry()], engine_anomalies=[],
            vat_anomalies=[], matching_anomalies=[],
        )

        mock_vat.check.assert_called_once_with([tx], config)

    def test_matching_checker_called(self, tmp_path: Path) -> None:
        """MatchingChecker.check() est appelé avec les transactions agrégées."""
        tx = _make_tx()
        config = _make_config()
        parse_result = ParseResult(transactions=[tx], payouts=[], anomalies=[], channel="shopify")

        _, mock_matching, _ = _run_pipeline_with_mocks(
            tmp_path, config, parse_result,
            entries=[_make_entry()], engine_anomalies=[],
            vat_anomalies=[], matching_anomalies=[],
        )

        mock_matching.check.assert_called_once_with([tx], config)

    def test_anomalies_aggregated(self, tmp_path: Path) -> None:
        """Les anomalies des checkers sont agrégées avec celles des parsers."""
        parser_anomaly = _make_anomaly(type="orphan_sale")
        engine_anomaly = _make_anomaly(type="mixed_psp_payout")
        vat_anomaly = _make_anomaly(type="tva_mismatch")
        matching_anomaly = _make_anomaly(type="amount_mismatch")

        tx = _make_tx()
        config = _make_config()
        parse_result = ParseResult(
            transactions=[tx], payouts=[], anomalies=[parser_anomaly], channel="shopify"
        )

        _, _, mock_export = _run_pipeline_with_mocks(
            tmp_path, config, parse_result,
            entries=[_make_entry()], engine_anomalies=[engine_anomaly],
            vat_anomalies=[vat_anomaly], matching_anomalies=[matching_anomaly],
        )

        call_args = mock_export.call_args
        all_anomalies = call_args[0][1]
        anomaly_types = [a.type for a in all_anomalies]
        assert "orphan_sale" in anomaly_types
        assert "mixed_psp_payout" in anomaly_types
        assert "tva_mismatch" in anomaly_types
        assert "amount_mismatch" in anomaly_types

    def test_all_anomalies_passed_to_export(self, tmp_path: Path) -> None:
        """all_anomalies est passé à export()."""
        vat_anomaly = _make_anomaly(type="unknown_country")
        matching_anomaly = _make_anomaly(type="orphan_refund")

        tx = _make_tx()
        config = _make_config()
        parse_result = ParseResult(transactions=[tx], payouts=[], anomalies=[], channel="shopify")

        _, _, mock_export = _run_pipeline_with_mocks(
            tmp_path, config, parse_result,
            entries=[_make_entry()], engine_anomalies=[],
            vat_anomalies=[vat_anomaly], matching_anomalies=[matching_anomaly],
        )

        call_args = mock_export.call_args
        all_anomalies = call_args[0][1]
        assert len(all_anomalies) == 2
        assert all_anomalies[0].type == "unknown_country"
        assert all_anomalies[1].type == "orphan_refund"


def _make_kpi_config() -> AppConfig:
    """Config avec 2 canaux et 2 pays pour les tests KPI."""
    return AppConfig(
        clients={"shopify": "411SHOPIFY", "manomano": "411MANOMANO"},
        fournisseurs={},
        psp={"card": PspConfig(compte="51150007", commission="62700002")},
        transit="58000000",
        banque="51200000",
        comptes_speciaux={},
        comptes_vente_prefix="707",
        canal_codes={"shopify": "01", "manomano": "02"},
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
            "manomano": ChannelConfig(
                files={"sales": "CA_ManoMano*.csv"},
                encoding="utf-8",
                separator=";",
            ),
        },
    )


def _build_kpi_test_data() -> (
    tuple[list[AccountingEntry], list[ParseResult], AppConfig]
):
    """Jeu de données multi-canal, multi-pays, avec ventes/remboursements/adjustment."""
    config = _make_kpi_config()

    # --- Shopify : 2 ventes (FR + BE) + 1 remboursement (FR) ---
    tx_shopify_sale_fr = _make_tx(
        reference="#S001", channel="shopify", type="sale",
        amount_ht=100.0, amount_tva=20.0, amount_ttc=120.0,
        shipping_ht=10.0, shipping_tva=2.0,
        country_code="250", commission_ttc=-3.6, commission_ht=-3.0,
    )
    tx_shopify_sale_be = _make_tx(
        reference="#S002", channel="shopify", type="sale",
        amount_ht=200.0, amount_tva=42.0, amount_ttc=242.0,
        shipping_ht=15.0, shipping_tva=3.15,
        country_code="056", commission_ttc=-7.26, commission_ht=-6.05,
    )
    tx_shopify_refund_fr = _make_tx(
        reference="#S003", channel="shopify", type="refund",
        amount_ht=-50.0, amount_tva=-10.0, amount_ttc=-60.0,
        shipping_ht=0.0, shipping_tva=0.0,
        country_code="250", commission_ttc=1.8, commission_ht=1.5,
    )

    # --- ManoMano : 1 vente (FR) + 1 ADJUSTMENT (exclue des KPIs) ---
    tx_mano_sale_fr = _make_tx(
        reference="#M001", channel="manomano", type="sale",
        amount_ht=80.0, amount_tva=16.0, amount_ttc=96.0,
        shipping_ht=5.0, shipping_tva=1.0,
        country_code="250", commission_ttc=-12.0, commission_ht=-10.0,
    )
    tx_mano_adjustment = _make_tx(
        reference="#M002", channel="manomano", type="sale",
        amount_ht=5.0, amount_tva=1.0, amount_ttc=6.0,
        shipping_ht=0.0, shipping_tva=0.0,
        country_code="250", commission_ttc=0.0, commission_ht=None,
        special_type="ADJUSTMENT",
    )

    parse_results = [
        ParseResult(
            transactions=[tx_shopify_sale_fr, tx_shopify_sale_be, tx_shopify_refund_fr],
            payouts=[], anomalies=[], channel="shopify",
        ),
        ParseResult(
            transactions=[tx_mano_sale_fr, tx_mano_adjustment],
            payouts=[], anomalies=[], channel="manomano",
        ),
    ]

    entries = [
        _make_entry(entry_type="sale", debit=0.0, credit=120.0),
        _make_entry(entry_type="sale", debit=0.0, credit=242.0),
        _make_entry(entry_type="settlement", debit=116.4, credit=0.0),
    ]

    return entries, parse_results, config


class TestBuildSummaryKPIs:
    """Tests pour les KPIs financiers de _build_summary() (AC 1-12)."""

    def test_ca_par_canal(self) -> None:
        """CA HT et TTC par canal — ventes uniquement, special_type exclues (AC2, AC12)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        ca = summary["ca_par_canal"]
        # Shopify: HT = (100+10) + (200+15) = 325, TTC = 120 + 242 = 362
        assert ca["shopify"] == {"ht": 325.0, "ttc": 362.0}
        # ManoMano: HT = 80+5 = 85, TTC = 96 (ADJUSTMENT exclue)
        assert ca["manomano"] == {"ht": 85.0, "ttc": 96.0}

    def test_remboursements_par_canal(self) -> None:
        """Remboursements count + montants en valeur absolue (AC3, AC12)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        remb = summary["remboursements_par_canal"]
        # Shopify: 1 refund, HT=abs(-50+0)=50, TTC=abs(-60)=60
        assert remb["shopify"] == {"count": 1, "ht": 50.0, "ttc": 60.0}
        # ManoMano: 0 refunds
        assert remb["manomano"] == {"count": 0, "ht": 0.0, "ttc": 0.0}

    def test_taux_remboursement_par_canal(self) -> None:
        """Taux de remboursement = nb_refunds / nb_sales * 100 (AC4)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        taux = summary["taux_remboursement_par_canal"]
        # Shopify: 1 refund / 2 sales = 50.0%
        assert taux["shopify"] == 50.0
        # ManoMano: 0 / 1 = 0.0%
        assert taux["manomano"] == 0.0

    def test_commissions_par_canal(self) -> None:
        """Commissions en valeur absolue, toutes transactions normales (AC5)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        comm = summary["commissions_par_canal"]
        # Shopify: TTC = |−3.6|+|−7.26|+|1.8| = 12.66, HT = |−3|+|−6.05|+|1.5| = 10.55
        assert comm["shopify"] == {"ht": 10.55, "ttc": 12.66}
        # ManoMano: TTC = |−12| = 12, HT = |−10| = 10
        assert comm["manomano"] == {"ht": 10.0, "ttc": 12.0}

    def test_net_vendeur_par_canal(self) -> None:
        """Net vendeur = CA TTC − |Commissions TTC| − Remboursements TTC (AC6)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        net = summary["net_vendeur_par_canal"]
        # Shopify: 362 − 12.66 − 60 = 289.34
        assert net["shopify"] == 289.34
        # ManoMano: 96 − 12 − 0 = 84
        assert net["manomano"] == 84.0

    def test_tva_collectee_par_canal(self) -> None:
        """TVA collectée = amount_tva + shipping_tva des ventes (AC7)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        tva = summary["tva_collectee_par_canal"]
        # Shopify: (20+2) + (42+3.15) = 67.15
        assert tva["shopify"] == 67.15
        # ManoMano: 16+1 = 17
        assert tva["manomano"] == 17.0

    def test_repartition_geo_globale(self) -> None:
        """Répartition géographique globale, triée par CA TTC desc (AC8)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        geo = summary["repartition_geo_globale"]
        # Belgique: count=1, ca_ttc=242 > France: count=2, ca_ttc=216
        countries = list(geo.keys())
        assert countries == ["Belgique", "France"]
        assert geo["Belgique"] == {"count": 1, "ca_ttc": 242.0, "ca_ht": 215.0}
        assert geo["France"] == {"count": 2, "ca_ttc": 216.0, "ca_ht": 195.0}

    def test_repartition_geo_par_canal(self) -> None:
        """Répartition géographique par canal, triée par CA TTC desc (AC9)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        geo_canal = summary["repartition_geo_par_canal"]
        # ManoMano: France seulement
        assert list(geo_canal["manomano"].keys()) == ["France"]
        assert geo_canal["manomano"]["France"] == {"count": 1, "ca_ttc": 96.0, "ca_ht": 85.0}
        # Shopify: Belgique (242) > France (120)
        assert list(geo_canal["shopify"].keys()) == ["Belgique", "France"]
        assert geo_canal["shopify"]["Belgique"] == {"count": 1, "ca_ttc": 242.0, "ca_ht": 215.0}
        assert geo_canal["shopify"]["France"] == {"count": 1, "ca_ttc": 120.0, "ca_ht": 110.0}

    def test_existing_keys_unchanged(self) -> None:
        """Les 3 clés existantes restent intactes (AC11)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        # transactions_par_canal: shopify=3, manomano=2 (incl. ADJUSTMENT)
        assert summary["transactions_par_canal"]["shopify"] == 3
        assert summary["transactions_par_canal"]["manomano"] == 2
        # ecritures_par_type
        assert summary["ecritures_par_type"]["sale"] == 2
        assert summary["ecritures_par_type"]["settlement"] == 1
        # totaux
        assert summary["totaux"]["debit"] == 116.4
        assert summary["totaux"]["credit"] == 362.0

    def test_special_type_excluded_from_kpis(self) -> None:
        """Les transactions special_type sont exclues des KPIs (AC12)."""
        entries, parse_results, config = _build_kpi_test_data()
        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)

        # ManoMano ADJUSTMENT (6 TTC) ne doit pas être dans le CA
        assert summary["ca_par_canal"]["manomano"]["ttc"] == 96.0

    def test_unknown_country_fallback(self) -> None:
        """Country code inconnu → 'Pays inconnu (code)' (Dev Notes)."""
        config = _make_kpi_config()
        tx = _make_tx(
            reference="#U001", channel="shopify", type="sale",
            amount_ht=50.0, amount_tva=10.0, amount_ttc=60.0,
            shipping_ht=0.0, shipping_tva=0.0,
            country_code="999", commission_ttc=-1.5, commission_ht=-1.25,
        )
        parse_results = [
            ParseResult(transactions=[tx], payouts=[], anomalies=[], channel="shopify"),
        ]
        entries = [_make_entry()]

        summary = PipelineOrchestrator()._build_summary(entries, parse_results, config)
        geo = summary["repartition_geo_globale"]
        assert "Pays inconnu (999)" in geo
