"""Conversion des dataclasses métier vers les structures JSON de l'API."""

from __future__ import annotations

from compta_ecom.models import AccountingEntry, Anomaly


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
    }


def serialize_response(
    entries: list[AccountingEntry],
    anomalies: list[Anomaly],
    summary: dict[str, dict[str, int] | dict[str, float]],
) -> dict[str, object]:
    """Assemble la réponse complète ProcessResponse."""
    return {
        "entries": [serialize_entry(e) for e in entries],
        "anomalies": [serialize_anomaly(a) for a in anomalies],
        "summary": summary,
    }
