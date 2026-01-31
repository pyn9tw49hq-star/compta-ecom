"""Génération des écritures de règlement et commission (PSP 511 + 627 → 411)."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import JOURNAL_VENTE, verify_balance
from compta_ecom.models import AccountingEntry, NormalizedTransaction


def generate_settlement_entries(
    transaction: NormalizedTransaction, config: AppConfig
) -> list[AccountingEntry]:
    """Génère les écritures de règlement/commission pour une transaction PSP."""
    if transaction.payment_method is None:
        return []

    net = round(transaction.net_amount, 2)
    commission = round(transaction.commission_ttc, 2)
    total_411 = round(net + commission, 2)

    if net == 0.0 and commission == 0.0:
        return []

    psp_config = config.psp[transaction.payment_method]
    if psp_config.commission is None:
        raise ValueError(
            f"PSP '{transaction.payment_method}' missing commission account"
        )
    commission_account = psp_config.commission
    client_account = config.clients[transaction.channel]
    canal_display = transaction.channel.replace("_", " ").title()
    is_refund = transaction.type == "refund"
    label_prefix = "Remb. PSP" if is_refund else "Règlement"
    label = f"{label_prefix} {transaction.reference} {canal_display}"

    entries: list[AccountingEntry] = []

    # Ligne PSP 511 — omise si net == 0
    if net != 0.0:
        entries.append(
            AccountingEntry(
                date=transaction.date,
                journal=JOURNAL_VENTE,
                account=psp_config.compte,
                label=label,
                debit=net if net > 0 else 0.0,
                credit=abs(net) if net < 0 else 0.0,
                piece_number=transaction.reference,
                lettrage=transaction.reference,
                channel=transaction.channel,
                entry_type="settlement",
            )
        )

    # Ligne Commission 627 — omise si commission == 0
    if commission != 0.0:
        entries.append(
            AccountingEntry(
                date=transaction.date,
                journal=JOURNAL_VENTE,
                account=commission_account,
                label=label,
                debit=commission if commission > 0 else 0.0,
                credit=abs(commission) if commission < 0 else 0.0,
                piece_number=transaction.reference,
                lettrage=transaction.reference,
                channel=transaction.channel,
                entry_type="commission",
            )
        )

    # Ligne 411 Client — omise si total_411 == 0
    if total_411 != 0.0:
        entries.append(
            AccountingEntry(
                date=transaction.date,
                journal=JOURNAL_VENTE,
                account=client_account,
                label=label,
                debit=abs(total_411) if total_411 < 0 else 0.0,
                credit=total_411 if total_411 > 0 else 0.0,
                piece_number=transaction.reference,
                lettrage=transaction.reference,
                channel=transaction.channel,
                entry_type="settlement",
            )
        )

    if entries:
        verify_balance(entries)

    return entries
