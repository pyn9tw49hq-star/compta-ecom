"""Conversion des dataclasses métier vers les structures JSON de l'API."""

from __future__ import annotations

from compta_ecom.models import AccountingEntry, Anomaly, NormalizedTransaction


def serialize_entry(entry: AccountingEntry) -> dict[str, object]:
    """Sérialise une AccountingEntry vers le format JSON de l'API."""
    return {
        "date": entry.date.isoformat(),
        "journal": entry.journal,
        "compte": entry.account,
        "libelle": entry.label,
        "debit": entry.debit,
        "credit": entry.credit,
        "piece": entry.piece_number,
        "lettrage": entry.lettrage,
        "canal": entry.channel,
        "type_ecriture": entry.entry_type,
    }


def serialize_anomaly(anomaly: Anomaly) -> dict[str, object]:
    """Sérialise une Anomaly vers le format JSON de l'API."""
    return {
        "type": anomaly.type,
        "severity": anomaly.severity,
        "canal": anomaly.channel,
        "reference": anomaly.reference,
        "detail": anomaly.detail,
        "expected_value": anomaly.expected_value,
        "actual_value": anomaly.actual_value,
    }


def serialize_transaction(tx: NormalizedTransaction) -> dict[str, object]:
    """Sérialise une NormalizedTransaction vers le format JSON léger de l'API."""
    return {
        "reference": tx.reference,
        "channel": tx.channel,
        "date": tx.date.isoformat(),
        "type": tx.type,
        "amount_ht": tx.amount_ht,
        "amount_tva": tx.amount_tva,
        "amount_ttc": tx.amount_ttc,
        "shipping_ht": tx.shipping_ht,
        "shipping_tva": tx.shipping_tva,
        "tva_rate": tx.tva_rate,
        "country_code": tx.country_code,
        "commission_ttc": tx.commission_ttc,
        "commission_ht": tx.commission_ht,
        "special_type": tx.special_type,
    }


def serialize_response(
    entries: list[AccountingEntry],
    anomalies: list[Anomaly],
    summary: dict[str, dict[str, int] | dict[str, float]],
    transactions: list[NormalizedTransaction] | None = None,
    country_names: dict[str, str] | None = None,
) -> dict[str, object]:
    """Assemble la réponse complète ProcessResponse."""
    result: dict[str, object] = {
        "entries": [serialize_entry(e) for e in entries],
        "anomalies": [serialize_anomaly(a) for a in anomalies],
        "summary": summary,
    }
    if transactions is not None:
        result["transactions"] = [serialize_transaction(t) for t in transactions]
    if country_names is not None:
        result["country_names"] = country_names
    return result
