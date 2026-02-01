"""Génération des écritures de commission marketplace (401 ↔ 411)."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import JOURNAL_REGLEMENT, verify_balance
from compta_ecom.models import AccountingEntry, NormalizedTransaction

# commission_ht non utilisée — commission marketplace comptabilisée en TTC uniquement


def generate_marketplace_commission(
    transaction: NormalizedTransaction, config: AppConfig
) -> list[AccountingEntry]:
    """Génère les écritures de commission marketplace (401 ↔ 411).

    Utilise la convention signée : positif → débit, négatif → crédit (abs).
    Retourne [] si commission_ttc == 0.0.
    """
    commission = round(transaction.commission_ttc, 2)

    if commission == 0.0:
        return []

    fournisseur_account = config.fournisseurs[transaction.channel]
    client_account = config.clients[transaction.channel]

    canal_display = transaction.channel.replace("_", " ").title()
    label_prefix = "Commission" if transaction.type == "sale" else "Remb. commission"
    label = f"{label_prefix} {transaction.reference} {canal_display}"

    if commission > 0:
        debit_account = fournisseur_account
        credit_account = client_account
    else:
        debit_account = client_account
        credit_account = fournisseur_account

    amount = round(abs(commission), 2)

    entries = [
        AccountingEntry(
            date=transaction.date,
            journal=JOURNAL_REGLEMENT,
            account=debit_account,
            label=label,
            debit=amount,
            credit=0.0,
            piece_number=transaction.reference,
            lettrage=transaction.reference,
            channel=transaction.channel,
            entry_type="commission",
        ),
        AccountingEntry(
            date=transaction.date,
            journal=JOURNAL_REGLEMENT,
            account=credit_account,
            label=label,
            debit=0.0,
            credit=amount,
            piece_number=transaction.reference,
            lettrage=transaction.reference,
            channel=transaction.channel,
            entry_type="commission",
        ),
    ]

    verify_balance(entries)

    return entries
