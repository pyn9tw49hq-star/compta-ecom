"""Tests unitaires pour le point d'entrée CLI main.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from compta_ecom.main import main, parse_args


class TestParseArgs:
    def test_valid_args(self) -> None:
        args = parse_args(["./input", "output.xlsx"])
        assert args.input_dir == "./input"
        assert args.output_file == "output.xlsx"
        assert args.config_dir == "./config/"
        assert args.log_level == "INFO"

    def test_missing_args(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            parse_args([])
        assert exc_info.value.code == 2

    def test_custom_config_dir(self) -> None:
        args = parse_args(["./input", "output.xlsx", "--config-dir", "/custom/config"])
        assert args.config_dir == "/custom/config"

    def test_log_level_debug(self) -> None:
        args = parse_args(["./input", "output.xlsx", "--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"

    def test_log_level_invalid(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["./input", "output.xlsx", "--log-level", "VERBOSE"])
        assert exc_info.value.code == 2


class TestMain:
    def test_valid_config(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "chart_of_accounts.yaml").write_text("""\
clients:
  shopify: "411SHOPIFY"
fournisseurs:
  manomano: "FMANO"
psp:
  card:
    compte: "51150007"
    commission: "62700002"
transit: "58000000"
banque: "512"
comptes_vente:
  prefix: "707"
  canal_codes:
    shopify: "01"
comptes_tva:
  prefix: "4457"
""")
        (config_dir / "vat_table.yaml").write_text("""\
countries:
  "250":
    name: "France"
    rate: 20.0
    alpha2: "FR"
""")
        (config_dir / "channels.yaml").write_text("""\
channels:
  shopify:
    files:
      sales: "Ventes Shopify*.csv"
    encoding: utf-8
    separator: ","
""")
        # No CSV files → exit code 3 (no results)
        with pytest.raises(SystemExit) as exc_info:
            main(["./input", "output.xlsx", "--config-dir", str(config_dir)])
        assert exc_info.value.code == 3

    def test_config_dir_missing(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(SystemExit) as exc_info:
            main(["./input", "output.xlsx", "--config-dir", str(nonexistent)])
        assert exc_info.value.code == 2

    def test_log_level_applied(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "chart_of_accounts.yaml").write_text("""\
clients:
  shopify: "411SHOPIFY"
fournisseurs:
  manomano: "FMANO"
psp:
  card:
    compte: "51150007"
    commission: "62700002"
transit: "58000000"
banque: "512"
comptes_vente:
  prefix: "707"
  canal_codes:
    shopify: "01"
comptes_tva:
  prefix: "4457"
""")
        (config_dir / "vat_table.yaml").write_text("""\
countries:
  "250":
    name: "France"
    rate: 20.0
    alpha2: "FR"
""")
        (config_dir / "channels.yaml").write_text("""\
channels:
  shopify:
    files:
      sales: "Ventes Shopify*.csv"
    encoding: utf-8
    separator: ","
""")
        with patch("logging.basicConfig") as mock_basic:
            with pytest.raises(SystemExit) as exc_info:
                main(["./input", "output.xlsx", "--config-dir", str(config_dir), "--log-level", "DEBUG"])
            assert exc_info.value.code == 3
            mock_basic.assert_called_once()
            call_kwargs = mock_basic.call_args
            assert call_kwargs[1]["level"] == 10  # logging.DEBUG
