"""Génération des écritures de règlement direct (Klarna, Bank Deposit — sans PSP)."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.models import AccountingEntry, NormalizedTransaction, channel_display_name


def generate_direct_payment_entries(
    transaction: NormalizedTransaction, config: AppConfig
) -> list[AccountingEntry]:
    """Génère 2 lignes RG : débit compte direct + crédit 411 client."""
    if transaction.payment_method is None:
        return []

    dp_config = config.direct_payments.get(transaction.payment_method)
    if dp_config is None:
        return []

    amount = round(transaction.amount_ttc, 2)
    if amount <= 0.0:
        return []

    client_account = config.clients[transaction.channel]
    canal_display = channel_display_name(transaction.channel)
    label = f"Règlement direct {transaction.reference} {canal_display}"

    entries = [
        AccountingEntry(
            date=transaction.date,
            journal=config.journal_reglement,
            account=dp_config.compte,
            label=label,
            debit=amount,
            credit=0.0,
            piece_number=transaction.reference,
            lettrage="",
            channel=transaction.channel,
            entry_type="settlement",
        ),
        AccountingEntry(
            date=transaction.date,
            journal=config.journal_reglement,
            account=client_account,
            label=label,
            debit=0.0,
            credit=amount,
            piece_number=transaction.reference,
            lettrage=transaction.reference,
            channel=transaction.channel,
            entry_type="settlement",
        ),
    ]

    verify_balance(entries)
    return entries
