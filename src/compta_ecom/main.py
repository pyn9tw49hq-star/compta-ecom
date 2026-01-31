"""Point d'entrée CLI de compta-ecom."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from compta_ecom.config.loader import load_config
from compta_ecom.models import ConfigError, NoResultError
from compta_ecom.pipeline import PipelineOrchestrator

logger = logging.getLogger("compta_ecom.main")

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse les arguments CLI."""
    parser = argparse.ArgumentParser(
        prog="compta-ecom",
        description="Automatisation comptable e-commerce multi-canal",
    )
    parser.add_argument("input_dir", help="Répertoire contenant les fichiers CSV d'entrée")
    parser.add_argument("output_file", help="Fichier Excel de sortie")
    parser.add_argument(
        "--config-dir",
        default="./config/",
        help="Répertoire de configuration YAML (défaut : ./config/)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=VALID_LOG_LEVELS,
        help="Niveau de log (défaut : INFO)",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> None:
    """Point d'entrée principal."""
    parsed = parse_args(args)

    logging.basicConfig(
        level=getattr(logging, parsed.log_level),
        format=LOG_FORMAT,
    )

    config_dir = Path(parsed.config_dir)
    try:
        config = load_config(config_dir)
    except ConfigError as e:
        logger.error("Erreur de configuration : %s", e)
        sys.exit(2)

    try:
        orchestrator = PipelineOrchestrator()
        orchestrator.run(
            input_dir=Path(parsed.input_dir),
            output_path=Path(parsed.output_file),
            config=config,
        )
    except NoResultError:
        print(
            "ERREUR : Aucun canal n'a produit de résultat. "
            "Vérifiez les fichiers CSV et la configuration."
        )
        sys.exit(3)
    except Exception:
        logger.exception("Erreur inattendue")
        sys.exit(1)


if __name__ == "__main__":
    main()
