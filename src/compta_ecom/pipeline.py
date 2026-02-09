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
from compta_ecom.models import AccountingEntry, Anomaly, NormalizedTransaction, NoResultError, ParseError, ParseResult
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
    ) -> tuple[list[AccountingEntry], list[Anomaly], dict[str, object]]:
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
        summary = self._build_summary(entries, all_parse_results, config)

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

    def _build_summary(
        self,
        entries: list[AccountingEntry],
        all_parse_results: list[ParseResult],
        config: AppConfig,
    ) -> dict[str, object]:
        """Construit le résumé : transactions par canal, écritures par type, totaux, KPIs financiers."""
        # Transactions par canal (unique par reference + channel)
        seen_refs: set[tuple[str, str]] = set()
        transactions_par_canal: Counter[str] = Counter()
        unique_txs: list[NormalizedTransaction] = []
        for pr in all_parse_results:
            for t in pr.transactions:
                key = (t.reference, t.channel)
                if key not in seen_refs:
                    seen_refs.add(key)
                    transactions_par_canal[t.channel] += 1
                    unique_txs.append(t)

        # Écritures par type
        ecritures_par_type: Counter[str] = Counter(e.entry_type for e in entries)

        # Totaux
        total_debit = round(sum(e.debit for e in entries), 2)
        total_credit = round(sum(e.credit for e in entries), 2)

        # --- KPIs financiers (accumulateurs par canal) ---
        ca_ht: dict[str, float] = {}
        ca_ttc: dict[str, float] = {}
        refund_ht: dict[str, float] = {}
        refund_ttc: dict[str, float] = {}
        refund_nb: dict[str, int] = {}
        sales_nb: dict[str, int] = {}
        comm_ht: dict[str, float] = {}
        comm_ttc: dict[str, float] = {}
        tva_col: dict[str, float] = {}

        for t in unique_txs:
            if t.special_type is not None:
                continue
            c = t.channel
            # Initialise les accumulateurs pour ce canal
            if c not in ca_ht:
                ca_ht[c] = ca_ttc[c] = 0.0
                refund_ht[c] = refund_ttc[c] = 0.0
                refund_nb[c] = sales_nb[c] = 0
                comm_ht[c] = comm_ttc[c] = 0.0
                tva_col[c] = 0.0

            if t.type == "sale":
                sales_nb[c] += 1
                ca_ht[c] += t.amount_ht + t.shipping_ht
                ca_ttc[c] += t.amount_ttc
                tva_col[c] += t.amount_tva + t.shipping_tva
            elif t.type == "refund":
                refund_nb[c] += 1
                refund_ht[c] += abs(t.amount_ht + t.shipping_ht)
                refund_ttc[c] += abs(t.amount_ttc)

            # Commissions : toutes transactions normales (ventes + remboursements)
            comm_ttc[c] += abs(t.commission_ttc)
            if t.commission_ht is not None:
                comm_ht[c] += abs(t.commission_ht)

        # Arrondi financier systématique (round(x, 2))
        channels = sorted(ca_ht.keys())
        for c in channels:
            ca_ht[c] = round(ca_ht[c], 2)
            ca_ttc[c] = round(ca_ttc[c], 2)
            refund_ht[c] = round(refund_ht[c], 2)
            refund_ttc[c] = round(refund_ttc[c], 2)
            comm_ht[c] = round(comm_ht[c], 2)
            comm_ttc[c] = round(comm_ttc[c], 2)
            tva_col[c] = round(tva_col[c], 2)

        # Construction des dicts de sortie
        ca_par_canal = {c: {"ht": ca_ht[c], "ttc": ca_ttc[c]} for c in channels}
        remboursements_par_canal = {
            c: {"count": refund_nb[c], "ht": refund_ht[c], "ttc": refund_ttc[c]}
            for c in channels
        }
        taux_remboursement_par_canal = {
            c: round(refund_nb[c] / sales_nb[c] * 100, 1) if sales_nb[c] > 0 else 0.0
            for c in channels
        }
        commissions_par_canal = {c: {"ht": comm_ht[c], "ttc": comm_ttc[c]} for c in channels}
        net_vendeur_par_canal = {
            c: round(ca_ttc[c] - comm_ttc[c] - refund_ttc[c], 2)
            for c in channels
        }
        tva_collectee_par_canal = {c: tva_col[c] for c in channels}

        # Répartition géographique (ventes uniquement)
        def resolve_country(code: str) -> str:
            """Résout un country_code numérique en nom de pays via vat_table."""
            entry = config.vat_table.get(code)
            if entry:
                return str(entry["name"])
            return f"Pays inconnu ({code})"

        geo_g_count: dict[str, int] = {}
        geo_g_ca: dict[str, float] = {}
        geo_c_count: dict[str, dict[str, int]] = {}
        geo_c_ca: dict[str, dict[str, float]] = {}

        for t in unique_txs:
            if t.special_type is not None or t.type != "sale":
                continue
            country = resolve_country(t.country_code)
            canal = t.channel

            # Global
            geo_g_count[country] = geo_g_count.get(country, 0) + 1
            geo_g_ca[country] = geo_g_ca.get(country, 0.0) + t.amount_ttc

            # Par canal
            if canal not in geo_c_count:
                geo_c_count[canal] = {}
                geo_c_ca[canal] = {}
            geo_c_count[canal][country] = geo_c_count[canal].get(country, 0) + 1
            geo_c_ca[canal][country] = geo_c_ca[canal].get(country, 0.0) + t.amount_ttc

        repartition_geo_globale = {
            country: {"count": geo_g_count[country], "ca_ttc": round(geo_g_ca[country], 2)}
            for country in sorted(geo_g_ca, key=lambda p: geo_g_ca[p], reverse=True)
        }
        repartition_geo_par_canal = {
            canal: {
                country: {"count": geo_c_count[canal][country], "ca_ttc": round(geo_c_ca[canal][country], 2)}
                for country in sorted(geo_c_ca[canal], key=lambda p: geo_c_ca[canal][p], reverse=True)
            }
            for canal in sorted(geo_c_count)
        }

        return {
            "transactions_par_canal": dict(transactions_par_canal),
            "ecritures_par_type": dict(ecritures_par_type),
            "totaux": {"debit": total_debit, "credit": total_credit},
            "ca_par_canal": ca_par_canal,
            "remboursements_par_canal": remboursements_par_canal,
            "taux_remboursement_par_canal": taux_remboursement_par_canal,
            "commissions_par_canal": commissions_par_canal,
            "net_vendeur_par_canal": net_vendeur_par_canal,
            "tva_collectee_par_canal": tva_collectee_par_canal,
            "repartition_geo_globale": repartition_geo_globale,
            "repartition_geo_par_canal": repartition_geo_par_canal,
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
                # Only dispatch if all required (non-multi_files) keys are present
                required_keys = {k for k in channel_config.files if k not in multi_files}
                if required_keys.issubset(canal_files.keys()):
                    result[canal] = canal_files

        return result
