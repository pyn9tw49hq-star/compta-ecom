"""Validation et application des overrides du plan comptable."""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from pydantic import BaseModel, field_validator

from compta_ecom.config.loader import AppConfig

# --- Regex de validation ---
RE_COMPTE_TIERS = re.compile(r"^[A-Z0-9]{3,15}$")
RE_COMPTE_CHARGE = re.compile(r"^[0-9]{8}$")
RE_CODE_JOURNAL = re.compile(r"^[A-Z]{2,3}$")


def _check_dict_values(values: dict[str, str] | None, pattern: re.Pattern[str], label: str) -> dict[str, str] | None:
    """Valide chaque valeur d'un dict optionnel contre une regex."""
    if values is None:
        return None
    for key, val in values.items():
        if not pattern.match(val):
            raise ValueError(f"{label} '{key}': format invalide '{val}'")
    return values


class ChargesOverride(BaseModel):
    """Override des comptes de charges."""

    commissions: dict[str, str] | None = None
    abonnements: dict[str, str] | None = None

    @field_validator("commissions", "abonnements")
    @classmethod
    def validate_charges(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        return _check_dict_values(v, RE_COMPTE_CHARGE, "Compte charge")


class JournauxVentesOverride(BaseModel):
    """Override des journaux de vente."""

    ventes: dict[str, str] | None = None
    achats: str | None = None
    reglement: str | None = None

    @field_validator("ventes")
    @classmethod
    def validate_ventes(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        return _check_dict_values(v, RE_CODE_JOURNAL, "Journal vente")

    @field_validator("achats", "reglement")
    @classmethod
    def validate_journal_code(cls, v: str | None) -> str | None:
        if v is not None and not RE_CODE_JOURNAL.match(v):
            raise ValueError(f"Code journal invalide : '{v}'")
        return v


class AccountOverridesSchema(BaseModel):
    """Schéma Pydantic pour les overrides du plan comptable."""

    clients: dict[str, str] | None = None
    fournisseurs: dict[str, str] | None = None
    charges: ChargesOverride | None = None
    tva_deductible: str | None = None
    journaux: JournauxVentesOverride | None = None

    @field_validator("clients", "fournisseurs")
    @classmethod
    def validate_tiers(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        return _check_dict_values(v, RE_COMPTE_TIERS, "Compte tiers")

    @field_validator("tva_deductible")
    @classmethod
    def validate_tva(cls, v: str | None) -> str | None:
        if v is not None and not RE_COMPTE_CHARGE.match(v):
            raise ValueError(f"Compte TVA déductible invalide : '{v}'")
        return v


def apply_overrides(config: AppConfig, overrides: dict[str, Any]) -> AppConfig:
    """Applique les overrides au config — merge partiel, retourne une copie."""
    schema = AccountOverridesSchema.model_validate(overrides)

    replacements: dict[str, Any] = {}

    if schema.clients:
        replacements["clients"] = {**config.clients, **schema.clients}

    if schema.fournisseurs:
        replacements["fournisseurs"] = {**config.fournisseurs, **schema.fournisseurs}

    if schema.charges:
        new_charges_mp = {k: dict(v) for k, v in config.comptes_charges_marketplace.items()}
        if schema.charges.commissions:
            for chan, compte in schema.charges.commissions.items():
                if chan not in new_charges_mp:
                    new_charges_mp[chan] = {}
                new_charges_mp[chan]["commission"] = compte
        if schema.charges.abonnements:
            for chan, compte in schema.charges.abonnements.items():
                if chan not in new_charges_mp:
                    new_charges_mp[chan] = {}
                new_charges_mp[chan]["abonnement"] = compte
        replacements["comptes_charges_marketplace"] = new_charges_mp

    if schema.tva_deductible:
        new_charges_mp = replacements.get(
            "comptes_charges_marketplace",
            {k: dict(v) for k, v in config.comptes_charges_marketplace.items()},
        )
        for chan_charges in new_charges_mp.values():
            if "tva_deductible" in chan_charges:
                chan_charges["tva_deductible"] = schema.tva_deductible
        replacements["comptes_charges_marketplace"] = new_charges_mp

    if schema.journaux:
        if schema.journaux.ventes:
            replacements["journaux_vente"] = {**config.journaux_vente, **schema.journaux.ventes}
        if schema.journaux.achats is not None:
            replacements["journal_achats"] = schema.journaux.achats
        if schema.journaux.reglement is not None:
            replacements["journal_reglement"] = schema.journaux.reglement

    if not replacements:
        return config

    return dataclasses.replace(config, **replacements)
