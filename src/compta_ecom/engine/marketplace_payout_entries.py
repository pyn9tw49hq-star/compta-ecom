"""Génération des écritures de reversement marketplace (512 ↔ 401/compte spécial)."""

from __future__ import annotations

import logging

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
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

    Priorité :
    1. SUBSCRIPTION + comptes_charges_marketplace.abonnement → compte de charge
    2. special_type in comptes_speciaux → compte spécial
    3. sinon → fournisseur
    """
    if transaction.special_type == "SUBSCRIPTION":
        charges_mp = config.comptes_charges_marketplace.get(transaction.channel, {})
        charge_account = charges_mp.get("abonnement")
        if charge_account is not None:
            return charge_account
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

    amount = round(abs(net), 2)

    # Frais d'abonnement : date d'écriture = date de création (transaction.date)
    # Autres reversements : date d'écriture = date du cycle de paiement (payout_date)
    entry_date = transaction.date if transaction.special_type == "SUBSCRIPTION" else transaction.payout_date

    # Lettrage : les comptes de charge (classe 6) n'ont jamais de lettrage.
    # Pour Décathlon SUBSCRIPTION, le compte client est lettré par cycle de paiement.
    charges_mp = config.comptes_charges_marketplace.get(transaction.channel, {})
    has_charge_account = (
        transaction.special_type == "SUBSCRIPTION" and "abonnement" in charges_mp
    )
    journal = config.journal_achats if has_charge_account else config.journal_reglement
    tva_deductible_account = charges_mp.get("tva_deductible")
    default_lettrage = transaction.reference

    if has_charge_account:
        client_ref = transaction.payout_reference or transaction.reference
    elif (
        transaction.channel in ("decathlon", "leroy_merlin")
        and transaction.special_type == "SUBSCRIPTION"
        and transaction.payout_reference
    ):
        client_ref = transaction.payout_reference
    else:
        client_ref = default_lettrage

    # Calculer la TVA déductible pour les abonnements avec charge account
    fee_tva = 0.0
    if has_charge_account and tva_deductible_account is not None:
        channel_config = config.channels.get(transaction.channel)
        if channel_config and channel_config.commission_vat_rate:
            fee_tva = round(amount * channel_config.commission_vat_rate / 100, 2)

    if fee_tva > 0:
        # Abonnement avec TVA déductible : 3 écritures (charge HT + TVA + client TTC)
        ttc_amount = round(amount + fee_tva, 2)

        if net > 0:
            # Avoir / remboursement : client D TTC, charge C HT, TVA C
            entries = [
                AccountingEntry(
                    date=entry_date,
                    journal=journal,
                    account=bank_or_client_account,  # client (411LM)
                    label=label,
                    debit=ttc_amount,
                    credit=0.0,
                    piece_number=transaction.reference,
                    lettrage=client_ref,
                    channel=transaction.channel,
                    entry_type=entry_type,
                ),
                AccountingEntry(
                    date=entry_date,
                    journal=journal,
                    account=account,  # charge account (61311113)
                    label=label,
                    debit=0.0,
                    credit=amount,
                    piece_number=transaction.reference,
                    lettrage="",
                    channel=transaction.channel,
                    entry_type=entry_type,
                ),
                AccountingEntry(
                    date=entry_date,
                    journal=journal,
                    account=tva_deductible_account,  # TVA déductible (44566001)
                    label=label,
                    debit=0.0,
                    credit=fee_tva,
                    piece_number=transaction.reference,
                    lettrage="",
                    channel=transaction.channel,
                    entry_type=entry_type,
                ),
            ]
        else:
            # Charge normale : charge D HT, TVA D, client C TTC
            entries = [
                AccountingEntry(
                    date=entry_date,
                    journal=journal,
                    account=account,  # charge account (61311113)
                    label=label,
                    debit=amount,
                    credit=0.0,
                    piece_number=transaction.reference,
                    lettrage="",
                    channel=transaction.channel,
                    entry_type=entry_type,
                ),
                AccountingEntry(
                    date=entry_date,
                    journal=journal,
                    account=tva_deductible_account,  # TVA déductible (44566001)
                    label=label,
                    debit=fee_tva,
                    credit=0.0,
                    piece_number=transaction.reference,
                    lettrage="",
                    channel=transaction.channel,
                    entry_type=entry_type,
                ),
                AccountingEntry(
                    date=entry_date,
                    journal=journal,
                    account=bank_or_client_account,  # client (411LM)
                    label=label,
                    debit=0.0,
                    credit=ttc_amount,
                    piece_number=transaction.reference,
                    lettrage=client_ref,
                    channel=transaction.channel,
                    entry_type=entry_type,
                ),
            ]
    else:
        # Cas standard : 2 écritures (sans TVA déductible)
        if net > 0:
            debit_account = bank_or_client_account
            credit_account = account
        else:
            debit_account = account
            credit_account = bank_or_client_account

        if has_charge_account:
            client_account_val = config.clients[transaction.channel]
            debit_lettrage = client_ref if debit_account == client_account_val else ""
            credit_lettrage = client_ref if credit_account == client_account_val else ""
        else:
            debit_lettrage = client_ref
            credit_lettrage = client_ref

        entries = [
            AccountingEntry(
                date=entry_date,
                journal=journal,
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
                journal=journal,
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
            journal=config.journal_reglement,
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
            journal=config.journal_reglement,
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
