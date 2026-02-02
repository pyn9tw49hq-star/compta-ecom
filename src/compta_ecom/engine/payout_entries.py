"""Génération des écritures de reversement PSP (58000000 → PSP 511)."""

from __future__ import annotations

import logging

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import JOURNAL_REGLEMENT, verify_balance
from compta_ecom.models import AccountingEntry, Anomaly, PayoutSummary

logger = logging.getLogger(__name__)


def generate_payout_entries(
    payout: PayoutSummary, config: AppConfig
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Génère les écritures de reversement pour un PayoutSummary.

    Dispatch entre mode détaillé (1 paire par commande) et mode agrégé
    (1 paire pour le versement entier) selon la présence de payout.details.
    """
    if payout.details is not None:
        return _generate_detailed_payout_entries(payout, config)
    return _generate_aggregated_payout_entries(payout, config)


def _generate_aggregated_payout_entries(
    payout: PayoutSummary, config: AppConfig
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Mode agrégé : 1 paire d'écritures pour le versement entier (logique existante)."""
    if payout.psp_type is None:
        anomaly = Anomaly(
            type="mixed_psp_payout",
            severity="warning",
            reference=payout.payout_reference or "",
            channel=payout.channel,
            detail=f"Payout {payout.payout_reference} contient des PSP hétérogènes — écriture de reversement manuelle requise",
            expected_value=None,
            actual_value=None,
        )
        return [], [anomaly]

    total = round(payout.total_amount, 2)
    if total == 0.0:
        return [], []

    psp_account = config.psp[payout.psp_type].compte
    transit_account = config.transit
    date_str = payout.payout_date.strftime("%Y-%m-%d")
    label = f"Reversement {payout.psp_type} {date_str}"
    ref = payout.payout_reference or f"PAYOUT-{date_str}"

    entries = [
        AccountingEntry(
            date=payout.payout_date,
            journal=JOURNAL_REGLEMENT,
            account=transit_account,
            label=label,
            debit=total if total > 0 else 0.0,
            credit=abs(total) if total < 0 else 0.0,
            piece_number=ref,
            lettrage=ref,
            channel=payout.channel,
            entry_type="payout",
        ),
        AccountingEntry(
            date=payout.payout_date,
            journal=JOURNAL_REGLEMENT,
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


def _generate_detailed_payout_entries(
    payout: PayoutSummary, config: AppConfig
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Mode détaillé : 1 paire d'écritures par commande (PayoutDetail)."""
    entries: list[AccountingEntry] = []
    anomalies: list[Anomaly] = []
    transit_account = config.transit

    for detail in payout.details:  # type: ignore[union-attr]
        net = round(detail.net, 2)
        if net == 0.0:
            logger.debug("PayoutDetail %s ignoré : net == 0", detail.order_reference)
            continue

        psp_type = detail.payment_method or payout.psp_type

        if psp_type is None:
            logger.debug("PayoutDetail %s ignoré : PSP inconnu", detail.order_reference)
            anomalies.append(
                Anomaly(
                    type="unknown_psp_detail",
                    severity="warning",
                    reference=detail.order_reference,
                    channel=payout.channel,
                    detail=f"PayoutDetail {detail.order_reference} sans payment_method ni psp_type — ligne ignorée",
                    expected_value=None,
                    actual_value=None,
                )
            )
            continue

        psp_account = config.psp[psp_type].compte
        label = f"Reversement {psp_type} {detail.order_reference}"

        pair = [
            AccountingEntry(
                date=payout.payout_date,
                journal=JOURNAL_REGLEMENT,
                account=transit_account,
                label=label,
                debit=net if net > 0 else 0.0,
                credit=abs(net) if net < 0 else 0.0,
                piece_number=detail.order_reference,
                lettrage=detail.order_reference,
                channel=payout.channel,
                entry_type="payout",
            ),
            AccountingEntry(
                date=payout.payout_date,
                journal=JOURNAL_REGLEMENT,
                account=psp_account,
                label=label,
                debit=abs(net) if net < 0 else 0.0,
                credit=net if net > 0 else 0.0,
                piece_number=detail.order_reference,
                lettrage=detail.order_reference,
                channel=payout.channel,
                entry_type="payout",
            ),
        ]

        verify_balance(pair)
        entries.extend(pair)

    return entries, anomalies
