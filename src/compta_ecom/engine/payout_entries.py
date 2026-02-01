"""Génération des écritures de reversement PSP (58000000 → PSP 511)."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import JOURNAL_REGLEMENT, verify_balance
from compta_ecom.models import AccountingEntry, Anomaly, PayoutSummary


def generate_payout_entries(
    payout: PayoutSummary, config: AppConfig
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Génère l'écriture de reversement pour un PayoutSummary."""
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
