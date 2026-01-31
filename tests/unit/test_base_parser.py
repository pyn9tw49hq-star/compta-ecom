"""Tests unitaires pour BaseParser."""

from __future__ import annotations

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
