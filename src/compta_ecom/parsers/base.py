"""Classe abstraite de base pour les parsers CSV."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import ParseError, ParseResult


class BaseParser(ABC):
    """Classe abstraite définissant l'interface commune des parsers."""

    @abstractmethod
    def parse(self, files: dict[str, Path], config: AppConfig) -> ParseResult:
        """Parse les fichiers CSV et retourne un ParseResult normalisé."""

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
