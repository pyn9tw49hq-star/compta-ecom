"""Tests unitaires pour BaseParser."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import ParseError, ParseResult
from compta_ecom.parsers.base import BaseParser


class _ConcreteParser(BaseParser):
    """Stub pour tester BaseParser."""

    def parse(self, files: dict[str, Path], config: AppConfig) -> ParseResult:
        raise NotImplementedError


class TestValidateColumns:
    def test_all_columns_present(self) -> None:
        parser = _ConcreteParser()
        df = pd.DataFrame({"A": [1], "B": [2], "C": [3]})
        parser.validate_columns(df, ["A", "B"])

    def test_single_column_missing(self) -> None:
        parser = _ConcreteParser()
        df = pd.DataFrame({"A": [1]})
        with pytest.raises(ParseError, match="B"):
            parser.validate_columns(df, ["A", "B"])

    def test_multiple_columns_missing(self) -> None:
        parser = _ConcreteParser()
        df = pd.DataFrame({"A": [1]})
        with pytest.raises(ParseError, match="B") as exc_info:
            parser.validate_columns(df, ["A", "B", "C"])
        assert "C" in str(exc_info.value)


class TestDetectSeparator:
    def test_header_comma(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("A,B,C\n1,2,3\n", encoding="utf-8")
        assert BaseParser.detect_separator(f) == ","

    def test_header_semicolon(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("A;B;C\n1;2;3\n", encoding="utf-8")
        assert BaseParser.detect_separator(f) == ";"

    def test_bytesio_comma(self) -> None:
        buf = BytesIO(b"A,B,C\n1,2,3\n")
        pos_before = buf.tell()
        assert BaseParser.detect_separator(buf) == ","
        assert buf.tell() == pos_before

    def test_bytesio_semicolon(self) -> None:
        buf = BytesIO(b"A;B;C\n1;2;3\n")
        buf.seek(0)
        pos_before = buf.tell()
        assert BaseParser.detect_separator(buf) == ";"
        assert buf.tell() == pos_before

    def test_empty_file_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.csv"
        f.write_text("", encoding="utf-8")
        assert BaseParser.detect_separator(f) == ","

    def test_no_separator_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("ABCDEF\n123456\n", encoding="utf-8")
        assert BaseParser.detect_separator(f) == ","

    def test_mixed_most_frequent_wins(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("A;B;C;D,E\n1;2;3;4,5\n", encoding="utf-8")
        assert BaseParser.detect_separator(f) == ";"


class TestReadCsv:
    def test_normal_comma(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("A,B\n1,2\n", encoding="utf-8")
        parser = _ConcreteParser()
        df = parser.read_csv(f, configured_sep=",")
        assert list(df.columns) == ["A", "B"]
        assert df["A"].iloc[0] == 1

    def test_autodetect_semicolon_warns(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        f = tmp_path / "test.csv"
        f.write_text("A;B\n1;2\n", encoding="utf-8")
        parser = _ConcreteParser()
        with caplog.at_level(logging.WARNING, logger="compta_ecom.parsers.base"):
            df = parser.read_csv(f, configured_sep=",")
        assert list(df.columns) == ["A", "B"]
        assert "détecté" in caplog.text

    def test_bytesio_source(self) -> None:
        buf = BytesIO(b"X,Y\n10,20\n")
        parser = _ConcreteParser()
        df = parser.read_csv(buf, configured_sep=",")
        assert list(df.columns) == ["X", "Y"]
        assert df["Y"].iloc[0] == 20

    def test_forward_kwargs_usecols(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text("A,B,C\n1,2,3\n", encoding="utf-8")
        parser = _ConcreteParser()
        df = parser.read_csv(f, configured_sep=",", usecols=["A", "C"])
        assert list(df.columns) == ["A", "C"]
