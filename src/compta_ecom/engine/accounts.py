"""Utilitaires partagés du moteur d'écritures comptables."""

from __future__ import annotations

from compta_ecom.models import AccountingEntry, BalanceError

JOURNAL_VENTE = "VE"
JOURNAL_BANQUE = "BQ"


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


def verify_balance(entries: list[AccountingEntry]) -> None:
    """Vérifie l'équilibre débit/crédit d'un ensemble d'écritures. Lève BalanceError si déséquilibre."""
    total_debit = round(sum(e.debit for e in entries), 2)
    total_credit = round(sum(e.credit for e in entries), 2)
    if total_debit != total_credit:
        raise BalanceError(
            f"Déséquilibre écriture: débit={total_debit}, crédit={total_credit}"
        )
