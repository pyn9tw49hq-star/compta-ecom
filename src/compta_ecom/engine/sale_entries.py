"""Génération des écritures de vente (411 → 707 + 7085 + 4457)."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import (
    JOURNAUX_VENTE,
    build_account,
    build_shipping_account,
    resolve_shipping_zone,
    verify_balance,
)
from compta_ecom.models import AccountingEntry, NormalizedTransaction


def generate_sale_entries(
    transaction: NormalizedTransaction, config: AppConfig
) -> list[AccountingEntry]:
    """Génère les écritures de vente ou d'avoir pour une transaction."""
    accounts = _resolve_accounts(transaction, config)
    amounts = _compute_amounts(transaction)
    # Décathlon : lettrage client par cycle de paiement pour rapprochement avec Paiement
    client_lettrage = transaction.reference
    if transaction.channel == "decathlon" and transaction.payout_reference:
        client_lettrage = transaction.payout_reference
    entries = _build_entries(transaction, accounts, amounts, client_lettrage)
    verify_balance(entries)
    return entries


def _resolve_accounts(
    transaction: NormalizedTransaction, config: AppConfig
) -> dict[str, str]:
    channel_code = config.canal_codes[transaction.channel]
    accounts = {
        "client": config.clients[transaction.channel],
        "vente": build_account(
            config.comptes_vente_prefix, channel_code, transaction.country_code
        ),
        "tva": build_account(config.comptes_tva_prefix, None, transaction.country_code),
    }
    if transaction.shipping_ht != 0.0:
        zone = resolve_shipping_zone(transaction.country_code, config.vat_table)
        zone_code = config.zones_port[zone]
        accounts["port"] = build_shipping_account(
            config.comptes_port_prefix, channel_code, zone_code
        )
    return accounts


def _compute_amounts(transaction: NormalizedTransaction) -> dict[str, float]:
    return {
        "ht": round(transaction.amount_ht, 2),
        "shipping_ht": round(transaction.shipping_ht, 2),
        "tva": round(transaction.amount_tva + transaction.shipping_tva, 2),
        "ttc": transaction.amount_ttc,
    }


def _build_entries(
    transaction: NormalizedTransaction,
    accounts: dict[str, str],
    amounts: dict[str, float],
    client_lettrage: str = "",
) -> list[AccountingEntry]:
    canal_display = transaction.channel.replace("_", " ").title()
    journal = JOURNAUX_VENTE[transaction.channel]
    is_sale = transaction.type == "sale"
    label_prefix = "Vente" if is_sale else "Avoir"
    label = f"{label_prefix} {transaction.reference} {canal_display}"
    entry_type = "sale" if is_sale else "refund"

    ttc = round(amounts["ttc"], 2)
    ht = round(amounts["ht"], 2)
    shipping_ht = round(amounts["shipping_ht"], 2)
    tva = round(amounts["tva"], 2)

    entries: list[AccountingEntry] = []

    # Ligne 411 (client)
    entries.append(
        AccountingEntry(
            date=transaction.date,
            journal=journal,
            account=accounts["client"],
            label=label,
            debit=ttc if is_sale else 0.0,
            credit=0.0 if is_sale else ttc,
            piece_number=transaction.reference,
            lettrage=client_lettrage or transaction.reference,
            channel=transaction.channel,
            entry_type=entry_type,
        )
    )

    # Ligne 707 (vente produit HT, hors frais de port)
    entries.append(
        AccountingEntry(
            date=transaction.date,
            journal=journal,
            account=accounts["vente"],
            label=label,
            debit=0.0 if is_sale else ht,
            credit=ht if is_sale else 0.0,
            piece_number=transaction.reference,
            lettrage="",
            channel=transaction.channel,
            entry_type=entry_type,
        )
    )

    # Ligne 7085 (frais de port HT) — omise si shipping_ht = 0
    if shipping_ht != 0.0:
        entries.append(
            AccountingEntry(
                date=transaction.date,
                journal=journal,
                account=accounts["port"],
                label=label,
                debit=0.0 if is_sale else shipping_ht,
                credit=shipping_ht if is_sale else 0.0,
                piece_number=transaction.reference,
                lettrage="",
                channel=transaction.channel,
                entry_type=entry_type,
            )
        )

    # Ligne 4457 (TVA) — omise si TVA = 0
    if tva != 0.0:
        entries.append(
            AccountingEntry(
                date=transaction.date,
                journal=journal,
                account=accounts["tva"],
                label=label,
                debit=0.0 if is_sale else tva,
                credit=tva if is_sale else 0.0,
                piece_number=transaction.reference,
                lettrage="",
                channel=transaction.channel,
                entry_type=entry_type,
            )
        )

    return entries
