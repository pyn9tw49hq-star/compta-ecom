"""Tests pour le parser ManoMano (CA, Versements et Detail commandes)."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

import pandas as pd
import pytest

from compta_ecom.config.loader import AppConfig, ChannelConfig
from compta_ecom.models import ParseError
from compta_ecom.parsers.manomano import ManoManoParser


# --- Helpers ---


def _make_ca_df(**overrides: object) -> pd.DataFrame:
    """Crée un DataFrame CA minimal avec une ligne ORDER."""
    data: dict[str, list[object]] = {
        "reference": ["M001"],
        "type": ["ORDER"],
        "createdAt": ["2026-01-15"],
        "amountVatIncl": [120.00],
        "commissionVatIncl": [-18.00],
        "commissionVatExcl": [-15.00],
        "vatOnCommission": [-3.00],
        "netAmount": [102.00],
        "productPriceVatExcl": [83.33],
        "vatOnProduct": [16.67],
        "shippingPriceVatExcl": [8.33],
        "vatOnShipping": [1.67],
    }
    for k, v in overrides.items():
        data[k] = [v]
    return pd.DataFrame(data)


def _make_payout_df(rows: list[dict[str, object]] | None = None) -> pd.DataFrame:
    """Crée un DataFrame Versements minimal."""
    if rows is None:
        rows = [
            {
                "REFERENCE": "M001",
                "TYPE": "ORDER",
                "PAYOUT_REFERENCE": "PAY001",
                "PAYOUT_DATE": "2026-01-31",
                "AMOUNT": 102.00,
            },
        ]
    return pd.DataFrame(rows)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    """Écrit un DataFrame en CSV avec séparateur ';'."""
    df.to_csv(path, sep=";", index=False)


def _config_without_country_code(sample_config: AppConfig) -> AppConfig:
    """Retourne une config avec default_country_code=None pour manomano."""
    sample_config.channels["manomano"] = ChannelConfig(
        files={"ca": "CA Manomano*.csv", "payouts": "Detail versement Manomano*.csv"},
        encoding="utf-8",
        separator=";",
        default_country_code=None,
    )
    return sample_config


# =============================================================================
# Tâche 3 : Tests parsing CA
# =============================================================================


class TestParseCA:
    """Tests pour _parse_ca()."""

    def test_nominal_order(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """ORDER → dict avec montants positifs, type='sale'."""
        # Arrange
        df = _make_ca_df()
        ca_path = tmp_path / "ca.csv"
        _write_csv(df, ca_path)
        parser = ManoManoParser()

        # Act
        rows, anomalies = parser._parse_ca(ca_path, sample_config)

        # Assert
        assert len(rows) == 1
        assert len(anomalies) == 0
        row = rows[0]
        assert row["reference"] == "M001"
        assert row["type"] == "sale"
        assert row["amount_ht"] == 83.33
        assert row["amount_tva"] == 16.67
        assert row["amount_ttc"] == 120.00
        assert row["shipping_ht"] == 8.33
        assert row["shipping_tva"] == 1.67
        assert row["commission_ttc"] == -18.00
        assert row["commission_ht"] == -15.00
        assert row["net_amount"] == 102.00
        assert row["country_code"] == "250"
        assert row["tva_rate"] == 20.0
        assert row["payment_method"] is None if "payment_method" in row else True
        assert row.get("special_type") is None

    def test_nominal_refund(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """REFUND → montants positifs (abs), type='refund', commission signée."""
        # Arrange
        df = _make_ca_df(
            type="REFUND",
            amountVatIncl=-120.00,
            productPriceVatExcl=-83.33,
            vatOnProduct=-16.67,
            shippingPriceVatExcl=-8.33,
            vatOnShipping=-1.67,
            commissionVatIncl=18.00,
            commissionVatExcl=15.00,
            vatOnCommission=3.00,
            netAmount=-102.00,
        )
        ca_path = tmp_path / "ca.csv"
        _write_csv(df, ca_path)
        parser = ManoManoParser()

        # Act
        rows, anomalies = parser._parse_ca(ca_path, sample_config)

        # Assert
        assert len(rows) == 1
        assert len(anomalies) == 0
        row = rows[0]
        assert row["type"] == "refund"
        assert row["amount_ht"] == 83.33
        assert row["amount_tva"] == 16.67
        assert row["amount_ttc"] == 120.00
        assert row["shipping_ht"] == 8.33
        assert row["shipping_tva"] == 1.67
        assert row["commission_ttc"] == 18.00

    def test_unknown_type(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Type inconnu → Anomaly(type='unknown_transaction_type'), ligne ignorée."""
        # Arrange
        df = _make_ca_df(type="PARTIAL_REFUND")
        ca_path = tmp_path / "ca.csv"
        _write_csv(df, ca_path)
        parser = ManoManoParser()

        # Act
        rows, anomalies = parser._parse_ca(ca_path, sample_config)

        # Assert
        assert len(rows) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "unknown_transaction_type"
        assert anomalies[0].reference == "M001"

    def test_missing_column(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Colonne manquante → ParseError."""
        # Arrange
        df = _make_ca_df()
        df = df.drop(columns=["amountVatIncl"])
        ca_path = tmp_path / "ca.csv"
        _write_csv(df, ca_path)
        parser = ManoManoParser()

        # Act & Assert
        with pytest.raises(ParseError, match="amountVatIncl"):
            parser._parse_ca(ca_path, sample_config)

    def test_non_numeric_value(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Valeur non-numérique → Anomaly(type='parse_warning'), ligne ignorée."""
        # Arrange
        df = _make_ca_df(amountVatIncl="N/A")
        ca_path = tmp_path / "ca.csv"
        _write_csv(df, ca_path)
        parser = ManoManoParser()

        # Act
        rows, anomalies = parser._parse_ca(ca_path, sample_config)

        # Assert
        assert len(rows) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "parse_warning"

    def test_default_country_code_none(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """default_country_code=None → ParseError."""
        # Arrange
        config = _config_without_country_code(sample_config)
        df = _make_ca_df()
        ca_path = tmp_path / "ca.csv"
        _write_csv(df, ca_path)
        parser = ManoManoParser()

        # Act & Assert
        with pytest.raises(ParseError, match="default_country_code"):
            parser._parse_ca(ca_path, config)

    def test_tva_rate_from_vat_table(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """tva_rate résolu via vat_table['250']."""
        # Arrange
        df = _make_ca_df()
        ca_path = tmp_path / "ca.csv"
        _write_csv(df, ca_path)
        parser = ManoManoParser()

        # Act
        rows, _ = parser._parse_ca(ca_path, sample_config)

        # Assert
        assert rows[0]["tva_rate"] == 20.0

    def test_empty_date(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Date vide → date=None dans le dict (fallback résolu en matching)."""
        # Arrange
        df = _make_ca_df(createdAt="")
        ca_path = tmp_path / "ca.csv"
        _write_csv(df, ca_path)
        parser = ManoManoParser()

        # Act
        rows, anomalies = parser._parse_ca(ca_path, sample_config)

        # Assert
        assert len(rows) == 1
        assert rows[0]["date"] is None
        assert len(anomalies) == 0


# =============================================================================
# Tâche 5 : Tests parsing Versements
# =============================================================================


class TestParsePayouts:
    """Tests pour _parse_payout_lines() + _aggregate_payout_summaries()."""

    def test_nominal_order_refund_lookup(self, sample_config: AppConfig) -> None:
        """ORDER + REFUND → lookup_dict correct."""
        # Arrange
        df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 102.00},
            {"REFERENCE": "M002", "TYPE": "REFUND", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -50.00},
        ])
        parser = ManoManoParser()

        # Act
        specials, lookup, anomalies = parser._parse_payout_lines(df, sample_config)

        # Assert
        assert len(specials) == 0
        assert len(anomalies) == 0
        assert "M001" in lookup
        assert "M002" in lookup
        assert lookup["M001"] == (datetime.date(2026, 1, 31), "PAY001")

    def test_special_adjustment(self, sample_config: AppConfig) -> None:
        """ADJUSTMENT → special_type='ADJUSTMENT', montants classiques à 0.00, net_amount signé."""
        # Arrange
        df = _make_payout_df([
            {"REFERENCE": "ADJ001", "TYPE": "ADJUSTMENT", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -5.50},
        ])
        parser = ManoManoParser()

        # Act
        specials, lookup, anomalies = parser._parse_payout_lines(df, sample_config)

        # Assert
        assert len(specials) == 1
        assert specials[0]["special_type"] == "ADJUSTMENT"
        assert specials[0]["type"] == "sale"
        assert specials[0]["net_amount"] == -5.50
        assert specials[0]["date"] == datetime.date(2026, 1, 31)

    def test_special_eco_contribution(self, sample_config: AppConfig) -> None:
        """ECO_CONTRIBUTION → special_type correct."""
        df = _make_payout_df([
            {"REFERENCE": "ECO001", "TYPE": "ECO_CONTRIBUTION", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -2.00},
        ])
        parser = ManoManoParser()
        specials, _, _ = parser._parse_payout_lines(df, sample_config)
        assert specials[0]["special_type"] == "ECO_CONTRIBUTION"

    def test_special_subscription(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION → special_type correct."""
        df = _make_payout_df([
            {"REFERENCE": "SUB001", "TYPE": "SUBSCRIPTION", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -39.90},
        ])
        parser = ManoManoParser()
        specials, _, _ = parser._parse_payout_lines(df, sample_config)
        assert specials[0]["special_type"] == "SUBSCRIPTION"

    def test_special_refund_penalty(self, sample_config: AppConfig) -> None:
        """REFUND_PENALTY → special_type correct."""
        df = _make_payout_df([
            {"REFERENCE": "PEN001", "TYPE": "REFUND_PENALTY", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -10.00},
        ])
        parser = ManoManoParser()
        specials, _, _ = parser._parse_payout_lines(df, sample_config)
        assert specials[0]["special_type"] == "REFUND_PENALTY"

    def test_unknown_payout_type(self, sample_config: AppConfig) -> None:
        """Type inconnu Versements → Anomaly(type='unknown_payout_type'), ligne ignorée."""
        df = _make_payout_df([
            {"REFERENCE": "X001", "TYPE": "MARKETING_FEE", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -15.00},
        ])
        parser = ManoManoParser()
        specials, lookup, anomalies = parser._parse_payout_lines(df, sample_config)
        assert len(specials) == 0
        assert len(lookup) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "unknown_payout_type"

    def test_missing_column_payout(self, sample_config: AppConfig) -> None:
        """Colonne manquante Versements → ParseError."""
        df = _make_payout_df()
        df = df.drop(columns=["AMOUNT"])
        parser = ManoManoParser()
        with pytest.raises(ParseError, match="AMOUNT"):
            parser._parse_payout_lines(df, sample_config)

    def test_invalid_payout_date(self, sample_config: AppConfig) -> None:
        """PAYOUT_DATE invalide → Anomaly(type='invalid_date'), ligne ignorée."""
        df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "not-a-date", "AMOUNT": 102.00},
        ])
        parser = ManoManoParser()
        specials, lookup, anomalies = parser._parse_payout_lines(df, sample_config)
        assert len(lookup) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "invalid_date"

    def test_payout_summary_simple(self, sample_config: AppConfig) -> None:
        """3 lignes même PAYOUT_REFERENCE → 1 PayoutSummary, total_amount = somme signée."""
        df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 102.00},
            {"REFERENCE": "M002", "TYPE": "REFUND", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -50.00},
            {"REFERENCE": "ADJ001", "TYPE": "ADJUSTMENT", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -5.00},
        ])
        parser = ManoManoParser()
        summaries, anomalies = parser._aggregate_payout_summaries(df)
        assert len(summaries) == 1
        assert len(anomalies) == 0
        s = summaries[0]
        assert s.payout_reference == "PAY001"
        assert s.total_amount == 47.00
        assert s.payout_date == datetime.date(2026, 1, 31)
        assert s.channel == "manomano"
        assert s.psp_type is None
        assert s.charges == 0.0
        assert s.refunds == 0.0
        assert s.fees == 0.0
        # transaction_references excludes special types
        assert sorted(s.transaction_references) == ["M001", "M002"]

    def test_payout_summary_multiple_payouts(self, sample_config: AppConfig) -> None:
        """2 PAYOUT_REFERENCE distincts → 2 PayoutSummary séparés."""
        df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 100.00},
            {"REFERENCE": "M002", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY002", "PAYOUT_DATE": "2026-02-15", "AMOUNT": 200.00},
        ])
        parser = ManoManoParser()
        summaries, anomalies = parser._aggregate_payout_summaries(df)
        assert len(summaries) == 2
        assert len(anomalies) == 0
        refs = {s.payout_reference: s for s in summaries}
        assert refs["PAY001"].total_amount == 100.00
        assert refs["PAY002"].total_amount == 200.00

    def test_payout_summary_invalid_date(self, sample_config: AppConfig) -> None:
        """PAYOUT_DATE invalide dans aggregate → Anomaly, payout ignoré."""
        df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "bad-date", "AMOUNT": 100.00},
        ])
        parser = ManoManoParser()
        summaries, anomalies = parser._aggregate_payout_summaries(df)
        assert len(summaries) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "invalid_date"


# =============================================================================
# Tâche 7 : Tests matching + ParseResult
# =============================================================================


class TestMatching:
    """Tests pour l'enrichissement payout + fallback date."""

    def test_matching_complete(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """CA ref 'M001' + Versement ref 'M001' → payout_date et payout_reference peuplés."""
        # Arrange
        ca_df = _make_ca_df()
        payout_df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 102.00},
        ])
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse({"ca": ca_path, "payouts": payout_path}, sample_config)

        # Assert
        assert len(result.transactions) == 1
        tx = result.transactions[0]
        assert tx.payout_date == datetime.date(2026, 1, 31)
        assert tx.payout_reference == "PAY001"

    def test_matching_partial(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """CA ref 'M001' sans correspondance Versement → payout_date=None."""
        # Arrange
        ca_df = _make_ca_df()
        payout_df = _make_payout_df([
            {"REFERENCE": "M999", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 50.00},
        ])
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse({"ca": ca_path, "payouts": payout_path}, sample_config)

        # Assert
        assert len(result.transactions) == 1
        tx = result.transactions[0]
        assert tx.payout_date is None
        assert tx.payout_reference is None

    def test_matching_inverse_debug_log(
        self, sample_config: AppConfig, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Versement ORDER ref 'M002' sans CA correspondance → log DEBUG, pas d'anomalie."""
        # Arrange
        ca_df = _make_ca_df()
        payout_df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 102.00},
            {"REFERENCE": "M002", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 50.00},
        ])
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        parser = ManoManoParser()

        # Act
        with caplog.at_level(logging.DEBUG, logger="compta_ecom.parsers.manomano"):
            result = parser.parse({"ca": ca_path, "payouts": payout_path}, sample_config)

        # Assert
        assert not any(a.type == "unknown_payout_type" for a in result.anomalies)
        assert "M002" in caplog.text

    def test_fallback_date_from_payout(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """CA createdAt vide + matching Versement → date = PAYOUT_DATE."""
        # Arrange
        ca_df = _make_ca_df(createdAt="")
        payout_df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 102.00},
        ])
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse({"ca": ca_path, "payouts": payout_path}, sample_config)

        # Assert
        assert len(result.transactions) == 1
        assert result.transactions[0].date == datetime.date(2026, 1, 31)

    def test_missing_date_no_fallback(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Date absente dans CA et pas de correspondance Versement → Anomaly(type='missing_date')."""
        # Arrange
        ca_df = _make_ca_df(createdAt="")
        payout_df = _make_payout_df([
            {"REFERENCE": "M999", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 50.00},
        ])
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse({"ca": ca_path, "payouts": payout_path}, sample_config)

        # Assert
        assert len(result.transactions) == 0
        assert any(a.type == "missing_date" for a in result.anomalies)


class TestParseResult:
    """Tests pour parse() complet."""

    def test_full_parse_result(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """ParseResult complet : transactions CA + spéciales, payouts agrégés, channel='manomano'."""
        # Arrange
        ca_df = _make_ca_df()
        payout_df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 102.00},
            {"REFERENCE": "ADJ001", "TYPE": "ADJUSTMENT", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": -5.00},
        ])
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse({"ca": ca_path, "payouts": payout_path}, sample_config)

        # Assert
        assert result.channel == "manomano"
        assert len(result.transactions) == 2  # 1 CA + 1 special
        assert len(result.payouts) == 1

        # CA transaction
        ca_tx = [t for t in result.transactions if t.special_type is None]
        assert len(ca_tx) == 1
        assert ca_tx[0].reference == "M001"
        assert ca_tx[0].type == "sale"
        assert ca_tx[0].amount_ht == 83.33
        assert ca_tx[0].payment_method is None
        assert ca_tx[0].channel == "manomano"

        # Special transaction
        special_tx = [t for t in result.transactions if t.special_type is not None]
        assert len(special_tx) == 1
        assert special_tx[0].special_type == "ADJUSTMENT"
        assert special_tx[0].type == "sale"
        assert special_tx[0].amount_ht == 0.00
        assert special_tx[0].amount_tva == 0.00
        assert special_tx[0].amount_ttc == 0.00
        assert special_tx[0].shipping_ht == 0.00
        assert special_tx[0].shipping_tva == 0.00
        assert special_tx[0].commission_ttc == 0.00
        assert special_tx[0].commission_ht is None
        assert special_tx[0].net_amount == -5.00
        assert special_tx[0].tva_rate == 0.0

        # Payout summary
        payout = result.payouts[0]
        assert payout.payout_reference == "PAY001"
        assert payout.total_amount == 97.00
        assert payout.psp_type is None
        assert payout.transaction_references == ["M001"]

    def test_parse_with_csv_files(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """parse() lit correctement les fichiers CSV temporaires."""
        # Arrange
        ca_df = pd.DataFrame({
            "reference": ["M001", "M002"],
            "type": ["ORDER", "REFUND"],
            "createdAt": ["2026-01-15", "2026-01-16"],
            "amountVatIncl": [120.00, -60.00],
            "commissionVatIncl": [-18.00, 9.00],
            "commissionVatExcl": [-15.00, 7.50],
            "vatOnCommission": [-3.00, 1.50],
            "netAmount": [102.00, -51.00],
            "productPriceVatExcl": [83.33, -41.67],
            "vatOnProduct": [16.67, -8.33],
            "shippingPriceVatExcl": [8.33, -4.17],
            "vatOnShipping": [1.67, -0.83],
        })
        payout_df = pd.DataFrame({
            "REFERENCE": ["M001", "M002"],
            "TYPE": ["ORDER", "REFUND"],
            "PAYOUT_REFERENCE": ["PAY001", "PAY001"],
            "PAYOUT_DATE": ["2026-01-31", "2026-01-31"],
            "AMOUNT": [102.00, -51.00],
        })
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse({"ca": ca_path, "payouts": payout_path}, sample_config)

        # Assert
        assert len(result.transactions) == 2
        refs = {t.reference: t for t in result.transactions}
        assert refs["M001"].type == "sale"
        assert refs["M001"].amount_ttc == 120.00
        assert refs["M002"].type == "refund"
        assert refs["M002"].amount_ttc == 60.00  # abs()
        assert refs["M002"].commission_ttc == 9.00  # signed
        assert refs["M002"].net_amount == -51.00  # signed


# =============================================================================
# Story 2.5 : Tests order_details lookup
# =============================================================================


def _make_od_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Crée un DataFrame order_details."""
    return pd.DataFrame(rows)


class TestOrderDetailsLookup:
    """Tests pour _parse_order_details()."""

    def test_nominal_multi_pays(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """3 commandes (FR, DE, IT) avec multi-lignes → lookup correct."""
        # Arrange
        df = pd.DataFrame({
            "Order Reference": ["M001", "M001", "M002", "M003", "M003", "M003"],
            "Billing Country ISO": ["DE", "DE", "FR", "IT", "IT", "IT"],
        })
        od_path = tmp_path / "od.csv"
        _write_csv(df, od_path)
        parser = ManoManoParser()

        # Act
        lookup, anomalies = parser._parse_order_details(od_path, sample_config)

        # Assert
        assert lookup == {"M001": "276", "M002": "250", "M003": "380"}
        assert len(anomalies) == 0

    def test_deduplication_multi_lignes(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """5 lignes pour 2 commandes → lookup 2 entrées."""
        # Arrange
        df = pd.DataFrame({
            "Order Reference": ["M001", "M001", "M001", "M002", "M002"],
            "Billing Country ISO": ["FR", "FR", "FR", "DE", "DE"],
        })
        od_path = tmp_path / "od.csv"
        _write_csv(df, od_path)
        parser = ManoManoParser()

        # Act
        lookup, anomalies = parser._parse_order_details(od_path, sample_config)

        # Assert
        assert len(lookup) == 2
        assert lookup["M001"] == "250"
        assert lookup["M002"] == "276"
        assert len(anomalies) == 0

    def test_country_conflict(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Même Order Reference avec FR puis DE → Anomaly(type='country_conflict') + premier code retenu."""
        # Arrange
        df = pd.DataFrame({
            "Order Reference": ["M001", "M001"],
            "Billing Country ISO": ["FR", "DE"],
        })
        od_path = tmp_path / "od.csv"
        _write_csv(df, od_path)
        parser = ManoManoParser()

        # Act
        lookup, anomalies = parser._parse_order_details(od_path, sample_config)

        # Assert
        assert lookup["M001"] == "250"  # First occurrence = FR → 250
        conflict_anomalies = [a for a in anomalies if a.type == "country_conflict"]
        assert len(conflict_anomalies) == 1
        assert conflict_anomalies[0].reference == "M001"

    def test_unknown_alpha2(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Alpha-2 inconnu → Anomaly(type='unknown_country_alpha2') + absence du lookup."""
        # Arrange
        df = pd.DataFrame({
            "Order Reference": ["M001"],
            "Billing Country ISO": ["XX"],
        })
        od_path = tmp_path / "od.csv"
        _write_csv(df, od_path)
        parser = ManoManoParser()

        # Act
        lookup, anomalies = parser._parse_order_details(od_path, sample_config)

        # Assert
        assert "M001" not in lookup
        assert len(anomalies) == 1
        assert anomalies[0].type == "unknown_country_alpha2"
        assert anomalies[0].actual_value == "XX"

    def test_missing_country_iso_empty(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Billing Country ISO vide → Anomaly(type='missing_country_iso') + absence du lookup."""
        # Arrange
        df = pd.DataFrame({
            "Order Reference": ["M001"],
            "Billing Country ISO": [""],
        })
        od_path = tmp_path / "od.csv"
        _write_csv(df, od_path)
        parser = ManoManoParser()

        # Act
        lookup, anomalies = parser._parse_order_details(od_path, sample_config)

        # Assert
        assert "M001" not in lookup
        assert len(anomalies) == 1
        assert anomalies[0].type == "missing_country_iso"

    def test_missing_column(self, sample_config: AppConfig, tmp_path: Path) -> None:
        """Colonne manquante → ParseError."""
        # Arrange
        df = pd.DataFrame({"Order Reference": ["M001"]})
        od_path = tmp_path / "od.csv"
        _write_csv(df, od_path)
        parser = ManoManoParser()

        # Act & Assert
        with pytest.raises(ParseError):
            parser._parse_order_details(od_path, sample_config)


class TestParseWithCountryLookup:
    """Tests pour parse() avec/sans order_details — résolution pays par transaction."""

    def test_parse_with_order_details_multi_pays(
        self, sample_config: AppConfig, tmp_path: Path
    ) -> None:
        """2 transactions CA (M001=DE, M002=FR) → country_code et tva_rate résolus par lookup."""
        # Arrange
        ca_df = pd.DataFrame({
            "reference": ["M001", "M002"],
            "type": ["ORDER", "ORDER"],
            "createdAt": ["2026-01-15", "2026-01-16"],
            "amountVatIncl": [119.00, 120.00],
            "commissionVatIncl": [-18.00, -18.00],
            "commissionVatExcl": [-15.00, -15.00],
            "vatOnCommission": [-3.00, -3.00],
            "netAmount": [101.00, 102.00],
            "productPriceVatExcl": [100.00, 100.00],
            "vatOnProduct": [19.00, 20.00],
            "shippingPriceVatExcl": [0.00, 0.00],
            "vatOnShipping": [0.00, 0.00],
        })
        payout_df = _make_payout_df([
            {"REFERENCE": "M001", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 101.00},
            {"REFERENCE": "M002", "TYPE": "ORDER", "PAYOUT_REFERENCE": "PAY001", "PAYOUT_DATE": "2026-01-31", "AMOUNT": 102.00},
        ])
        od_df = pd.DataFrame({
            "Order Reference": ["M001", "M002"],
            "Billing Country ISO": ["DE", "FR"],
        })
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        od_path = tmp_path / "od.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        _write_csv(od_df, od_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse(
            {"ca": ca_path, "payouts": payout_path, "order_details": od_path},
            sample_config,
        )

        # Assert
        refs = {t.reference: t for t in result.transactions}
        assert refs["M001"].country_code == "276"
        assert refs["M001"].tva_rate == 19.0
        assert refs["M002"].country_code == "250"
        assert refs["M002"].tva_rate == 20.0

    def test_parse_without_order_details_retrocompat(
        self, sample_config: AppConfig, tmp_path: Path
    ) -> None:
        """files sans clé order_details → tout = France 250 (comportement story 2.1)."""
        # Arrange
        ca_df = _make_ca_df()
        payout_df = _make_payout_df()
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse({"ca": ca_path, "payouts": payout_path}, sample_config)

        # Assert
        assert len(result.transactions) == 1
        tx = result.transactions[0]
        assert tx.country_code == "250"
        assert tx.tva_rate == 20.0
        # No order_reference_not_in_lookup anomaly (lookup is empty, not active)
        assert not any(a.type == "order_reference_not_in_lookup" for a in result.anomalies)

    def test_parse_ref_absent_from_lookup(
        self, sample_config: AppConfig, tmp_path: Path
    ) -> None:
        """Référence CA absente du lookup → country_code='250' + Anomaly info."""
        # Arrange
        ca_df = _make_ca_df()  # M001
        payout_df = _make_payout_df()
        od_df = pd.DataFrame({
            "Order Reference": ["M999"],
            "Billing Country ISO": ["DE"],
        })
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        od_path = tmp_path / "od.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        _write_csv(od_df, od_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse(
            {"ca": ca_path, "payouts": payout_path, "order_details": od_path},
            sample_config,
        )

        # Assert
        tx = result.transactions[0]
        assert tx.country_code == "250"
        assert tx.tva_rate == 20.0
        info_anomalies = [a for a in result.anomalies if a.type == "order_reference_not_in_lookup"]
        assert len(info_anomalies) == 1
        assert info_anomalies[0].severity == "info"

    def test_parse_full_integration_with_od(
        self, sample_config: AppConfig, tmp_path: Path
    ) -> None:
        """Intégration complète : CA + Versements + order_details via tmp_path CSV."""
        # Arrange
        ca_df = pd.DataFrame({
            "reference": ["M001", "M002", "M003"],
            "type": ["ORDER", "ORDER", "REFUND"],
            "createdAt": ["2026-01-15", "2026-01-16", "2026-01-17"],
            "amountVatIncl": [119.00, 122.00, -120.00],
            "commissionVatIncl": [-17.85, -18.30, 18.00],
            "commissionVatExcl": [-14.88, -15.25, 15.00],
            "vatOnCommission": [-2.97, -3.05, 3.00],
            "netAmount": [101.15, 103.70, -102.00],
            "productPriceVatExcl": [100.00, 100.00, -100.00],
            "vatOnProduct": [19.00, 22.00, -20.00],
            "shippingPriceVatExcl": [0.00, 0.00, 0.00],
            "vatOnShipping": [0.00, 0.00, 0.00],
        })
        payout_df = pd.DataFrame({
            "REFERENCE": ["M001", "M002", "M003"],
            "TYPE": ["ORDER", "ORDER", "REFUND"],
            "PAYOUT_REFERENCE": ["PAY001", "PAY001", "PAY001"],
            "PAYOUT_DATE": ["2026-01-31", "2026-01-31", "2026-01-31"],
            "AMOUNT": [101.15, 103.70, -102.00],
        })
        od_df = pd.DataFrame({
            "Order Reference": ["M001", "M002", "M003"],
            "Billing Country ISO": ["DE", "IT", "FR"],
        })
        ca_path = tmp_path / "ca.csv"
        payout_path = tmp_path / "payouts.csv"
        od_path = tmp_path / "od.csv"
        _write_csv(ca_df, ca_path)
        _write_csv(payout_df, payout_path)
        _write_csv(od_df, od_path)
        parser = ManoManoParser()

        # Act
        result = parser.parse(
            {"ca": ca_path, "payouts": payout_path, "order_details": od_path},
            sample_config,
        )

        # Assert
        refs = {t.reference: t for t in result.transactions}
        assert refs["M001"].country_code == "276"
        assert refs["M001"].tva_rate == 19.0
        assert refs["M002"].country_code == "380"
        assert refs["M002"].tva_rate == 22.0
        assert refs["M003"].country_code == "250"
        assert refs["M003"].tva_rate == 20.0
        assert len(result.anomalies) == 0
