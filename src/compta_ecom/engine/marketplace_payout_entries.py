"""Génération des écritures de reversement marketplace (512 ↔ 401/compte spécial)."""

from __future__ import annotations

import logging

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import JOURNAL_REGLEMENT, verify_balance
from compta_ecom.models import AccountingEntry, NormalizedTransaction, PayoutSummary

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
    if transaction.payout_date is None and transaction.special_type != "SUBSCRIPTION":
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

    # Déterminer le type d'écriture et le compte banque/client
    if transaction.special_type == "SUBSCRIPTION":
        entry_type = "fee"
        # Frais d'abonnement: utiliser le compte client au lieu de la banque
        bank_or_client_account = config.clients[transaction.channel]
    else:
        entry_type = "payout"
        bank_or_client_account = config.banque

    if net > 0:
        debit_account = bank_or_client_account
        credit_account = account
    else:
        debit_account = account
        credit_account = bank_or_client_account

    amount = round(abs(net), 2)

    # Frais d'abonnement : date d'écriture = date de création (transaction.date)
    # Autres reversements : date d'écriture = date du cycle de paiement (payout_date)
    entry_date = transaction.date if transaction.special_type == "SUBSCRIPTION" else transaction.payout_date

    # Décathlon SUBSCRIPTION : seul le compte client (CDECATHLON) est lettré
    default_lettrage = transaction.reference
    if (
        transaction.channel == "decathlon"
        and transaction.special_type == "SUBSCRIPTION"
        and transaction.payout_reference
    ):
        client_account_val = config.clients[transaction.channel]
        debit_lettrage = transaction.payout_reference if debit_account == client_account_val else ""
        credit_lettrage = transaction.payout_reference if credit_account == client_account_val else ""
    else:
        debit_lettrage = default_lettrage
        credit_lettrage = default_lettrage

    entries = [
        AccountingEntry(
            date=entry_date,
            journal=JOURNAL_REGLEMENT,
            account=debit_account,
            label=label,
            debit=amount,
            credit=0.0,
            piece_number=transaction.reference,
            lettrage=debit_lettrage,
            channel=transaction.channel,
            entry_type=entry_type,
        ),
        AccountingEntry(
            date=entry_date,
            journal=JOURNAL_REGLEMENT,
            account=credit_account,
            label=label,
            debit=0.0,
            credit=amount,
            piece_number=transaction.reference,
            lettrage=credit_lettrage,
            channel=transaction.channel,
            entry_type=entry_type,
        ),
    ]

    verify_balance(entries)

    return entries


def generate_marketplace_payout_from_summary(
    payout: PayoutSummary, config: AppConfig
) -> list[AccountingEntry]:
    """Génère les écritures de payout marketplace agrégé (580 ↔ 411).

    Pour les lignes "Paiement" des marketplaces (Decathlon, etc.):
    - Débite le compte transit (580)
    - Crédite le compte client (CDECATHLON)

    Retourne [] si total_amount == 0.0.
    """
    total = round(payout.total_amount, 2)
    if total == 0.0:
        return []

    client_account = config.clients[payout.channel]
    transit_account = config.transit
    date_str = payout.payout_date.strftime("%Y-%m-%d")
    label = f"Reversement {payout.channel.replace('_', ' ').title()} {date_str}"
    ref = payout.payout_reference or f"PAYOUT-{date_str}"

    # Les montants de paiement sont négatifs (sortie d'argent du marketplace)
    # Donc abs(total) pour les écritures
    amount = round(abs(total), 2)

    entries = [
        AccountingEntry(
            date=payout.payout_date,
            journal=JOURNAL_REGLEMENT,
            account=transit_account,
            label=label,
            debit=amount,
            credit=0.0,
            piece_number=ref,
            lettrage="",
            channel=payout.channel,
            entry_type="payout",
        ),
        AccountingEntry(
            date=payout.payout_date,
            journal=JOURNAL_REGLEMENT,
            account=client_account,
            label=label,
            debit=0.0,
            credit=amount,
            piece_number=ref,
            lettrage=ref,
            channel=payout.channel,
            entry_type="payout",
        ),
    ]

    verify_balance(entries)

    return entries
