"""Modèles de données métier et hiérarchie d'exceptions."""

from __future__ import annotations

import datetime
from dataclasses import dataclass


# --- Exceptions métier ---


class ComptaEcomError(Exception):
    """Erreur de base pour l'application compta-ecom."""


class ConfigError(ComptaEcomError):
    """YAML malformé, clé manquante, valeur invalide."""


class ParseError(ComptaEcomError):
    """Colonne CSV manquante, fichier illisible."""


class BalanceError(ComptaEcomError):
    """Déséquilibre débit/crédit (bug moteur)."""


class NoResultError(ComptaEcomError):
    """Aucun canal n'a produit de résultat."""


# --- Dataclasses métier (frozen) ---


@dataclass(frozen=True)
class NormalizedTransaction:
    """Transaction normalisée issue du parsing CSV."""

    reference: str
    channel: str
    date: datetime.date
    type: str
    amount_ht: float
    amount_tva: float
    amount_ttc: float
    shipping_ht: float
    shipping_tva: float
    tva_rate: float
    country_code: str
    commission_ttc: float
    commission_ht: float | None  # None pour les lignes spéciales ManoMano (ADJUSTMENT, ECO_CONTRIBUTION, SUBSCRIPTION, REFUND_PENALTY). Le code en aval (settlement_entries) ne l'accède pas directement grâce au guard payment_method=None.
    net_amount: float
    payout_date: datetime.date | None
    payout_reference: str | None
    payment_method: str | None
    special_type: str | None


@dataclass(frozen=True)
class AccountingEntry:
    """Unité atomique de l'export Excel."""

    date: datetime.date
    journal: str
    account: str
    label: str
    debit: float
    credit: float
    piece_number: str
    lettrage: str
    channel: str
    entry_type: str


@dataclass(frozen=True)
class Anomaly:
    """Anomalie détectée lors du traitement."""

    type: str
    severity: str
    reference: str
    channel: str
    detail: str
    expected_value: str | None
    actual_value: str | None


@dataclass(frozen=True)
class PayoutSummary:
    """Résumé d'un versement PSP."""

    payout_date: datetime.date
    channel: str
    total_amount: float
    charges: float
    refunds: float
    fees: float
    transaction_references: list[str]
    psp_type: str | None
    payout_reference: str | None


@dataclass(frozen=True)
class ParseResult:
    """Résultat du parsing d'un canal.

    Convention : les champs ``list[]`` ne doivent pas être mutés après
    construction. L'immutabilité est assurée par convention, pas par
    contrainte technique (les listes restent des ``list`` et non des
    ``tuple`` pour des raisons de compatibilité avec pandas).
    """

    transactions: list[NormalizedTransaction]
    payouts: list[PayoutSummary]
    anomalies: list[Anomaly]
    channel: str
