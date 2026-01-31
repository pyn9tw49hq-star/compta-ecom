"""Orchestrateur du pipeline de traitement complet."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from compta_ecom.config.loader import AppConfig
from compta_ecom.controls.matching_checker import MatchingChecker
from compta_ecom.controls.vat_checker import VatChecker
from compta_ecom.engine import generate_entries
from compta_ecom.exporters.excel import export, print_summary
from compta_ecom.models import NoResultError, ParseError, ParseResult
from compta_ecom.parsers import ShopifyParser
from compta_ecom.parsers.base import BaseParser
from compta_ecom.parsers.manomano import ManoManoParser
from compta_ecom.parsers.mirakl import MiraklParser

logger = logging.getLogger(__name__)

PARSER_REGISTRY: dict[str, Callable[[], BaseParser]] = {
    "shopify": ShopifyParser,
    "manomano": ManoManoParser,
    "decathlon": lambda: MiraklParser("decathlon"),
    "leroy_merlin": lambda: MiraklParser("leroy_merlin"),
}


class PipelineOrchestrator:
    """Orchestre le pipeline CSV → Écritures → Excel."""

    def run(self, input_dir: Path, output_path: Path, config: AppConfig) -> None:
        """Exécute le pipeline complet."""
        all_parse_results: list[ParseResult] = []
        channel_errors: list[tuple[str, str]] = []

        for canal, channel_config in config.channels.items():
            parser_factory = PARSER_REGISTRY.get(canal)
            if parser_factory is None:
                logger.warning("Parser non implémenté pour le canal %s — ignoré", canal)
                continue

            files = self._detect_files(input_dir, channel_config.files)
            if not files:
                logger.info("Aucun fichier trouvé pour le canal %s — ignoré", canal)
                continue

            try:
                parser = parser_factory()
                result = parser.parse(files, config)
                all_parse_results.append(result)
                logger.info("Canal %s : %d transactions parsées", canal, len(result.transactions))
            except ParseError as e:
                logger.error("Échec du parsing %s : %s", canal, e)
                channel_errors.append((canal, str(e)))

        if not all_parse_results:
            raise NoResultError(
                "Aucun canal n'a produit de résultat. "
                "Vérifiez les fichiers CSV et la configuration."
            )

        all_transactions = [t for pr in all_parse_results for t in pr.transactions]
        all_payouts = [p for pr in all_parse_results for p in pr.payouts]
        all_anomalies = [a for pr in all_parse_results for a in pr.anomalies]

        entries, engine_anomalies = generate_entries(all_transactions, all_payouts, config)
        all_anomalies.extend(engine_anomalies)

        # Contrôles de cohérence
        vat_anomalies = VatChecker.check(all_transactions, config)
        logger.info("VatChecker: %d anomalies détectées", len(vat_anomalies))

        matching_anomalies = MatchingChecker.check(all_transactions, config)
        logger.info("MatchingChecker: %d anomalies détectées", len(matching_anomalies))

        all_anomalies.extend(vat_anomalies)
        all_anomalies.extend(matching_anomalies)

        export(entries, all_anomalies, output_path, config)
        print_summary(entries, all_anomalies, channel_errors)

    @staticmethod
    def _detect_files(
        input_dir: Path, file_patterns: dict[str, str]
    ) -> dict[str, Path]:
        """Détecte les fichiers CSV dans input_dir via les patterns glob."""
        found: dict[str, Path] = {}
        for file_key, pattern in file_patterns.items():
            matches = sorted(input_dir.glob(pattern))
            if matches:
                found[file_key] = matches[0]
        return found
