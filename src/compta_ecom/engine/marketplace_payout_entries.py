"""Génération des écritures de reversement marketplace (512 ↔ 401/compte spécial)."""

from __future__ import annotations

import logging

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import JOURNAL_REGLEMENT, verify_balance
from compta_ecom.models import AccountingEntry, NormalizedTransaction

logger = logging.getLogger(__name__)

_SPECIAL_LABELS: dict[str, str] = {
    "ADJUSTMENT": "Ajustement",
    "ECO_CONTRIBUTION": "Éco-contribution",
    "SUBSCRIPTION": "Abonnement",
    "REFUND_PENALTY": "Pénalité remb.",
}


def _resolve_payout_account(
    transaction: NormalizedTransaction, config: AppConfig
) -> str:
    """Résout le compte de contrepartie pour le reversement.

    special_type in comptes_speciaux → compte spécial, sinon → fournisseur.
    """
    if (
        transaction.special_type is not None
        and transaction.special_type in config.comptes_speciaux
    ):
        return config.comptes_speciaux[transaction.special_type]
    return config.fournisseurs[transaction.channel]


def generate_marketplace_payout(
    transaction: NormalizedTransaction, config: AppConfig
) -> list[AccountingEntry]:
    """Génère l'écriture de reversement marketplace (512 ↔ 401/compte spécial).

    Gère les transactions régulières et les lignes spéciales.
    Retourne [] si payout_date is None ou net_amount == 0.0.
    """
    if transaction.payout_date is None:
        if transaction.special_type is not None:
            logger.warning(
                "Ligne spéciale %s sans payout_date — inattendu",
                transaction.reference,
            )
        return []

    net = round(transaction.net_amount, 2)
    if net == 0.0:
        return []

    account = _resolve_payout_account(transaction, config)
    canal_display = transaction.channel.replace("_", " ").title()
    label_prefix = _SPECIAL_LABELS.get(
        transaction.special_type or "", "Reversement"
    )
    label = f"{label_prefix} {transaction.reference} {canal_display}"

    if net > 0:
        debit_account = config.banque
        credit_account = account
    else:
        debit_account = account
        credit_account = config.banque

    amount = round(abs(net), 2)

    entries = [
        AccountingEntry(
            date=transaction.payout_date,
            journal=JOURNAL_REGLEMENT,
            account=debit_account,
            label=label,
            debit=amount,
            credit=0.0,
            piece_number=transaction.reference,
            lettrage=transaction.reference,
            channel=transaction.channel,
            entry_type="payout",
        ),
        AccountingEntry(
            date=transaction.payout_date,
            journal=JOURNAL_REGLEMENT,
            account=credit_account,
            label=label,
            debit=0.0,
            credit=amount,
            piece_number=transaction.reference,
            lettrage=transaction.reference,
            channel=transaction.channel,
            entry_type="payout",
        ),
    ]

    verify_balance(entries)

    return entries
