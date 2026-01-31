"""Contrôles de matching financier post-génération."""

from __future__ import annotations

import logging

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import Anomaly, NormalizedTransaction

logger = logging.getLogger(__name__)


class MatchingChecker:
    """Contrôles de matching financier post-génération."""

    @staticmethod
    def check(
        transactions: list[NormalizedTransaction], config: AppConfig
    ) -> list[Anomaly]:
        """Vérifie la cohérence montant, couverture payout et matching refund."""
        if len(transactions) == 0:
            return []

        anomalies: list[Anomaly] = []

        for tx in transactions:
            if tx.special_type is not None:
                continue
            anomalies.extend(MatchingChecker._check_amount_coherence(tx, config))
            anomalies.extend(MatchingChecker._check_payout_coverage(tx))

        anomalies.extend(MatchingChecker._check_refund_matching(transactions))

        return anomalies

    @staticmethod
    def _check_amount_coherence(
        transaction: NormalizedTransaction, config: AppConfig
    ) -> list[Anomaly]:
        """Vérifie amount_ttc ≈ abs(commission_ttc + net_amount)."""
        if (
            transaction.commission_ttc == 0.0
            and transaction.net_amount == 0.0
            and transaction.amount_ttc == 0.0
        ):
            return []

        expected = abs(round(transaction.commission_ttc + transaction.net_amount, 2))
        diff = round(abs(transaction.amount_ttc - expected), 2)

        if diff > config.matching_tolerance:
            return [
                Anomaly(
                    type="amount_mismatch",
                    severity="warning",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=(
                        f"Montant TTC ({transaction.amount_ttc}€) ne correspond pas "
                        f"à la décomposition commission ({transaction.commission_ttc}€) "
                        f"+ net ({transaction.net_amount}€) = {expected}€ "
                        f"— écart de {round(diff, 2)}€"
                    ),
                    expected_value=str(expected),
                    actual_value=str(transaction.amount_ttc),
                )
            ]

        return []

    @staticmethod
    def _check_payout_coverage(
        transaction: NormalizedTransaction,
    ) -> list[Anomaly]:
        """Signale les transactions sans payout_date (severity=info)."""
        if transaction.payout_date is None:
            return [
                Anomaly(
                    type="missing_payout",
                    severity="info",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail="Transaction sans date de reversement — payout en attente",
                    expected_value="date de payout",
                    actual_value="None",
                )
            ]
        return []

    @staticmethod
    def _check_refund_matching(
        transactions: list[NormalizedTransaction],
    ) -> list[Anomaly]:
        """Vérifie que chaque refund a une vente correspondante (référence exacte)."""
        # Matching naïf par référence exacte — les 3 parsers MVP (Shopify, ManoMano, Mirakl)
        # utilisent la même référence pour sale et refund. Si un futur canal post-MVP utilise
        # des références dérivées (ex: suffixe -R), adapter ce contrôle.
        sale_references: set[str] = set()
        for tx in transactions:
            if tx.type == "sale":
                sale_references.add(tx.reference)

        anomalies: list[Anomaly] = []
        for tx in transactions:
            if tx.type == "refund" and tx.reference not in sale_references:
                anomalies.append(
                    Anomaly(
                        type="orphan_refund",
                        severity="warning",
                        reference=tx.reference,
                        channel=tx.channel,
                        detail=(
                            f"Remboursement sans vente correspondante "
                            f"(référence {tx.reference} absente des ventes)"
                        ),
                        expected_value="vente correspondante",
                        actual_value="aucune",
                    )
                )

        return anomalies
