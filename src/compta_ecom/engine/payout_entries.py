"""Génération des écritures de reversement PSP (58000000 → PSP 511)."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.models import AccountingEntry, Anomaly, PayoutSummary


def generate_payout_entries(
    payout: PayoutSummary, config: AppConfig
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Génère les écritures de reversement pour un PayoutSummary.

    Toujours en mode agrégé : 1 paire d'écritures (580 D / 511 C)
    pour le versement entier, avec lettrage = payout_reference.
    Les fichiers detail servent uniquement à détecter les refunds
    manquants (logique parser, pas engine).
    """
    return _generate_aggregated_payout_entries(payout, config)


def _generate_aggregated_payout_entries(
    payout: PayoutSummary, config: AppConfig
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Mode agrégé : 1 paire d'écritures pour le versement entier (logique existante)."""
    if payout.psp_type is None:
        # Multi-PSP payout: generate one entry pair per PSP if breakdown available
        if payout.psp_amounts:
            return _generate_aggregated_multi_psp_entries(payout, config)
        # Cross-period payout: no matched transactions in current dataset → info severity
        # True mixed PSP (transactions present but heterogeneous without breakdown) → warning
        is_cross_period = payout.matched_net_sum is None
        anomaly = Anomaly(
            type="mixed_psp_payout",
            severity="info" if is_cross_period else "warning",
            reference=payout.payout_reference or "",
            channel=payout.channel,
            detail=(
                f"Versement {payout.payout_reference} sans aucune transaction correspondante — probable versement couvrant une période différente de celle exportée"
                if is_cross_period
                else f"Versement {payout.payout_reference} contient plusieurs moyens de paiement différents — l'écriture de reversement devra être saisie manuellement"
            ),
            expected_value=None,
            actual_value=None,
        )
        return [], [anomaly]

    total = round(payout.total_amount, 2)
    if total == 0.0:
        return [], []

    psp_cfg = config.psp[payout.psp_type]
    psp_account = psp_cfg.compte_intermediaire or psp_cfg.compte
    transit_account = config.transit
    date_str = payout.payout_date.strftime("%Y-%m-%d")
    label = f"Reversement {payout.psp_type} {date_str}"
    ref = payout.payout_reference or f"PAYOUT-{date_str}"

    entries = [
        AccountingEntry(
            date=payout.payout_date,
            journal=config.journal_reglement,
            account=transit_account,
            label=label,
            debit=total if total > 0 else 0.0,
            credit=abs(total) if total < 0 else 0.0,
            piece_number=ref,
            lettrage="",
            channel=payout.channel,
            entry_type="payout",
        ),
        AccountingEntry(
            date=payout.payout_date,
            journal=config.journal_reglement,
            account=psp_account,
            label=label,
            debit=abs(total) if total < 0 else 0.0,
            credit=total if total > 0 else 0.0,
            piece_number=ref,
            lettrage=ref,
            channel=payout.channel,
            entry_type="payout",
        ),
    ]

    verify_balance(entries)
    return entries, []


def _generate_aggregated_multi_psp_entries(
    payout: PayoutSummary, config: AppConfig
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Mode agrégé multi-PSP : 1 paire d'écritures par PSP."""
    entries: list[AccountingEntry] = []
    anomalies: list[Anomaly] = []
    transit_account = config.transit
    date_str = payout.payout_date.strftime("%Y-%m-%d")
    ref = payout.payout_reference or f"PAYOUT-{date_str}"

    for psp_type, net in payout.psp_amounts.items():  # type: ignore[union-attr]
        amount = round(net, 2)
        if amount == 0.0:
            continue

        if psp_type not in config.psp:
            anomalies.append(
                Anomaly(
                    type="unknown_psp_detail",
                    severity="warning",
                    reference=ref,
                    channel=payout.channel,
                    detail=f"Moyen de paiement « {psp_type} » non configuré — impossible de déterminer le compte bancaire pour le versement {ref}",
                    expected_value=None,
                    actual_value=psp_type,
                )
            )
            continue

        psp_cfg = config.psp[psp_type]
        psp_account = psp_cfg.compte_intermediaire or psp_cfg.compte
        label = f"Reversement {psp_type} {date_str}"

        pair = [
            AccountingEntry(
                date=payout.payout_date,
                journal=config.journal_reglement,
                account=transit_account,
                label=label,
                debit=amount if amount > 0 else 0.0,
                credit=abs(amount) if amount < 0 else 0.0,
                piece_number=ref,
                lettrage="",
                channel=payout.channel,
                entry_type="payout",
            ),
            AccountingEntry(
                date=payout.payout_date,
                journal=config.journal_reglement,
                account=psp_account,
                label=label,
                debit=abs(amount) if amount < 0 else 0.0,
                credit=amount if amount > 0 else 0.0,
                piece_number=ref,
                lettrage=ref,
                channel=payout.channel,
                entry_type="payout",
            ),
        ]

        verify_balance(pair)
        entries.extend(pair)

    return entries, anomalies
