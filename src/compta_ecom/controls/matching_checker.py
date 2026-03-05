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
        channel_metadata: dict[str, dict] | None = None,
    ) -> list[Anomaly]:
        """Vérifie la cohérence montant, couverture payout et matching refund."""
        if len(transactions) == 0:
            return []

        today = _today or datetime.date.today()
        anomalies: list[Anomaly] = []
        pending_manomano_refs: list[str] = []
        pending_manomano_amounts: list[float] = []
        overdue_manomano_refs: list[str] = []
        overdue_manomano_amounts: list[float] = []
        prior_period_manomano_refund_refs: list[str] = []
        prior_period_manomano_refund_amounts: list[float] = []

        # Track missing_payout per channel for LM/Decathlon summary
        missing_payout_by_channel: dict[str, list[NormalizedTransaction]] = {}

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
                            pending_manomano_amounts.append(tx.amount_ttc)
                            continue
                        elif tx.type == "refund":
                            # Refunds for old periods are normal — not overdue
                            prior_period_manomano_refund_refs.append(tx.reference)
                            prior_period_manomano_refund_amounts.append(tx.amount_ttc)
                            continue
                        else:
                            overdue_manomano_refs.append(tx.reference)
                            overdue_manomano_amounts.append(tx.amount_ttc)
                            continue

            payout_anomalies = MatchingChecker._check_payout_coverage(tx)
            anomalies.extend(payout_anomalies)

            # Track missing_payout transactions for all channels summary
            if payout_anomalies:
                if tx.channel not in missing_payout_by_channel:
                    missing_payout_by_channel[tx.channel] = []
                missing_payout_by_channel[tx.channel].append(tx)

        if pending_manomano_refs:
            count = len(pending_manomano_refs)
            total_pending = round(sum(pending_manomano_amounts), 2)
            anomalies.append(
                Anomaly(
                    type="pending_manomano_payout",
                    severity="info",
                    reference="",
                    channel="manomano",
                    detail=(
                        f"Les reversements de {count} commande{'s' if count > 1 else ''} "
                        f"ManoMano du mois en cours ({total_pending}EUR TTC au total) "
                        f"seront reversés en début de mois prochain. "
                        f"Références : {', '.join(pending_manomano_refs)}"
                    ),
                    expected_value=None,
                    actual_value=", ".join(pending_manomano_refs),
                )
            )

        if overdue_manomano_refs:
            count = len(overdue_manomano_refs)
            total_overdue = round(sum(overdue_manomano_amounts), 2)
            anomalies.append(
                Anomaly(
                    type="overdue_manomano_payout",
                    severity="warning",
                    reference="",
                    channel="manomano",
                    detail=(
                        f"{count} commande{'s' if count > 1 else ''} ManoMano "
                        f"de mois antérieurs sans reversement ({total_overdue}EUR TTC au total) — "
                        f"vérification nécessaire auprès de ManoMano. "
                        f"Références : {', '.join(overdue_manomano_refs)}"
                    ),
                    expected_value="reversement reçu",
                    actual_value=", ".join(overdue_manomano_refs),
                )
            )

        if prior_period_manomano_refund_refs:
            count = len(prior_period_manomano_refund_refs)
            total_refund = round(sum(abs(a) for a in prior_period_manomano_refund_amounts), 2)
            anomalies.append(
                Anomaly(
                    type="prior_period_manomano_refund",
                    severity="info",
                    reference="",
                    channel="manomano",
                    detail=(
                        f"{count} remboursement{'s' if count > 1 else ''} "
                        f"ManoMano concern{'ent' if count > 1 else 'e'} des commandes "
                        f"de périodes antérieures ({total_refund}EUR TTC au total) — "
                        f"les commandes d'origine ne figurent pas dans l'export du mois en cours. "
                        f"Références : {', '.join(prior_period_manomano_refund_refs)}"
                    ),
                    expected_value=None,
                    actual_value=", ".join(prior_period_manomano_refund_refs),
                )
            )

        # --- Missing payout summary for ALL channels ---
        for chan, mp_txs in missing_payout_by_channel.items():
            count = len(mp_txs)
            total_ttc = round(sum(tx.amount_ttc for tx in mp_txs), 2)
            ch_display = channel_display_name(chan)
            summary_parts = [
                f"{count} reversement{'s' if count > 1 else ''} manquant{'s' if count > 1 else ''} "
                f"pour un total de {total_ttc}EUR"
            ]

            solde = None
            if channel_metadata and chan in channel_metadata:
                solde = channel_metadata[chan].get("solde")

            if solde is not None:
                solde_val = float(solde)
                ecart = abs(total_ttc - solde_val)
                if ecart <= 1.0:
                    summary_parts.append("montant confirme par le fichier source")
                else:
                    summary_parts.append(
                        f"ecart de {round(ecart, 2)}EUR entre le total en attente et le solde fichier source"
                    )

            # Collect references of pending transactions for actual_value
            mp_refs = ", ".join(tx.reference for tx in mp_txs if tx.reference)
            anomalies.append(
                Anomaly(
                    type="missing_payout_summary",
                    severity="info",
                    reference="",
                    channel=chan,
                    detail=f"{ch_display} : {' -- '.join(summary_parts)}",
                    expected_value=str(solde) if solde is not None else None,
                    actual_value=mp_refs if mp_refs else None,
                )
            )

            # Solde négatif: specific info anomaly
            if solde is not None and float(solde) < 0:
                anomalies.append(
                    Anomaly(
                        type="negative_solde",
                        severity="info",
                        reference="",
                        channel=chan,
                        detail=(
                            f"Solde negatif ({solde}EUR) chez {ch_display} : "
                            f"situation normale -- le solde negatif reflete des retours en cours "
                            f"de traitement, aucun reversement attendu tant que les ventes "
                            f"n'apurent pas l'avoir"
                        ),
                        expected_value=None,
                        actual_value=None,
                    )
                )

        anomalies.extend(MatchingChecker._check_refund_matching(transactions, _today=today))
        anomalies.extend(
            MatchingChecker._check_payment_delay(transactions, channel_metadata=channel_metadata)
        )

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
            tx_type_label = "vente" if transaction.type == "sale" else "remboursement"
            channel_display = channel_display_name(transaction.channel)
            return [
                Anomaly(
                    type="amount_mismatch",
                    severity="warning",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=(
                        f"{tx_type_label.capitalize()} ({channel_display}, "
                        f"{transaction.date.isoformat()}) : écart de {round(diff, 2)}EUR "
                        f"entre le montant TTC ({transaction.amount_ttc}EUR) "
                        f"et la somme commission ({transaction.commission_ttc}EUR) "
                        f"+ net versé ({transaction.net_amount}EUR) "
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
            tx_type_label = "vente" if transaction.type == "sale" else "remboursement"
            return [
                Anomaly(
                    type="missing_payout",
                    severity="info",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=(
                        f"{tx_type_label.capitalize()} du {transaction.date.isoformat()} "
                        f"({transaction.amount_ttc}EUR TTC) — "
                        f"versement en attente chez {channel_display}"
                    ),
                    expected_value="date de versement",
                    actual_value=f"{transaction.amount_ttc}EUR TTC, {tx_type_label} du {transaction.date.isoformat()}",
                )
            ]
        return []

    @staticmethod
    def _check_refund_matching(
        transactions: list[NormalizedTransaction],
        *,
        _today: datetime.date | None = None,
    ) -> list[Anomaly]:
        """Vérifie que chaque refund a une vente correspondante (référence exacte)."""
        today = _today or datetime.date.today()
        current_year_2digit = today.year % 100  # e.g. 26 for 2026

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
        # LM prior-period refunds (year-based) — keyed by year
        lm_prior_period_refunds: dict[int, list[NormalizedTransaction]] = {}

        for tx in transactions:
            if tx.special_type == "orphan_settlement":
                continue
            if tx.type == "refund" and tx.reference not in sale_references:
                # ManoMano refunds are handled by the YYMM-specific logic
                # in check() — skip here to avoid duplicate anomalies
                if tx.channel == "manomano":
                    continue
                # Shopify refunds are handled by the parser's own matching logic
                # (prior-period detection in _match_and_build) — skip to avoid duplicates
                if tx.channel == "shopify":
                    continue
                # Leroy Merlin: year-based prior-period detection
                if tx.channel == "leroy_merlin":
                    lm_match = re.match(r"^001-(\d{2})", tx.reference)
                    if lm_match:
                        ref_year = int(lm_match.group(1))
                        if ref_year < current_year_2digit:
                            if ref_year not in lm_prior_period_refunds:
                                lm_prior_period_refunds[ref_year] = []
                            lm_prior_period_refunds[ref_year].append(tx)
                            continue
                    # If no match or current year → fall through to orphan_refund below

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
                    ch_display = channel_display_name(tx.channel)
                    anomalies.append(
                        Anomaly(
                            type="orphan_refund",
                            severity="warning",
                            reference=tx.reference,
                            channel=tx.channel,
                            detail=(
                                f"Remboursement ({ch_display}, "
                                f"{tx.date.isoformat()}, {tx.amount_ttc}EUR TTC) "
                                f"sans vente d'origine trouvée dans la période exportée — "
                                f"la commande remboursée est peut-être antérieure à l'export"
                            ),
                            expected_value="vente correspondante",
                            actual_value=f"{tx.amount_ttc}EUR TTC, remboursement du {tx.date.isoformat()}",
                        )
                    )

        # Emit a single summary anomaly for prior-period refunds (generic)
        if prior_period_refunds:
            def _ref_num(r: str) -> int:
                m = re.search(r"(\d+)", r)
                return int(m.group(1)) if m else 0

            refs_str = ", ".join(
                sorted([tx.reference for tx in prior_period_refunds], key=_ref_num)
            )
            count = len(prior_period_refunds)
            total_refund = round(sum(abs(tx.amount_ttc) for tx in prior_period_refunds), 2)
            ch_display = channel_display_name(prior_period_refunds[0].channel)
            anomalies.append(
                Anomaly(
                    type="prior_period_refund",
                    severity="info",
                    reference="",
                    channel=prior_period_refunds[0].channel,
                    detail=(
                        f"{count} remboursement{'s' if count > 1 else ''} {ch_display} "
                        f"concern{'ent' if count > 1 else 'e'} une période antérieure "
                        f"({total_refund}EUR TTC au total) — les commandes d'origine ne "
                        f"figurent pas dans l'export. Références : {refs_str}"
                    ),
                    expected_value="ventes correspondantes dans la période exportée",
                    actual_value=refs_str,
                )
            )

        # Emit LM prior-period refund summaries (year-based)
        for year_2d in sorted(lm_prior_period_refunds):
            txs = lm_prior_period_refunds[year_2d]
            count = len(txs)
            total_refund = round(sum(abs(tx.amount_ttc) for tx in txs), 2)
            full_year = 2000 + year_2d
            refs_str = ", ".join(sorted(tx.reference for tx in txs))
            anomalies.append(
                Anomaly(
                    type="prior_period_lm_refund",
                    severity="info",
                    reference="",
                    channel="leroy_merlin",
                    detail=(
                        f"{count} remboursement{'s' if count > 1 else ''} Leroy Merlin "
                        f"concern{'ent' if count > 1 else 'e'} des commandes de l'annee "
                        f"precedente ({full_year}) -- {total_refund}EUR TTC au total. "
                        f"References : {refs_str}"
                    ),
                    expected_value=None,
                    actual_value=refs_str,
                )
            )

        return anomalies

    @staticmethod
    def _check_payment_delay(
        transactions: list[NormalizedTransaction],
        *,
        channel_metadata: dict[str, dict] | None = None,
    ) -> list[Anomaly]:
        """Signale les factures marketplace sans règlement depuis >= 20 jours.

        Pour LM/Decathlon, si le Solde du fichier source confirme le montant
        en attente (tolerance <= 1EUR) ou est negatif, on ne genere PAS
        d'anomalie payment_delay.
        """
        marketplace_channels = {"decathlon", "leroy_merlin"}
        today = datetime.date.today()
        delay_threshold = 20

        # Pre-compute per-channel: sum of amount_ttc for unpaid sales
        unpaid_sum_by_channel: dict[str, float] = {}
        for tx in transactions:
            if tx.special_type is not None:
                continue
            if tx.type != "sale" or tx.channel not in marketplace_channels:
                continue
            if tx.payout_date is not None:
                continue
            unpaid_sum_by_channel[tx.channel] = unpaid_sum_by_channel.get(tx.channel, 0.0) + tx.amount_ttc

        # Determine which channels should be suppressed
        suppressed_channels: set[str] = set()
        if channel_metadata:
            for chan in marketplace_channels:
                if chan in channel_metadata:
                    solde = channel_metadata[chan].get("solde")
                    if solde is not None:
                        solde_val = float(solde)
                        if solde_val < 0:
                            # Negative solde -> suppress payment_delay
                            suppressed_channels.add(chan)
                        else:
                            unpaid_total = round(unpaid_sum_by_channel.get(chan, 0.0), 2)
                            if abs(unpaid_total - solde_val) <= 1.0:
                                suppressed_channels.add(chan)

        anomalies: list[Anomaly] = []
        for tx in transactions:
            if tx.special_type is not None:
                continue
            if tx.type != "sale" or tx.channel not in marketplace_channels:
                continue
            if tx.payout_date is not None:
                continue
            if tx.channel in suppressed_channels:
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
