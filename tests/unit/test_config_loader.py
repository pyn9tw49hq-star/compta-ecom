"""Tests unitaires pour le module config_loader."""

from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig, load_config
from compta_ecom.models import ConfigError


VALID_CHART = """\
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
"""

VALID_VAT = """\
countries:
  "250":
    name: "France"
    rate: 20.0
    alpha2: "FR"
"""

VALID_CHANNELS = """\
channels:
  shopify:
    files:
      sales: "Ventes Shopify*.csv"
    encoding: utf-8
    separator: ","
"""


def _write_configs(tmp_path: Path, chart: str = VALID_CHART, vat: str = VALID_VAT, channels: str = VALID_CHANNELS) -> None:
    """Helper pour écrire les 3 fichiers de config."""
    (tmp_path / "chart_of_accounts.yaml").write_text(chart)
    (tmp_path / "vat_table.yaml").write_text(vat)
    (tmp_path / "channels.yaml").write_text(channels)


class TestLoadConfigValid:
    def test_load_config_valid(self, tmp_path: Path) -> None:
        _write_configs(tmp_path)
        config = load_config(tmp_path)

        assert isinstance(config, AppConfig)
        assert config.clients["shopify"] == "411SHOPIFY"
        assert config.fournisseurs["manomano"] == "FMANO"
        assert config.psp["card"].compte == "51150007"
        assert config.psp["card"].commission == "62700002"
        assert config.transit == "58000000"
        assert config.banque == "512"
        assert config.comptes_vente_prefix == "707"
        assert config.canal_codes["shopify"] == "01"
        assert config.comptes_tva_prefix == "4457"
        assert config.vat_table["250"]["rate"] == 20.0
        assert config.vat_table["250"]["name"] == "France"
        assert config.vat_table["250"]["alpha2"] == "FR"
        assert config.alpha2_to_numeric == {"FR": "250"}
        assert config.channels["shopify"].separator == ","
        assert config.channels["shopify"].encoding == "utf-8"
        assert config.channels["shopify"].files["sales"] == "Ventes Shopify*.csv"


class TestLoadConfigMissingFiles:
    def test_chart_missing(self, tmp_path: Path) -> None:
        (tmp_path / "vat_table.yaml").write_text(VALID_VAT)
        (tmp_path / "channels.yaml").write_text(VALID_CHANNELS)
        with pytest.raises(ConfigError, match="chart_of_accounts.yaml"):
            load_config(tmp_path)

    def test_vat_missing(self, tmp_path: Path) -> None:
        (tmp_path / "chart_of_accounts.yaml").write_text(VALID_CHART)
        (tmp_path / "channels.yaml").write_text(VALID_CHANNELS)
        with pytest.raises(ConfigError, match="vat_table.yaml"):
            load_config(tmp_path)

    def test_channels_missing(self, tmp_path: Path) -> None:
        (tmp_path / "chart_of_accounts.yaml").write_text(VALID_CHART)
        (tmp_path / "vat_table.yaml").write_text(VALID_VAT)
        with pytest.raises(ConfigError, match="channels.yaml"):
            load_config(tmp_path)


class TestLoadConfigEmptyFile:
    def test_empty_yaml_file(self, tmp_path: Path) -> None:
        (tmp_path / "chart_of_accounts.yaml").write_text("")
        (tmp_path / "vat_table.yaml").write_text(VALID_VAT)
        (tmp_path / "channels.yaml").write_text(VALID_CHANNELS)
        with pytest.raises(ConfigError, match="mapping YAML"):
            load_config(tmp_path)


class TestLoadConfigMalformedYaml:
    def test_malformed_yaml(self, tmp_path: Path) -> None:
        _write_configs(tmp_path, chart="[invalid: yaml: {{{")
        with pytest.raises(ConfigError, match="YAML malformé"):
            load_config(tmp_path)


class TestLoadConfigMissingKeys:
    def test_clients_missing(self, tmp_path: Path) -> None:
        chart_no_clients = """\
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
"""
        _write_configs(tmp_path, chart=chart_no_clients)
        with pytest.raises(ConfigError, match="clients"):
            load_config(tmp_path)

    def test_transit_missing(self, tmp_path: Path) -> None:
        chart_no_transit = """\
clients:
  shopify: "411SHOPIFY"
fournisseurs:
  manomano: "FMANO"
psp:
  card:
    compte: "51150007"
banque: "512"
comptes_vente:
  prefix: "707"
  canal_codes:
    shopify: "01"
comptes_tva:
  prefix: "4457"
"""
        _write_configs(tmp_path, chart=chart_no_transit)
        with pytest.raises(ConfigError, match="transit"):
            load_config(tmp_path)


class TestLoadConfigVatValidation:
    def test_negative_rate(self, tmp_path: Path) -> None:
        vat_negative = """\
countries:
  "250":
    name: "France"
    rate: -5.0
    alpha2: "FR"
"""
        _write_configs(tmp_path, vat=vat_negative)
        with pytest.raises(ConfigError, match="négatif"):
            load_config(tmp_path)

    def test_rate_over_100(self, tmp_path: Path) -> None:
        vat_over = """\
countries:
  "250":
    name: "France"
    rate: 150.0
    alpha2: "FR"
"""
        _write_configs(tmp_path, vat=vat_over)
        with pytest.raises(ConfigError, match="100"):
            load_config(tmp_path)


class TestLoadConfigChannelValidation:
    def test_unsupported_encoding(self, tmp_path: Path) -> None:
        channels_bad_enc = """\
channels:
  shopify:
    files:
      sales: "Ventes*.csv"
    encoding: cp1252
    separator: ","
"""
        _write_configs(tmp_path, channels=channels_bad_enc)
        with pytest.raises(ConfigError, match="cp1252"):
            load_config(tmp_path)

    def test_invalid_separator(self, tmp_path: Path) -> None:
        channels_bad_sep = """\
channels:
  shopify:
    files:
      sales: "Ventes*.csv"
    encoding: utf-8
    separator: "\\t"
"""
        _write_configs(tmp_path, channels=channels_bad_sep)
        with pytest.raises(ConfigError, match="non supporté"):
            load_config(tmp_path)

    def test_empty_file_pattern(self, tmp_path: Path) -> None:
        channels_empty_pattern = """\
channels:
  shopify:
    files:
      sales: ""
    encoding: utf-8
    separator: ","
"""
        _write_configs(tmp_path, channels=channels_empty_pattern)
        with pytest.raises(ConfigError, match="Pattern fichier vide"):
            load_config(tmp_path)


class TestLoadConfigAlpha2Validation:
    def test_alpha2_missing(self, tmp_path: Path) -> None:
        vat_no_alpha2 = """\
countries:
  "250":
    name: "France"
    rate: 20.0
"""
        _write_configs(tmp_path, vat=vat_no_alpha2)
        with pytest.raises(ConfigError, match="alpha2"):
            load_config(tmp_path)

    def test_alpha2_invalid_length(self, tmp_path: Path) -> None:
        vat_bad_alpha2 = """\
countries:
  "250":
    name: "France"
    rate: 20.0
    alpha2: "FRA"
"""
        _write_configs(tmp_path, vat=vat_bad_alpha2)
        with pytest.raises(ConfigError, match="alpha2"):
            load_config(tmp_path)

    def test_alpha2_to_numeric_mapping(self, tmp_path: Path) -> None:
        vat_multi = """\
countries:
  "250":
    name: "France"
    rate: 20.0
    alpha2: "FR"
  "056":
    name: "Belgique"
    rate: 21.0
    alpha2: "BE"
"""
        _write_configs(tmp_path, vat=vat_multi)
        config = load_config(tmp_path)
        assert config.alpha2_to_numeric == {"FR": "250", "BE": "056"}


class TestMultiFiles:
    def test_multi_files_parsed(self, tmp_path: Path) -> None:
        channels_mf = """\
channels:
  shopify:
    files:
      sales: "Ventes Shopify*.csv"
      payout_details: "Detail transactions par versements/*.csv"
    multi_files: ["payout_details"]
    encoding: utf-8
    separator: ","
"""
        _write_configs(tmp_path, channels=channels_mf)
        config = load_config(tmp_path)
        assert config.channels["shopify"].multi_files == ["payout_details"]

    def test_multi_files_absent_defaults_empty(self, tmp_path: Path) -> None:
        _write_configs(tmp_path)
        config = load_config(tmp_path)
        assert config.channels["shopify"].multi_files == []

    def test_multi_files_invalid_key_raises(self, tmp_path: Path) -> None:
        channels_bad = """\
channels:
  shopify:
    files:
      sales: "Ventes Shopify*.csv"
    multi_files: ["inexistant"]
    encoding: utf-8
    separator: ","
"""
        _write_configs(tmp_path, channels=channels_bad)
        with pytest.raises(ConfigError, match="inexistant"):
            load_config(tmp_path)


class TestMatchingTolerance:
    def test_matching_tolerance_explicit(self, tmp_path: Path) -> None:
        chart_with_tolerance = VALID_CHART + "matching_tolerance: 0.05\n"
        _write_configs(tmp_path, chart=chart_with_tolerance)
        config = load_config(tmp_path)
        assert config.matching_tolerance == 0.05

    def test_matching_tolerance_fallback(self, tmp_path: Path) -> None:
        _write_configs(tmp_path)
        config = load_config(tmp_path)
        assert config.matching_tolerance == 0.01
