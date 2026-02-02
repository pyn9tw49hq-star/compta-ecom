"""Contrôle de lettrage soldé sur le compte 511 (PSP)."""

from __future__ import annotations

import logging
from collections import defaultdict

from compta_ecom.models import AccountingEntry, Anomaly

logger = logging.getLogger(__name__)

BALANCE_TOLERANCE = 0.01  # euros


class LettrageChecker:
    """Vérifie que chaque groupe de lettrage 511 est soldé (∑ débits == ∑ crédits)."""

    @staticmethod
    def check(entries: list[AccountingEntry]) -> list[Anomaly]:
        """Filtre les écritures 511 avec lettrage non vide, groupe par lettrage, vérifie l'équilibre."""
        groups: dict[str, list[AccountingEntry]] = defaultdict(list)

        for entry in entries:
            if entry.account.startswith("511") and entry.lettrage:
                groups[entry.lettrage].append(entry)

        anomalies: list[Anomaly] = []

        for lettrage, group in groups.items():
            total_debit = round(sum(e.debit for e in group), 2)
            total_credit = round(sum(e.credit for e in group), 2)
            diff = round(abs(total_debit - total_credit), 2)

            if diff > BALANCE_TOLERANCE:
                anomalies.append(
                    Anomaly(
                        type="lettrage_511_unbalanced",
                        severity="error",
                        reference=lettrage,
                        channel=group[0].channel,
                        detail=(
                            f"Groupe de lettrage 511 '{lettrage}' déséquilibré : "
                            f"débits={total_debit}€, crédits={total_credit}€, "
                            f"écart={diff}€"
                        ),
                        expected_value=str(total_debit),
                        actual_value=str(total_credit),
                    )
                )

        return anomalies
