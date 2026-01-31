"""Chargement et validation de la configuration YAML."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from compta_ecom.models import ConfigError

logger = logging.getLogger(__name__)

SUPPORTED_ENCODINGS = {"utf-8", "utf-8-sig", "latin-1", "iso-8859-1"}
SUPPORTED_SEPARATORS = {",", ";"}


@dataclass
class ChannelConfig:
    """Configuration d'un canal (non frozen — dataclass technique)."""

    files: dict[str, str]
    encoding: str
    separator: str
    default_country_code: str | None = None
    commission_vat_rate: float | None = None


@dataclass
class PspConfig:
    """Configuration d'un PSP."""

    compte: str
    commission: str | None = None


@dataclass
class AppConfig:
    """Configuration complète de l'application (non frozen — dataclass technique)."""

    # Plan comptable
    clients: dict[str, str]
    fournisseurs: dict[str, str]
    psp: dict[str, PspConfig]
    transit: str
    banque: str
    comptes_speciaux: dict[str, str]
    comptes_vente_prefix: str
    canal_codes: dict[str, str]
    comptes_tva_prefix: str

    # TVA
    vat_table: dict[str, dict[str, object]]
    alpha2_to_numeric: dict[str, str] = field(default_factory=dict)

    # Canaux
    channels: dict[str, ChannelConfig] = field(default_factory=dict)

    # Matching
    matching_tolerance: float = 0.01


def _load_yaml(filepath: Path) -> dict[str, object]:
    """Charge un fichier YAML et retourne son contenu."""
    if not filepath.exists():
        raise ConfigError(f"Fichier de configuration manquant : {filepath}")
    try:
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML malformé dans {filepath} : {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Le fichier {filepath} doit contenir un mapping YAML (reçu : {type(data).__name__})")
    return data


def _require_key(data: dict[str, object], key: str, context: str) -> object:
    """Vérifie qu'une clé existe dans un dictionnaire."""
    if key not in data:
        raise ConfigError(f"Clé obligatoire '{key}' manquante dans {context}")
    return data[key]


def _validate_chart(data: dict[str, object]) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, PspConfig],
    str,
    str,
    dict[str, str],
    str,
    dict[str, str],
    str,
]:
    """Valide et extrait le plan comptable."""
    context = "chart_of_accounts.yaml"

    clients = _require_key(data, "clients", context)
    if not isinstance(clients, dict):
        raise ConfigError(f"'clients' doit être un mapping dans {context}")

    fournisseurs = _require_key(data, "fournisseurs", context)
    if not isinstance(fournisseurs, dict):
        raise ConfigError(f"'fournisseurs' doit être un mapping dans {context}")

    psp_raw = _require_key(data, "psp", context)
    if not isinstance(psp_raw, dict):
        raise ConfigError(f"'psp' doit être un mapping dans {context}")

    psp: dict[str, PspConfig] = {}
    for psp_name, psp_data in psp_raw.items():
        if not isinstance(psp_data, dict):
            raise ConfigError(f"PSP '{psp_name}' doit être un mapping dans {context}")
        if "compte" not in psp_data:
            raise ConfigError(f"Clé 'compte' manquante pour PSP '{psp_name}' dans {context}")
        psp[str(psp_name)] = PspConfig(
            compte=str(psp_data["compte"]),
            commission=str(psp_data["commission"]) if "commission" in psp_data else None,
        )

    transit = str(_require_key(data, "transit", context))
    banque = str(_require_key(data, "banque", context))

    comptes_speciaux_raw = data.get("comptes_speciaux", {})
    if not isinstance(comptes_speciaux_raw, dict):
        raise ConfigError(f"'comptes_speciaux' doit être un mapping dans {context}")
    comptes_speciaux: dict[str, str] = {str(k): str(v) for k, v in comptes_speciaux_raw.items()}

    comptes_vente = _require_key(data, "comptes_vente", context)
    if not isinstance(comptes_vente, dict):
        raise ConfigError(f"'comptes_vente' doit être un mapping dans {context}")
    prefix = str(_require_key(comptes_vente, "prefix", f"{context}/comptes_vente"))
    canal_codes_raw = _require_key(comptes_vente, "canal_codes", f"{context}/comptes_vente")
    if not isinstance(canal_codes_raw, dict):
        raise ConfigError(f"'canal_codes' doit être un mapping dans {context}/comptes_vente")
    canal_codes: dict[str, str] = {str(k): str(v) for k, v in canal_codes_raw.items()}

    comptes_tva = _require_key(data, "comptes_tva", context)
    if not isinstance(comptes_tva, dict):
        raise ConfigError(f"'comptes_tva' doit être un mapping dans {context}")
    tva_prefix = str(_require_key(comptes_tva, "prefix", f"{context}/comptes_tva"))

    return (
        {str(k): str(v) for k, v in clients.items()},
        {str(k): str(v) for k, v in fournisseurs.items()},
        psp,
        transit,
        banque,
        comptes_speciaux,
        prefix,
        canal_codes,
        tva_prefix,
    )


def _validate_vat(data: dict[str, object]) -> dict[str, dict[str, object]]:
    """Valide et extrait la table TVA."""
    context = "vat_table.yaml"

    countries = _require_key(data, "countries", context)
    if not isinstance(countries, dict):
        raise ConfigError(f"'countries' doit être un mapping dans {context}")

    if len(countries) == 0:
        raise ConfigError(f"'countries' doit contenir au moins une entrée dans {context}")

    vat_table: dict[str, dict[str, object]] = {}
    for code, entry in countries.items():
        code_str = str(code)
        if not isinstance(entry, dict):
            raise ConfigError(f"L'entrée pays '{code_str}' doit être un mapping dans {context}")
        if "name" not in entry:
            raise ConfigError(f"Clé 'name' manquante pour le pays '{code_str}' dans {context}")
        if "rate" not in entry:
            raise ConfigError(f"Clé 'rate' manquante pour le pays '{code_str}' dans {context}")

        rate = entry["rate"]
        if not isinstance(rate, (int, float)):
            raise ConfigError(f"Taux TVA invalide pour le pays '{code_str}' dans {context} : doit être un nombre")

        rate_float = float(rate)
        if rate_float < 0:
            raise ConfigError(
                f"Taux TVA invalide pour le pays '{code_str}' dans {context} : "
                f"{rate_float}% est négatif (doit être entre 0 et 100)"
            )
        if rate_float > 100:
            raise ConfigError(
                f"Taux TVA invalide pour le pays '{code_str}' dans {context} : "
                f"{rate_float}% dépasse 100% (doit être entre 0 et 100)"
            )

        if "alpha2" not in entry:
            raise ConfigError(f"Clé 'alpha2' manquante pour le pays '{code_str}' dans {context}")
        alpha2 = entry["alpha2"]
        if not isinstance(alpha2, str) or len(alpha2) != 2:
            raise ConfigError(
                f"'alpha2' invalide pour le pays '{code_str}' dans {context} : "
                f"doit être une chaîne de 2 caractères (reçu : {alpha2!r})"
            )

        vat_table[code_str] = {"name": str(entry["name"]), "rate": rate_float, "alpha2": str(alpha2)}

    return vat_table


def _validate_channels(data: dict[str, object]) -> dict[str, ChannelConfig]:
    """Valide et extrait la configuration des canaux."""
    context = "channels.yaml"

    channels_raw = _require_key(data, "channels", context)
    if not isinstance(channels_raw, dict):
        raise ConfigError(f"'channels' doit être un mapping dans {context}")

    channels: dict[str, ChannelConfig] = {}
    for chan_name, chan_data in channels_raw.items():
        chan_str = str(chan_name)
        if not isinstance(chan_data, dict):
            raise ConfigError(f"Canal '{chan_str}' doit être un mapping dans {context}")

        # Files
        if "files" not in chan_data:
            raise ConfigError(f"Clé 'files' manquante pour le canal '{chan_str}' dans {context}")
        files = chan_data["files"]
        if not isinstance(files, dict) or len(files) == 0:
            raise ConfigError(f"'files' doit contenir au moins un pattern pour le canal '{chan_str}' dans {context}")
        for file_key, pattern in files.items():
            if not pattern or not str(pattern).strip():
                raise ConfigError(
                    f"Pattern fichier vide pour '{file_key}' du canal '{chan_str}' dans {context}"
                )

        # Encoding
        if "encoding" not in chan_data:
            raise ConfigError(f"Clé 'encoding' manquante pour le canal '{chan_str}' dans {context}")
        encoding = str(chan_data["encoding"])
        if encoding not in SUPPORTED_ENCODINGS:
            raise ConfigError(
                f"Encodage '{encoding}' non supporté pour le canal {chan_str}. "
                f"Encodages acceptés : {', '.join(sorted(SUPPORTED_ENCODINGS))}"
            )

        # Separator
        if "separator" not in chan_data:
            raise ConfigError(f"Clé 'separator' manquante pour le canal '{chan_str}' dans {context}")
        separator = str(chan_data["separator"])
        if separator not in SUPPORTED_SEPARATORS:
            raise ConfigError(
                f"Séparateur '{separator}' non supporté pour le canal {chan_str}. "
                f"Séparateurs acceptés : {', '.join(sorted(SUPPORTED_SEPARATORS))}"
            )

        default_country_code = (
            str(chan_data["default_country_code"]) if "default_country_code" in chan_data else None
        )

        commission_vat_rate: float | None = None
        if "commission_vat_rate" in chan_data:
            raw_cvr = chan_data["commission_vat_rate"]
            if not isinstance(raw_cvr, (int, float)):
                raise ConfigError(
                    f"'commission_vat_rate' doit être un nombre pour le canal '{chan_str}' dans {context}"
                )
            commission_vat_rate = float(raw_cvr)

        channels[chan_str] = ChannelConfig(
            files={str(k): str(v) for k, v in files.items()},
            encoding=encoding,
            separator=separator,
            default_country_code=default_country_code,
            commission_vat_rate=commission_vat_rate,
        )

    return channels


def load_config(config_dir: Path) -> AppConfig:
    """Charge et valide la configuration complète depuis un répertoire.

    Args:
        config_dir: Répertoire contenant les fichiers YAML de configuration.

    Returns:
        AppConfig validée.

    Raises:
        ConfigError: Si un fichier est manquant, malformé, ou contient des valeurs invalides.
    """
    logger.info("Chargement de la configuration depuis %s", config_dir)

    chart_data = _load_yaml(config_dir / "chart_of_accounts.yaml")
    vat_data = _load_yaml(config_dir / "vat_table.yaml")
    channels_data = _load_yaml(config_dir / "channels.yaml")

    clients, fournisseurs, psp, transit, banque, comptes_speciaux, prefix, canal_codes, tva_prefix = _validate_chart(chart_data)
    vat_table = _validate_vat(vat_data)
    channels = _validate_channels(channels_data)

    alpha2_to_numeric: dict[str, str] = {
        str(entry["alpha2"]): country_code
        for country_code, entry in vat_table.items()
    }

    raw_tolerance = chart_data.get("matching_tolerance", 0.01)
    matching_tolerance = float(str(raw_tolerance))

    config = AppConfig(
        clients=clients,
        fournisseurs=fournisseurs,
        psp=psp,
        transit=transit,
        banque=banque,
        comptes_speciaux=comptes_speciaux,
        comptes_vente_prefix=prefix,
        canal_codes=canal_codes,
        comptes_tva_prefix=tva_prefix,
        vat_table=vat_table,
        alpha2_to_numeric=alpha2_to_numeric,
        channels=channels,
        matching_tolerance=matching_tolerance,
    )

    logger.debug("matching_tolerance: %s", config.matching_tolerance)

    return config
