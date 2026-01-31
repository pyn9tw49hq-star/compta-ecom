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
