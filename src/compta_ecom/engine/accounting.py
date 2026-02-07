"""Orchestrateur des écritures comptables."""

from __future__ import annotations

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine import marketplace_entries
from compta_ecom.engine.accounts import normalize_lettrage
from compta_ecom.engine.marketplace_payout_entries import (
    generate_marketplace_payout,
    generate_marketplace_payout_from_summary,
)
from compta_ecom.engine.payout_entries import generate_payout_entries
from compta_ecom.engine.sale_entries import generate_sale_entries
from compta_ecom.engine.settlement_entries import generate_settlement_entries
from compta_ecom.models import AccountingEntry, Anomaly, BalanceError, NormalizedTransaction, PayoutSummary


def generate_all_payout_entries(
    payouts: list[PayoutSummary], config: AppConfig
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Génère les écritures de reversement pour tous les PayoutSummary."""
    entries: list[AccountingEntry] = []
    anomalies: list[Anomaly] = []
    for payout in payouts:
        payout_entries, payout_anomalies = generate_payout_entries(payout, config)
        entries.extend(payout_entries)
        anomalies.extend(payout_anomalies)
    return entries, anomalies


def generate_entries(
    transactions: list[NormalizedTransaction],
    payouts: list[PayoutSummary],
    config: AppConfig,
) -> tuple[list[AccountingEntry], list[Anomaly]]:
    """Orchestre la génération des écritures (vente + commission/settlement + reversement)."""
    entries: list[AccountingEntry] = []
    anomalies: list[Anomaly] = []

    for transaction in transactions:
        if transaction.special_type is not None:
            if transaction.special_type in ("payout_detail_refund", "orphan_settlement"):
                entries.extend(generate_settlement_entries(transaction, config))
            elif transaction.channel in config.fournisseurs:
                entries.extend(generate_marketplace_payout(transaction, config))
            continue
        try:
            entries.extend(generate_sale_entries(transaction, config))
        except BalanceError as exc:
            anomalies.append(
                Anomaly(
                    type="balance_error",
                    severity="error",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=str(exc),
                    expected_value=None,
                    actual_value=None,
                )
            )
            continue
        if transaction.channel in config.fournisseurs:
            entries.extend(
                marketplace_entries.generate_marketplace_commission(transaction, config)
            )
            if transaction.channel != "decathlon":
                entries.extend(generate_marketplace_payout(transaction, config))
        else:
            entries.extend(generate_settlement_entries(transaction, config))

    for payout in payouts:
        if payout.channel in config.fournisseurs:
            # Marketplace: générer les écritures de payout agrégé (580 ↔ 411)
            entries.extend(generate_marketplace_payout_from_summary(payout, config))
        else:
            # PSP: générer les écritures standard
            payout_entries_list, payout_anomalies = generate_payout_entries(payout, config)
            entries.extend(payout_entries_list)
            anomalies.extend(payout_anomalies)

    entries = normalize_lettrage(entries)
    return entries, anomalies
