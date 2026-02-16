"""Classe abstraite de base pour les parsers CSV."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path

import pandas as pd

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import ParseError, ParseResult


class BaseParser(ABC):
    """Classe abstraite définissant l'interface commune des parsers."""

    @abstractmethod
    def parse(self, files: dict[str, Path | BytesIO | list[Path | BytesIO]], config: AppConfig) -> ParseResult:
        """Parse les fichiers CSV et retourne un ParseResult normalisé."""

    @staticmethod
    def apply_column_aliases(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
        """Renomme les colonnes du DataFrame selon les alias définis.

        Pour chaque colonne attendue, si elle est absente mais qu'un alias
        est présent, la colonne est renommée.
        """
        rename_map: dict[str, str] = {}
        for expected, alternatives in aliases.items():
            if expected not in df.columns:
                for alt in alternatives:
                    if alt in df.columns:
                        rename_map[alt] = expected
                        break
        if rename_map:
            df = df.rename(columns=rename_map)
        return df

    @staticmethod
    def strip_whitespace(df: pd.DataFrame) -> pd.DataFrame:
        """Strip whitespace from column names and string cell values.

        Handles CSV files with spaces around separators (e.g. ` ; `).
        """
        df.columns = df.columns.str.strip()
        for col in df.columns:
            if pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].str.strip()
        return df

    def validate_columns(self, df: pd.DataFrame, required: list[str]) -> None:
        """Vérifie que toutes les colonnes requises sont présentes dans le DataFrame.

        Args:
            df: Le DataFrame à valider.
            required: Liste des noms de colonnes requises.

        Raises:
            ParseError: Si des colonnes requises sont absentes du DataFrame.
                Le message liste les colonnes manquantes.

        Returns:
            None — ne retourne rien si toutes les colonnes sont présentes.
        """
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ParseError(f"Colonnes manquantes : {', '.join(missing)}")
