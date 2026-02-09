"""Orchestrateur du pipeline de traitement complet."""

from __future__ import annotations

import fnmatch
import logging
import unicodedata
from collections import Counter
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

from compta_ecom.config.loader import AppConfig, ChannelConfig
from compta_ecom.controls.lettrage_checker import LettrageChecker
from compta_ecom.controls.matching_checker import MatchingChecker
from compta_ecom.controls.vat_checker import VatChecker
from compta_ecom.engine import generate_entries
from compta_ecom.exporters.excel import export, print_summary
from compta_ecom.models import AccountingEntry, Anomaly, NoResultError, ParseError, ParseResult
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

            files = self._detect_files(input_dir, channel_config.files, channel_config.multi_files)
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

        entries, all_anomalies = self._process_parse_results(all_parse_results, config)

        export(entries, all_anomalies, output_path, config)
        print_summary(entries, all_anomalies, channel_errors)

    def run_from_buffers(
        self,
        files: dict[str, bytes],
        config: AppConfig,
    ) -> tuple[list[AccountingEntry], list[Anomaly], dict[str, dict[str, int] | dict[str, float]]]:
        """Exécute le pipeline à partir de fichiers en mémoire.

        Args:
            files: Dictionnaire {nom_fichier: contenu_bytes}.
            config: Configuration de l'application.

        Returns:
            Tuple (écritures, anomalies, résumé).
        """
        canal_dispatch = self._detect_files_from_buffers(files, config.channels)

        all_parse_results: list[ParseResult] = []
        channel_errors: list[tuple[str, str]] = []

        for canal, canal_files in canal_dispatch.items():
            parser_factory = PARSER_REGISTRY.get(canal)
            if parser_factory is None:
                logger.warning("Parser non implémenté pour le canal %s — ignoré", canal)
                continue

            try:
                parser = parser_factory()
                result = parser.parse(canal_files, config)
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

        entries, all_anomalies = self._process_parse_results(all_parse_results, config)
        summary = self._build_summary(entries, all_parse_results)

        return entries, all_anomalies, summary

    def _process_parse_results(
        self,
        all_parse_results: list[ParseResult],
        config: AppConfig,
    ) -> tuple[list[AccountingEntry], list[Anomaly]]:
        """Agrège les résultats de parsing, génère les écritures et exécute les contrôles."""
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

        lettrage_anomalies = LettrageChecker.check(entries)
        logger.info("LettrageChecker: %d anomalies détectées", len(lettrage_anomalies))

        all_anomalies.extend(vat_anomalies)
        all_anomalies.extend(matching_anomalies)
        all_anomalies.extend(lettrage_anomalies)

        return entries, all_anomalies

    @staticmethod
    def _build_summary(
        entries: list[AccountingEntry],
        all_parse_results: list[ParseResult],
    ) -> dict[str, dict[str, int] | dict[str, float]]:
        """Construit le résumé : transactions par canal, écritures par type, totaux."""
        # Transactions par canal (unique par reference + channel)
        seen_refs: set[tuple[str, str]] = set()
        transactions_par_canal: Counter[str] = Counter()
        for pr in all_parse_results:
            for t in pr.transactions:
                key = (t.reference, t.channel)
                if key not in seen_refs:
                    seen_refs.add(key)
                    transactions_par_canal[t.channel] += 1

        # Écritures par type
        ecritures_par_type: Counter[str] = Counter(e.entry_type for e in entries)

        # Totaux
        total_debit = round(sum(e.debit for e in entries), 2)
        total_credit = round(sum(e.credit for e in entries), 2)

        return {
            "transactions_par_canal": dict(transactions_par_canal),
            "ecritures_par_type": dict(ecritures_par_type),
            "totaux": {"debit": total_debit, "credit": total_credit},
        }

    @staticmethod
    def _detect_files(
        input_dir: Path,
        file_patterns: dict[str, str],
        multi_files: list[str] | None = None,
    ) -> dict[str, Path | list[Path]]:
        """Détecte les fichiers CSV dans input_dir via les patterns glob."""
        multi_files = multi_files or []
        found: dict[str, Path | list[Path]] = {}
        for file_key, pattern in file_patterns.items():
            matches = sorted(input_dir.glob(pattern))
            if not matches:
                # macOS returns NFD filenames; retry with NFD-normalized pattern
                nfd_pattern = unicodedata.normalize("NFD", pattern)
                if nfd_pattern != pattern:
                    matches = sorted(input_dir.glob(nfd_pattern))
            if file_key in multi_files:
                if matches:
                    found[file_key] = matches
            else:
                if matches:
                    found[file_key] = matches[0]
        return found

    @staticmethod
    def _detect_files_from_buffers(
        files: dict[str, bytes],
        channels: dict[str, ChannelConfig],
    ) -> dict[str, dict[str, BytesIO | list[BytesIO]]]:
        """Dispatch des fichiers en mémoire vers les canaux via fnmatch sur les patterns."""
        result: dict[str, dict[str, BytesIO | list[BytesIO]]] = {}

        for canal, channel_config in channels.items():
            multi_files = channel_config.multi_files or []
            canal_files: dict[str, BytesIO | list[BytesIO]] = {}

            for file_key, pattern in channel_config.files.items():
                # For patterns with '/', match only the basename
                match_pattern = pattern.split("/")[-1] if "/" in pattern else pattern

                matched: list[tuple[str, bytes]] = []
                for filename, content in files.items():
                    basename = filename.split("/")[-1] if "/" in filename else filename
                    if fnmatch.fnmatch(basename, match_pattern):
                        matched.append((filename, content))

                if not matched:
                    # Try NFD-normalized pattern (macOS)
                    nfd_pattern = unicodedata.normalize("NFD", match_pattern)
                    if nfd_pattern != match_pattern:
                        for filename, content in files.items():
                            basename = filename.split("/")[-1] if "/" in filename else filename
                            if fnmatch.fnmatch(basename, nfd_pattern):
                                matched.append((filename, content))

                if file_key in multi_files:
                    if matched:
                        canal_files[file_key] = [BytesIO(content) for _, content in sorted(matched)]
                else:
                    if matched:
                        # Sort by filename for deterministic behavior, take first
                        matched.sort(key=lambda x: x[0])
                        canal_files[file_key] = BytesIO(matched[0][1])

            if canal_files:
                result[canal] = canal_files

        return result
