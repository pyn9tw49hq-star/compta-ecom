"""Génération des écritures de commission marketplace (401 ↔ 411)."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.models import AccountingEntry, NormalizedTransaction, channel_display_name


def generate_marketplace_commission(
    transaction: NormalizedTransaction, config: AppConfig
) -> list[AccountingEntry]:
    """Génère les écritures de commission marketplace (401 ↔ 411).

    Convention signée :
    - commission_ttc < 0 (vente) → Débit 401 Fournisseur, Crédit 411 Client
    - commission_ttc > 0 (retour/restituée) → Débit 411 Client, Crédit 401 Fournisseur

    Lorsqu'un compte de charge est configuré ET que la TVA déductible est
    disponible (commission_ht ≠ None, TVA > 0), génère 3 écritures :
    charge HT + TVA déductible + client TTC.

    Retourne [] si commission_ttc == 0.0.
    """
    commission = round(transaction.commission_ttc, 2)

    if commission == 0.0:
        return []

    # Compte de charge marketplace si configuré (ex: Decathlon → 62220800)
    charges_mp = config.comptes_charges_marketplace.get(transaction.channel, {})
    charge_account = charges_mp.get("commission")
    tva_deductible_account = charges_mp.get("tva_deductible")

    counterpart_account = charge_account or config.fournisseurs[transaction.channel]
    client_account = config.clients[transaction.channel]
    journal = config.journal_achats if charge_account is not None else config.journal_reglement

    canal_display = channel_display_name(transaction.channel)
    label_prefix = "Commission" if transaction.type == "sale" else "Remb. commission"
    label = f"{label_prefix} {transaction.reference} {canal_display}"

    # Lettrage : pas de lettrage sur le compte de contrepartie (fournisseur ou charge)
    # pour Décathlon ; le compte client est lettré par cycle de paiement
    if charge_account is not None:
        # Compte de charge : jamais de lettrage (classe 6)
        counterpart_lettrage = ""
        if transaction.payout_reference:
            client_lettrage = transaction.payout_reference
        elif transaction.channel == "manomano":
            client_lettrage = ""
        else:
            client_lettrage = transaction.reference
    elif transaction.channel in ("decathlon", "leroy_merlin") and transaction.payout_reference:
        client_lettrage = transaction.payout_reference
        counterpart_lettrage = ""
    else:
        client_lettrage = transaction.reference
        counterpart_lettrage = transaction.reference

    # Déterminer si on doit éclater en HT + TVA déductible
    tva_amount = 0.0
    ht_amount = round(abs(commission), 2)
    if (
        charge_account is not None
        and tva_deductible_account is not None
        and transaction.commission_ht is not None
    ):
        ht_amount = round(abs(transaction.commission_ht), 2)
        tva_amount = round(abs(commission) - ht_amount, 2)

    ttc_amount = round(abs(commission), 2)

    entries: list[AccountingEntry] = []

    if commission > 0:
        # Remboursement commission (retour) : client au débit, contrepartie(s) au crédit
        entries.append(AccountingEntry(
            date=transaction.date,
            journal=journal,
            account=client_account,
            label=label,
            debit=ttc_amount,
            credit=0.0,
            piece_number=transaction.reference,
            lettrage=client_lettrage,
            channel=transaction.channel,
            entry_type="commission",
        ))
        entries.append(AccountingEntry(
            date=transaction.date,
            journal=journal,
            account=counterpart_account,
            label=label,
            debit=0.0,
            credit=ht_amount,
            piece_number=transaction.reference,
            lettrage=counterpart_lettrage,
            channel=transaction.channel,
            entry_type="commission",
        ))
        if tva_amount > 0:
            entries.append(AccountingEntry(
                date=transaction.date,
                journal=journal,
                account=tva_deductible_account,
                label=label,
                debit=0.0,
                credit=tva_amount,
                piece_number=transaction.reference,
                lettrage="",
                channel=transaction.channel,
                entry_type="commission",
            ))
    else:
        # Commission vente normale : contrepartie(s) au débit, client au crédit
        entries.append(AccountingEntry(
            date=transaction.date,
            journal=journal,
            account=counterpart_account,
            label=label,
            debit=ht_amount,
            credit=0.0,
            piece_number=transaction.reference,
            lettrage=counterpart_lettrage,
            channel=transaction.channel,
            entry_type="commission",
        ))
        if tva_amount > 0:
            entries.append(AccountingEntry(
                date=transaction.date,
                journal=journal,
                account=tva_deductible_account,
                label=label,
                debit=tva_amount,
                credit=0.0,
                piece_number=transaction.reference,
                lettrage="",
                channel=transaction.channel,
                entry_type="commission",
            ))
        entries.append(AccountingEntry(
            date=transaction.date,
            journal=journal,
            account=client_account,
            label=label,
            debit=0.0,
            credit=ttc_amount,
            piece_number=transaction.reference,
            lettrage=client_lettrage,
            channel=transaction.channel,
            entry_type="commission",
        ))

    verify_balance(entries)

    return entries
