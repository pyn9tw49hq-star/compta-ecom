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

    Convention signée :
    - commission_ttc < 0 (vente) → Débit 401 Fournisseur, Crédit 411 Client
    - commission_ttc > 0 (retour/restituée) → Débit 411 Client, Crédit 401 Fournisseur
    Retourne [] si commission_ttc == 0.0.
    """
    commission = round(transaction.commission_ttc, 2)

    if commission == 0.0:
        return []

    # Compte de charge marketplace si configuré (ex: Decathlon → 62220800)
    charges_mp = config.comptes_charges_marketplace.get(transaction.channel, {})
    charge_account = charges_mp.get("commission")

    counterpart_account = charge_account or config.fournisseurs[transaction.channel]
    client_account = config.clients[transaction.channel]

    canal_display = transaction.channel.replace("_", " ").title()
    label_prefix = "Commission" if transaction.type == "sale" else "Remb. commission"
    label = f"{label_prefix} {transaction.reference} {canal_display}"

    # Lettrage : pas de lettrage sur le compte de contrepartie (fournisseur ou charge)
    # pour Décathlon ; le compte client est lettré par cycle de paiement
    if charge_account is not None:
        # Compte de charge : jamais de lettrage (classe 6)
        counterpart_lettrage = ""
        client_lettrage = transaction.payout_reference or transaction.reference
    elif transaction.channel == "decathlon" and transaction.payout_reference:
        client_lettrage = transaction.payout_reference
        counterpart_lettrage = ""
    else:
        client_lettrage = transaction.reference
        counterpart_lettrage = transaction.reference

    if commission > 0:
        # Remboursement commission (retour) : 411 Client au débit, contrepartie au crédit
        debit_account = client_account
        debit_lettrage = client_lettrage
        credit_account = counterpart_account
        credit_lettrage = counterpart_lettrage
    else:
        # Commission vente normale : contrepartie au débit, 411 Client au crédit
        debit_account = counterpart_account
        debit_lettrage = counterpart_lettrage
        credit_account = client_account
        credit_lettrage = client_lettrage

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
            lettrage=debit_lettrage,
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
            lettrage=credit_lettrage,
            channel=transaction.channel,
            entry_type="commission",
        ),
    ]

    verify_balance(entries)

    return entries
