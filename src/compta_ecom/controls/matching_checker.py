"""Contrôles de matching financier post-génération."""

from __future__ import annotations

import datetime
import logging
import re

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import Anomaly, NormalizedTransaction, channel_display_name

logger = logging.getLogger(__name__)


class MatchingChecker:
    """Contrôles de matching financier post-génération."""

    @staticmethod
    def check(
        transactions: list[NormalizedTransaction],
        config: AppConfig,
        *,
        _today: datetime.date | None = None,
    ) -> list[Anomaly]:
        """Vérifie la cohérence montant, couverture payout et matching refund."""
        if len(transactions) == 0:
            return []

        today = _today or datetime.date.today()
        anomalies: list[Anomaly] = []
        pending_manomano_refs: list[str] = []
        overdue_manomano_refs: list[str] = []
        prior_period_manomano_refund_refs: list[str] = []

        for tx in transactions:
            if tx.special_type is not None:
                continue
            anomalies.extend(MatchingChecker._check_amount_coherence(tx, config))

            # ManoMano orders without payout: classify by month
            if (
                tx.channel == "manomano"
                and tx.payout_date is None
                and abs(tx.amount_ttc) >= 0.01
            ):
                ref_match = re.match(r"^M?(\d{4})", tx.reference)
                if ref_match:
                    yymm = ref_match.group(1)
                    ref_year = 2000 + int(yymm[:2])
                    ref_month = int(yymm[2:4])
                    if 1 <= ref_month <= 12:
                        if (ref_year, ref_month) >= (today.year, today.month):
                            pending_manomano_refs.append(tx.reference)
                            continue
                        elif tx.type == "refund":
                            # Refunds for old periods are normal — not overdue
                            prior_period_manomano_refund_refs.append(tx.reference)
                            continue
                        else:
                            overdue_manomano_refs.append(tx.reference)
                            continue

            anomalies.extend(MatchingChecker._check_payout_coverage(tx))

        if pending_manomano_refs:
            count = len(pending_manomano_refs)
            anomalies.append(
                Anomaly(
                    type="pending_manomano_payout",
                    severity="info",
                    reference="",
                    channel="manomano",
                    detail=(
                        f"Les reversements de {count} commande{'s' if count > 1 else ''} "
                        f"du mois en cours seront reversés en début de mois prochain"
                    ),
                    expected_value=None,
                    actual_value=", ".join(pending_manomano_refs),
                )
            )

        if overdue_manomano_refs:
            count = len(overdue_manomano_refs)
            anomalies.append(
                Anomaly(
                    type="overdue_manomano_payout",
                    severity="warning",
                    reference="",
                    channel="manomano",
                    detail=(
                        f"{count} commande{'s' if count > 1 else ''} "
                        f"de mois antérieurs sans reversement — vérification nécessaire"
                    ),
                    expected_value=None,
                    actual_value=", ".join(overdue_manomano_refs),
                )
            )

        if prior_period_manomano_refund_refs:
            count = len(prior_period_manomano_refund_refs)
            anomalies.append(
                Anomaly(
                    type="prior_period_manomano_refund",
                    severity="info",
                    reference="",
                    channel="manomano",
                    detail=(
                        f"{count} remboursement{'s' if count > 1 else ''} "
                        f"ManoMano concernent des commandes de périodes antérieures"
                    ),
                    expected_value=None,
                    actual_value=", ".join(prior_period_manomano_refund_refs),
                )
            )

        anomalies.extend(MatchingChecker._check_refund_matching(transactions))
        anomalies.extend(MatchingChecker._check_payment_delay(transactions))

        return anomalies

    @staticmethod
    def _check_amount_coherence(
        transaction: NormalizedTransaction, config: AppConfig
    ) -> list[Anomaly]:
        """Vérifie amount_ttc ≈ commission_ttc + net_amount (deux formules de signe)."""
        if (
            transaction.commission_ttc == 0.0
            and transaction.net_amount == 0.0
            and transaction.amount_ttc == 0.0
        ):
            return []

        # Formula 1: |commission + net| — works when signs are consistent
        # (e.g. Shopify refund commission kept: +3.50 + -120 = -116.50)
        expected_sum = abs(round(transaction.commission_ttc + transaction.net_amount, 2))
        diff_sum = round(abs(transaction.amount_ttc - expected_sum), 2)

        # Formula 2: |commission| + |net| — works when commission sign is
        # flipped (e.g. ManoMano sale: commission=-15.43, net=103.27)
        expected_parts = round(abs(transaction.commission_ttc) + abs(transaction.net_amount), 2)
        diff_parts = round(abs(abs(transaction.amount_ttc) - expected_parts), 2)

        if diff_sum <= diff_parts:
            expected = expected_sum
            diff = diff_sum
        else:
            expected = expected_parts
            diff = diff_parts

        if diff > config.matching_tolerance:
            return [
                Anomaly(
                    type="amount_mismatch",
                    severity="warning",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=(
                        f"Écart de {round(diff, 2)}€ entre le montant TTC ({transaction.amount_ttc}€) "
                        f"et la somme commission ({transaction.commission_ttc}€) "
                        f"+ net versé ({transaction.net_amount}€) "
                        f"— vérifier la répartition"
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
        if abs(transaction.amount_ttc) < 0.01:
            return []
        if transaction.payout_date is None:
            channel_display = channel_display_name(transaction.channel)
            return [
                Anomaly(
                    type="missing_payout",
                    severity="info",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=f"Cette transaction n'a pas encore de date de versement — le virement bancaire est probablement en attente chez {channel_display}",
                    expected_value="date de versement",
                    actual_value="None",
                )
            ]
        return []

    @staticmethod
    def _check_refund_matching(
        transactions: list[NormalizedTransaction],
    ) -> list[Anomaly]:
        """Vérifie que chaque refund a une vente correspondante (référence exacte)."""
        sale_references: set[str] = set()
        for tx in transactions:
            if tx.type == "sale":
                sale_references.add(tx.reference)

        # Determine the first sale reference number for prior-period detection
        first_sale_num: int | None = None
        if sale_references:
            sale_nums = []
            for ref in sale_references:
                m = re.search(r"(\d+)", ref)
                if m:
                    sale_nums.append(int(m.group(1)))
            if sale_nums:
                first_sale_num = min(sale_nums)

        anomalies: list[Anomaly] = []
        prior_period_refunds: list[NormalizedTransaction] = []

        for tx in transactions:
            if tx.special_type == "orphan_settlement":
                continue
            if tx.type == "refund" and tx.reference not in sale_references:
                # ManoMano refunds are handled by the YYMM-specific logic
                # in check() — skip here to avoid duplicate anomalies
                if tx.channel == "manomano":
                    continue

                # Classify: prior period vs true orphan
                ref_m = re.search(r"(\d+)", tx.reference)
                ref_num = int(ref_m.group(1)) if ref_m else None
                is_prior = (
                    first_sale_num is not None
                    and ref_num is not None
                    and ref_num < first_sale_num
                )

                if is_prior:
                    prior_period_refunds.append(tx)
                else:
                    anomalies.append(
                        Anomaly(
                            type="orphan_refund",
                            severity="warning",
                            reference=tx.reference,
                            channel=tx.channel,
                            detail=(
                                f"Remboursement pour la commande {tx.reference} mais aucune vente "
                                f"d'origine trouvée — le remboursement est peut-être antérieur à la période exportée"
                            ),
                            expected_value="vente correspondante",
                            actual_value="aucune",
                        )
                    )

        # Emit a single summary anomaly for prior-period refunds
        if prior_period_refunds:
            def _ref_num(r: str) -> int:
                m = re.search(r"(\d+)", r)
                return int(m.group(1)) if m else 0

            refs_str = ", ".join(
                sorted([tx.reference for tx in prior_period_refunds], key=_ref_num)
            )
            count = len(prior_period_refunds)
            anomalies.append(
                Anomaly(
                    type="prior_period_refund",
                    severity="info",
                    reference="",
                    channel=prior_period_refunds[0].channel,
                    detail=f"{count} remboursement{'s' if count > 1 else ''} concernent une période antérieure",
                    expected_value=None,
                    actual_value=refs_str,
                )
            )

        return anomalies

    @staticmethod
    def _check_payment_delay(
        transactions: list[NormalizedTransaction],
    ) -> list[Anomaly]:
        """Signale les factures marketplace sans règlement depuis >= 20 jours."""
        marketplace_channels = {"decathlon", "leroy_merlin"}
        today = datetime.date.today()
        delay_threshold = 20

        anomalies: list[Anomaly] = []
        for tx in transactions:
            if tx.special_type is not None:
                continue
            if tx.type != "sale" or tx.channel not in marketplace_channels:
                continue
            if tx.payout_date is not None:
                continue
            days_elapsed = (today - tx.date).days
            if days_elapsed >= delay_threshold:
                anomalies.append(
                    Anomaly(
                        type="payment_delay",
                        severity="warning",
                        reference=tx.reference,
                        channel=tx.channel,
                        detail=(
                            f"Commande du {tx.date.isoformat()} non réglée "
                            f"depuis {days_elapsed} jours — retard de paiement à surveiller"
                        ),
                        expected_value=f"<= {delay_threshold} jours",
                        actual_value=f"{days_elapsed} jours",
                    )
                )

        return anomalies
