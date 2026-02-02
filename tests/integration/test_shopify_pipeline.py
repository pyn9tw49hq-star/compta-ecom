"""Tests d'intégration pour le pipeline Shopify complet."""

from __future__ import annotations

import shutil
from pathlib import Path

import openpyxl
import pytest

from compta_ecom.config.loader import load_config
from compta_ecom.main import main
from compta_ecom.models import NoResultError
from compta_ecom.pipeline import PipelineOrchestrator

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SHOPIFY_FIXTURES = FIXTURES_DIR / "shopify"
CONFIG_FIXTURES = FIXTURES_DIR / "config"


class TestPipelineNominal:
    """Pipeline nominal : 3 CSV → Excel avec 3 types d'écritures."""

    def test_nominal_excel_output(self, tmp_path: Path) -> None:
        """3 fichiers CSV Shopify → Excel avec 2 onglets, écritures des 3 types."""
        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"

        orchestrator = PipelineOrchestrator()
        orchestrator.run(SHOPIFY_FIXTURES, output, config)

        assert output.exists()

        wb = openpyxl.load_workbook(output)
        assert "Écritures" in wb.sheetnames
        assert "Anomalies" in wb.sheetnames

        ws_entries = wb["Écritures"]
        data_rows = list(ws_entries.iter_rows(min_row=2, values_only=True))
        assert len(data_rows) > 0

        # Check 3 entry types present
        entry_types = {row[9] for row in data_rows}  # entry_type is column 10 (index 9)
        assert "sale" in entry_types
        assert "settlement" in entry_types
        assert "payout" in entry_types

        wb.close()

    def test_anomalies_sheet_has_headers(self, tmp_path: Path) -> None:
        """L'onglet Anomalies a des en-têtes même si aucune anomalie critique."""
        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"

        orchestrator = PipelineOrchestrator()
        orchestrator.run(SHOPIFY_FIXTURES, output, config)

        wb = openpyxl.load_workbook(output)
        ws_anomalies = wb["Anomalies"]
        headers = [cell.value for cell in ws_anomalies[1]]
        assert "type" in headers
        assert "severity" in headers
        assert "detail" in headers
        wb.close()


class TestPipelineWithAnomalies:
    """Pipeline avec anomalies : commande orpheline."""

    def test_orphan_sale_anomaly(self, tmp_path: Path) -> None:
        """CSV ventes avec une commande orpheline → onglet Anomalies non vide."""
        # Create modified sales CSV with an extra order not in transactions
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Copy transactions and versements as-is
        shutil.copy(SHOPIFY_FIXTURES / "transactions.csv", input_dir / "transactions.csv")
        shutil.copy(SHOPIFY_FIXTURES / "versements.csv", input_dir / "versements.csv")

        # Create modified sales with an orphan order
        sales_content = (SHOPIFY_FIXTURES / "ventes.csv").read_text()
        sales_content += '#ORPHAN99,2026-01-18,30.00,0.00,6.00,36.00,FR TVA 20%,6.00,Shopify Payments,FR\n'
        (input_dir / "ventes.csv").write_text(sales_content)

        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"

        orchestrator = PipelineOrchestrator()
        orchestrator.run(input_dir, output, config)

        wb = openpyxl.load_workbook(output)
        ws_anomalies = wb["Anomalies"]
        data_rows = list(ws_anomalies.iter_rows(min_row=2, values_only=True))
        anomaly_types = [row[0] for row in data_rows]
        assert "orphan_sale" in anomaly_types
        wb.close()


class TestPipelineNoFiles:
    """Pipeline sans fichiers : répertoire vide → aucun résultat."""

    def test_empty_directory_raises(self, tmp_path: Path) -> None:
        """Répertoire vide → NoResultError."""
        input_dir = tmp_path / "empty_input"
        input_dir.mkdir()
        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"

        orchestrator = PipelineOrchestrator()
        with pytest.raises(NoResultError):
            orchestrator.run(input_dir, output, config)

        assert not output.exists()


class TestPipelineChannelError:
    """Pipeline canal en erreur : CSV malformé."""

    def test_malformed_csv_parse_error(self, tmp_path: Path, capsys: object) -> None:
        """CSV malformé (colonne manquante) → ParseError catchée, résumé mentionne l'erreur."""
        import _pytest.capture

        assert isinstance(capsys, _pytest.capture.CaptureFixture)

        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create a malformed sales CSV (missing required columns)
        (input_dir / "ventes.csv").write_text("BadCol1,BadCol2\nfoo,bar\n")
        # Provide valid transactions + versements so that parse error is on sales only
        shutil.copy(SHOPIFY_FIXTURES / "transactions.csv", input_dir / "transactions.csv")
        shutil.copy(SHOPIFY_FIXTURES / "versements.csv", input_dir / "versements.csv")

        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"

        orchestrator = PipelineOrchestrator()
        # sales file is malformed → ParseError → caught → NoResultError (only 1 channel)
        with pytest.raises(NoResultError):
            orchestrator.run(input_dir, output, config)


class TestCLIExitCodes:
    """Tests des exit codes CLI."""

    def test_exit_code_0_nominal(self, tmp_path: Path) -> None:
        """Pipeline nominal via main() → exit code 0 (pas de SystemExit)."""
        output = tmp_path / "output.xlsx"
        main([
            str(SHOPIFY_FIXTURES),
            str(output),
            "--config-dir",
            str(CONFIG_FIXTURES),
            "--log-level",
            "WARNING",
        ])
        assert output.exists()

    def test_exit_code_3_no_results(self, tmp_path: Path) -> None:
        """Répertoire vide via main() → exit code 3."""
        input_dir = tmp_path / "empty"
        input_dir.mkdir()
        output = tmp_path / "output.xlsx"

        with pytest.raises(SystemExit) as exc_info:
            main([
                str(input_dir),
                str(output),
                "--config-dir",
                str(CONFIG_FIXTURES),
                "--log-level",
                "WARNING",
            ])
        assert exc_info.value.code == 3


DETAIL_FIXTURES = SHOPIFY_FIXTURES / "detail_versements"


class TestPipelineDetailedLettrage:
    """AC19 : Pipeline avec detail_versements → lettrage identique entre settlement et payout sur 511."""

    def test_lettrage_settlement_payout_match(self, tmp_path: Path) -> None:
        """Pour une commande donnée, settlement et payout partagent le même lettrage sur le compte 511."""
        # Setup input directory with all files
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        shutil.copy(SHOPIFY_FIXTURES / "ventes.csv", input_dir / "ventes.csv")
        shutil.copy(SHOPIFY_FIXTURES / "transactions.csv", input_dir / "transactions.csv")
        shutil.copy(SHOPIFY_FIXTURES / "versements.csv", input_dir / "versements.csv")

        # Copy detail_versements files
        for detail_file in DETAIL_FIXTURES.glob("*.csv"):
            shutil.copy(detail_file, input_dir / detail_file.name)

        # Load config and add payout_details to shopify channel
        config = load_config(CONFIG_FIXTURES)
        config.channels["shopify"].files["payout_details"] = "detail_*.csv"
        config.channels["shopify"].multi_files = ["payout_details"]

        output = tmp_path / "output.xlsx"
        orchestrator = PipelineOrchestrator()
        orchestrator.run(input_dir, output, config)

        assert output.exists()

        wb = openpyxl.load_workbook(output)
        ws = wb["Écritures"]
        headers = [cell.value for cell in ws[1]]
        data_rows = list(ws.iter_rows(min_row=2, values_only=True))
        wb.close()

        # Build column index map
        col = {name: idx for idx, name in enumerate(headers)}

        # Collect entries on 511 accounts by lettrage (now = payout_reference)
        entries_511_by_lettrage: dict[str, list[tuple]] = {}

        for row in data_rows:
            account = row[col["account"]]
            lettrage = row[col["lettrage"]]

            if account is None or not str(account).startswith("511"):
                continue
            if not lettrage:
                continue

            entries_511_by_lettrage.setdefault(lettrage, []).append(row)

        # Verify: at least one lettrage group exists with both settlement and payout entries
        assert len(entries_511_by_lettrage) > 0, "No 511 entries with lettrage found"

        for lettrage, rows in entries_511_by_lettrage.items():
            entry_types = {r[col["entry_type"]] for r in rows}
            # Each lettrage group should have settlement AND payout entries (same payout_reference)
            assert "settlement" in entry_types, f"Lettrage {lettrage}: missing settlement entries"
            assert "payout" in entry_types, f"Lettrage {lettrage}: missing payout entries"

            # Each group must be balanced (sum debits == sum credits)
            total_debit = sum(r[col["debit"]] or 0 for r in rows)
            total_credit = sum(r[col["credit"]] or 0 for r in rows)
            assert round(total_debit, 2) == round(total_credit, 2), (
                f"Lettrage {lettrage}: déséquilibre D={total_debit} C={total_credit}"
            )
