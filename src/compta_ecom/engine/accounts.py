"""Utilitaires partagés du moteur d'écritures comptables."""

from __future__ import annotations

import dataclasses
from collections import defaultdict

from compta_ecom.models import AccountingEntry, BalanceError

JOURNAL_REGLEMENT = "RG"

JOURNAUX_VENTE: dict[str, str] = {
    "shopify": "VE",
    "manomano": "MM",
    "decathlon": "DEC",
    "leroy_merlin": "LM",
}


def build_account(
    prefix: str, channel_code: str | None, country_code: str
) -> str:
    """Construit un numéro de compte par concaténation.

    Concatène ``prefix + channel_code + country_code``.
    Si *channel_code* est ``None`` ou ``""``, il est omis.

    Examples:
        >>> build_account("707", "01", "250")
        '70701250'
        >>> build_account("4457", None, "250")
        '4457250'
    """
    if channel_code:
        return f"{prefix}{channel_code}{country_code}"
    return f"{prefix}{country_code}"


FRANCE_CODE = "250"
DOM_TOM_CODES = {"974"}


def resolve_shipping_zone(country_code: str, vat_table: dict[str, object]) -> str:
    """Détermine la zone géographique pour le compte de frais de port.

    Returns:
        ``"france"`` | ``"ue"`` | ``"hors_ue"``
    """
    if country_code == FRANCE_CODE:
        return "france"
    if country_code in DOM_TOM_CODES or country_code not in vat_table:
        return "hors_ue"
    return "ue"


def build_shipping_account(prefix: str, channel_code: str, zone_code: str) -> str:
    """Construit un numéro de compte de frais de port (8 chiffres).

    Format : ``prefix + channel_code + zone_code``

    Examples:
        >>> build_shipping_account("7085", "02", "00")
        '70850200'
    """
    return f"{prefix}{channel_code}{zone_code}"


def verify_balance(entries: list[AccountingEntry]) -> None:
    """Vérifie l'équilibre débit/crédit d'un ensemble d'écritures. Lève BalanceError si déséquilibre."""
    total_debit = round(sum(e.debit for e in entries), 2)
    total_credit = round(sum(e.credit for e in entries), 2)
    if total_debit != total_credit:
        raise BalanceError(
            f"Déséquilibre écriture: débit={total_debit}, crédit={total_credit}"
        )


def _index_to_letter(index: int) -> str:
    """Convertit un index (0-based) en code lettrage alphabétique.

    Séquence : A, B, ..., Z, AA, BB, ..., ZZ, AAA, BBB, ..., ZZZ, etc.
    """
    repeat = index // 26 + 1
    letter = chr(ord("A") + index % 26)
    return letter * repeat


def normalize_lettrage(entries: list[AccountingEntry]) -> list[AccountingEntry]:
    """Remplace les valeurs de lettrage par des lettres alphabétiques séquentielles.

    Compteurs indépendants par préfixe de compte (3 premiers caractères).
    Les entrées avec lettrage vide sont inchangées.
    """
    # Grouper par préfixe de compte : { "411": {"#1118": "A", "#1119": "B"}, "511": {...} }
    counters: dict[str, int] = defaultdict(int)
    mappings: dict[str, dict[str, str]] = defaultdict(dict)

    for entry in entries:
        if not entry.lettrage:
            continue
        prefix = entry.account[:3]
        if entry.lettrage not in mappings[prefix]:
            mappings[prefix][entry.lettrage] = _index_to_letter(counters[prefix])
            counters[prefix] += 1

    return [
        dataclasses.replace(entry, lettrage=mappings[entry.account[:3]][entry.lettrage])
        if entry.lettrage and entry.account[:3] in mappings
        else entry
        for entry in entries
    ]
