"""Contrôle de cohérence TVA sur les transactions normalisées."""

from __future__ import annotations

import logging

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import Anomaly, NormalizedTransaction

logger = logging.getLogger(__name__)

RATE_TOLERANCE = 0.1  # points de pourcentage
AMOUNT_TOLERANCE = 0.01  # euros

# commission_ht / commission_ttc : vérification TVA commission hors scope MVP
# cf. Story 2.2 — commission_vat_rate disponible pour extension future


class VatChecker:
    """Contrôle de cohérence TVA sur les transactions normalisées."""

    @staticmethod
    def check(
        transactions: list[NormalizedTransaction], config: AppConfig
    ) -> list[Anomaly]:
        """Vérifie la cohérence TVA de toutes les transactions.

        Exclut les transactions avec special_type is not None.
        Retourne [] si vat_table est vide.
        """
        if len(config.vat_table) == 0:
            logger.warning("Table TVA vide — contrôle TVA désactivé")
            return []

        anomalies: list[Anomaly] = []

        for tx in transactions:
            if tx.special_type is not None:
                continue

            anomalies.extend(VatChecker._check_rate(tx, config))
            anomalies.extend(VatChecker._check_tva_amounts(tx))
            anomalies.extend(VatChecker._check_ttc_coherence(tx))

        return anomalies

    @staticmethod
    def _check_rate(
        transaction: NormalizedTransaction, config: AppConfig
    ) -> list[Anomaly]:
        """Contrôle 1 — taux TVA vs pays."""
        country_code = transaction.country_code

        if country_code not in config.vat_table:
            return [
                Anomaly(
                    type="unknown_country",
                    severity="error",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=f"Pays inconnu (code {country_code}) — ce pays n'est pas dans la table TVA, le taux applicable n'a pas pu être vérifié",
                    expected_value=None,
                    actual_value=str(country_code),
                )
            ]

        raw_rate = config.vat_table[country_code]["rate"]
        expected_rate = float(str(raw_rate))

        if abs(transaction.tva_rate - expected_rate) > RATE_TOLERANCE:
            return [
                Anomaly(
                    type="tva_mismatch",
                    severity="warning",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=f"Taux de TVA incohérent : {transaction.tva_rate}% appliqué au lieu de {expected_rate}% attendu pour ce pays (code {country_code})",
                    expected_value=str(expected_rate),
                    actual_value=str(transaction.tva_rate),
                )
            ]

        return []

    @staticmethod
    def _check_tva_amounts(
        transaction: NormalizedTransaction,
    ) -> list[Anomaly]:
        """Contrôle 2 — montants TVA = HT × taux."""
        expected_product_tva = round(transaction.amount_ht * transaction.tva_rate / 100, 2)
        expected_shipping_tva = round(transaction.shipping_ht * transaction.tva_rate / 100, 2)

        product_mismatch = abs(transaction.amount_tva - expected_product_tva) > AMOUNT_TOLERANCE
        shipping_mismatch = abs(transaction.shipping_tva - expected_shipping_tva) > AMOUNT_TOLERANCE

        if not product_mismatch and not shipping_mismatch:
            return []

        parts: list[str] = []
        expected_parts: list[str] = []
        actual_parts: list[str] = []

        if product_mismatch:
            parts.append(
                f"Montant de TVA produit incorrect : {transaction.amount_tva}€ constaté au lieu de "
                f"{expected_product_tva}€ calculé ({transaction.amount_ht}€ HT × {transaction.tva_rate}%)"
            )
            expected_parts.append(str(expected_product_tva))
            actual_parts.append(str(transaction.amount_tva))

        if shipping_mismatch:
            parts.append(
                f"Montant de TVA port incorrect : {transaction.shipping_tva}€ constaté au lieu de "
                f"{expected_shipping_tva}€ calculé ({transaction.shipping_ht}€ HT × {transaction.tva_rate}%)"
            )
            expected_parts.append(str(expected_shipping_tva))
            actual_parts.append(str(transaction.shipping_tva))

        return [
            Anomaly(
                type="tva_amount_mismatch",
                severity="warning",
                reference=transaction.reference,
                channel=transaction.channel,
                detail=" ; ".join(parts) + " — écart dû à un arrondi ou un taux mixte",
                expected_value=", ".join(expected_parts),
                actual_value=", ".join(actual_parts),
            )
        ]

    @staticmethod
    def _check_ttc_coherence(
        transaction: NormalizedTransaction,
    ) -> list[Anomaly]:
        """Contrôle 3 — TTC = somme composants."""
        expected_ttc = round(
            transaction.amount_ht + transaction.shipping_ht + transaction.amount_tva + transaction.shipping_tva, 2
        )
        diff = abs(transaction.amount_ttc - expected_ttc)

        if diff > AMOUNT_TOLERANCE:
            return [
                Anomaly(
                    type="ttc_coherence_mismatch",
                    severity="warning",
                    reference=transaction.reference,
                    channel=transaction.channel,
                    detail=f"Montant TTC incohérent : {transaction.amount_ttc}€ affiché mais la somme HT + TVA + port donne {expected_ttc}€ (écart de {round(diff, 2)}€)",
                    expected_value=str(expected_ttc),
                    actual_value=str(transaction.amount_ttc),
                )
            ]

        return []
