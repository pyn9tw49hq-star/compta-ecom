"""Génération des écritures de règlement et commission (PSP 511 + 627 → 411)."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.models import AccountingEntry, NormalizedTransaction, channel_display_name


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
    canal_display = channel_display_name(transaction.channel)
    is_refund = transaction.type == "refund"
    label_prefix = "Remb. PSP" if is_refund else "Règlement"
    # Orphan settlements: transactions without matching sale — mark label for FEC traceability
    orphan_tag = "[Orphelin] " if transaction.special_type == "orphan_settlement" else ""
    label = f"{orphan_tag}{label_prefix} {transaction.reference} {canal_display}"

    entries: list[AccountingEntry] = []
    intermed = psp_config.compte_intermediaire
    payout_ref = transaction.payout_reference or ""

    if intermed is not None:
        # Flux 4 lignes avec compte intermédiaire (46710001)
        # Paire 1 : 46710001 D/C (TTC) ↔ 411 C/D (TTC) — omise si total_411 == 0
        if total_411 != 0.0:
            entries.append(
                AccountingEntry(
                    date=transaction.date,
                    journal=config.journal_reglement,
                    account=intermed,
                    label=label,
                    debit=total_411 if total_411 > 0 else 0.0,
                    credit=abs(total_411) if total_411 < 0 else 0.0,
                    piece_number=transaction.reference,
                    lettrage=payout_ref,
                    channel=transaction.channel,
                    entry_type="settlement",
                )
            )
            entries.append(
                AccountingEntry(
                    date=transaction.date,
                    journal=config.journal_reglement,
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

        # Paire 2 : 627 D/C (commission) ↔ 46710001 C/D (commission) — omise si commission == 0
        if commission != 0.0:
            entries.append(
                AccountingEntry(
                    date=transaction.date,
                    journal=config.journal_reglement,
                    account=commission_account,
                    label=label,
                    debit=commission if commission > 0 else 0.0,
                    credit=abs(commission) if commission < 0 else 0.0,
                    piece_number=transaction.reference,
                    lettrage="",
                    channel=transaction.channel,
                    entry_type="commission",
                )
            )
            entries.append(
                AccountingEntry(
                    date=transaction.date,
                    journal=config.journal_reglement,
                    account=intermed,
                    label=label,
                    debit=abs(commission) if commission < 0 else 0.0,
                    credit=commission if commission > 0 else 0.0,
                    piece_number=transaction.reference,
                    lettrage=payout_ref,
                    channel=transaction.channel,
                    entry_type="commission",
                )
            )
    else:
        # Flux classique 3 lignes (511 D + 627 D / 411 C)
        # Ligne PSP 511 — omise si net == 0
        if net != 0.0:
            entries.append(
                AccountingEntry(
                    date=transaction.date,
                    journal=config.journal_reglement,
                    account=psp_config.compte,
                    label=label,
                    debit=net if net > 0 else 0.0,
                    credit=abs(net) if net < 0 else 0.0,
                    piece_number=transaction.reference,
                    lettrage=payout_ref,
                    channel=transaction.channel,
                    entry_type="settlement",
                )
            )

        # Ligne Commission 627 — omise si commission == 0
        if commission != 0.0:
            entries.append(
                AccountingEntry(
                    date=transaction.date,
                    journal=config.journal_reglement,
                    account=commission_account,
                    label=label,
                    debit=commission if commission > 0 else 0.0,
                    credit=abs(commission) if commission < 0 else 0.0,
                    piece_number=transaction.reference,
                    lettrage="",
                    channel=transaction.channel,
                    entry_type="commission",
                )
            )

        # Ligne 411 Client — omise si total_411 == 0
        if total_411 != 0.0:
            entries.append(
                AccountingEntry(
                    date=transaction.date,
                    journal=config.journal_reglement,
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
