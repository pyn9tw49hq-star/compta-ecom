"""Classe abstraite de base pour les parsers CSV."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path

import pandas as pd

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import ParseError, ParseResult

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Classe abstraite définissant l'interface commune des parsers."""

    @abstractmethod
    def parse(self, files: dict[str, Path | BytesIO | list[Path | BytesIO]], config: AppConfig) -> ParseResult:
        """Parse les fichiers CSV et retourne un ParseResult normalisé."""

    @staticmethod
    def detect_separator(
        source: Path | BytesIO,
        encoding: str = "utf-8",
        candidates: tuple[str, ...] = (",", ";"),
    ) -> str:
        """Détecte le séparateur CSV en comptant les occurrences dans le header."""
        if isinstance(source, BytesIO):
            pos = source.tell()
            header = source.readline().decode(encoding)
            source.seek(pos)
        elif isinstance(source, Path):
            with open(source, encoding=encoding) as f:
                header = f.readline()
        else:
            return candidates[0] if candidates else ","

        if not header.strip():
            return candidates[0] if candidates else ","

        best = candidates[0]
        best_count = 0
        for sep in candidates:
            count = header.count(sep)
            if count > best_count:
                best_count = count
                best = sep
        return best

    def read_csv(
        self,
        source: Path | BytesIO,
        *,
        configured_sep: str,
        encoding: str = "utf-8",
        **kwargs: object,
    ) -> pd.DataFrame:
        """Lit un CSV avec auto-détection du séparateur."""
        detected = self.detect_separator(source, encoding)
        if detected != configured_sep:
            logger.warning(
                "Séparateur détecté '%s' différent du séparateur configuré '%s'"
                " — utilisation du séparateur détecté",
                detected,
                configured_sep,
            )
        if isinstance(source, BytesIO):
            source.seek(0)
        return pd.read_csv(source, sep=detected, encoding=encoding, **kwargs)

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
