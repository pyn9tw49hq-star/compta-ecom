"""Export Excel multi-onglets et résumé console."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from compta_ecom.config.loader import AppConfig
from compta_ecom.models import AccountingEntry, Anomaly

ENTRIES_COLUMNS = [
    "date",
    "journal",
    "account",
    "label",
    "debit",
    "credit",
    "piece_number",
    "lettrage",
    "channel",
    "entry_type",
]

ANOMALIES_COLUMNS = [
    "type",
    "severity",
    "reference",
    "channel",
    "detail",
    "expected_value",
    "actual_value",
]


def export(
    entries: list[AccountingEntry],
    anomalies: list[Anomaly],
    output_path: Path,
    config: AppConfig,
) -> None:
    """Exporte les écritures et anomalies dans un fichier Excel multi-onglets."""
    entries_data = [
        {
            "date": e.date,
            "journal": e.journal,
            "account": e.account,
            "label": e.label,
            "debit": e.debit,
            "credit": e.credit,
            "piece_number": e.piece_number,
            "lettrage": e.lettrage,
            "channel": e.channel,
            "entry_type": e.entry_type,
        }
        for e in entries
    ]
    df_entries = pd.DataFrame(entries_data, columns=ENTRIES_COLUMNS)

    anomalies_data = [
        {
            "type": a.type,
            "severity": a.severity,
            "reference": a.reference,
            "channel": a.channel,
            "detail": a.detail,
            "expected_value": a.expected_value,
            "actual_value": a.actual_value,
        }
        for a in anomalies
    ]
    df_anomalies = pd.DataFrame(anomalies_data, columns=ANOMALIES_COLUMNS)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_entries.to_excel(writer, sheet_name="Écritures", index=False)
        df_anomalies.to_excel(writer, sheet_name="Anomalies", index=False)


def print_summary(
    entries: list[AccountingEntry],
    anomalies: list[Anomaly],
    channel_errors: list[tuple[str, str]],
) -> None:
    """Affiche un résumé en console."""
    # Transactions par canal (sale + refund uniquement)
    tx_entries = [e for e in entries if e.entry_type in ("sale", "refund")]
    tx_by_channel: Counter[str] = Counter()
    refs_seen: set[tuple[str, str]] = set()
    for e in tx_entries:
        key = (e.channel, e.piece_number)
        if key not in refs_seen:
            refs_seen.add(key)
            tx_by_channel[e.channel] += 1

    print("=== Résumé ===")
    print(f"Transactions traitées : {sum(tx_by_channel.values())}")
    for channel, count in sorted(tx_by_channel.items()):
        print(f"  {channel} : {count}")

    # Écritures par type
    type_counts: Counter[str] = Counter(e.entry_type for e in entries)
    print(f"Écritures générées : {len(entries)}")
    for entry_type, count in sorted(type_counts.items()):
        print(f"  {entry_type} : {count}")

    # Anomalies
    n_serious = len([a for a in anomalies if a.severity != "info"])
    n_info = len([a for a in anomalies if a.severity == "info"])

    if not anomalies:
        print("Aucune anomalie détectée")
    else:
        print(f"Anomalies : {n_serious} warning/error, {n_info} info")

        # Ventilation par type (ordre d'apparition)
        type_order: list[str] = []
        type_counts_anom: Counter[str] = Counter()
        type_severity: dict[str, str] = {}
        for a in anomalies:
            if a.type not in type_severity:
                type_order.append(a.type)
                type_severity[a.type] = a.severity
            type_counts_anom[a.type] += 1

        print("  Par type :")
        for anom_type in type_order:
            count = type_counts_anom[anom_type]
            suffix = "  (info)" if type_severity[anom_type] == "info" else ""
            print(f"    {anom_type:<20s}: {count}{suffix}")

        # Ventilation par canal (ordre d'apparition)
        channel_order: list[str] = []
        channel_counts: Counter[str] = Counter()
        for a in anomalies:
            if a.channel not in channel_counts:
                channel_order.append(a.channel)
            channel_counts[a.channel] += 1

        print("  Par canal :")
        for chan in channel_order:
            print(f"    {chan:<20s}: {channel_counts[chan]}")

    # Canaux en erreur
    if channel_errors:
        print(f"Canaux en erreur : {len(channel_errors)}")
        for canal, msg in channel_errors:
            print(f"  {canal} : {msg}")
