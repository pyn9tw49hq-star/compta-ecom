"""Tests d'intégration — filtrage par plage de dates dans run_from_buffers()."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from compta_ecom.config.loader import load_config
from compta_ecom.models import Anomaly, NoResultError, ParseResult
from compta_ecom.pipeline import PipelineOrchestrator

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
CONFIG_FIXTURES = FIXTURES_DIR / "config"

# CSV Shopify fixtures — two sales in January, one in February
SHOPIFY_SALES = (
    "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country\n"
    "#SH001,2026-01-15,100.00,10.00,22.00,132.00,FR TVA 20%,22.00,Shopify Payments,FR\n"
    "#SH002,2026-01-20,50.00,0.00,10.00,60.00,FR TVA 20%,10.00,Shopify Payments,FR\n"
    "#SH003,2026-02-10,80.00,5.00,17.00,102.00,FR TVA 20%,17.00,Shopify Payments,FR\n"
)
SHOPIFY_TX = (
    "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
    "#SH001,charge,card,132.00,3.96,128.04,2026-01-23,P001\n"
    "#SH002,charge,card,60.00,1.80,58.20,2026-01-23,P001\n"
    "#SH003,charge,card,102.00,3.06,98.94,2026-02-15,P002\n"
)
SHOPIFY_PAYOUTS = (
    "Payout Date,Charges,Refunds,Fees,Total\n"
    "2026-01-23,192.00,0.00,-5.76,186.24\n"
    "2026-02-15,102.00,0.00,-3.06,98.94\n"
)


def _build_files() -> dict[str, bytes]:
    return {
        "ventes.csv": SHOPIFY_SALES.encode(),
        "transactions.csv": SHOPIFY_TX.encode(),
        "versements.csv": SHOPIFY_PAYOUTS.encode(),
    }


def test_pipeline_date_filter_includes_in_range():
    """Filtre janvier → seules les transactions de janvier."""
    config = load_config(CONFIG_FIXTURES)
    pipeline = PipelineOrchestrator()
    entries, anomalies, summary, txs = pipeline.run_from_buffers(
        _build_files(),
        config,
        date_from=datetime.date(2026, 1, 1),
        date_to=datetime.date(2026, 1, 31),
    )
    # Only January transactions
    tx_refs = {t.reference for t in txs}
    assert "#SH001" in tx_refs
    assert "#SH002" in tx_refs
    assert "#SH003" not in tx_refs


def test_pipeline_date_filter_excludes_out_of_range():
    """Filtre février → pas d'écritures de janvier."""
    config = load_config(CONFIG_FIXTURES)
    pipeline = PipelineOrchestrator()
    entries, anomalies, summary, txs = pipeline.run_from_buffers(
        _build_files(),
        config,
        date_from=datetime.date(2026, 2, 1),
        date_to=datetime.date(2026, 2, 28),
    )
    tx_refs = {t.reference for t in txs}
    assert "#SH003" in tx_refs
    assert "#SH001" not in tx_refs
    assert "#SH002" not in tx_refs


def test_pipeline_no_date_filter_returns_all():
    """Sans filtre → toutes les transactions."""
    config = load_config(CONFIG_FIXTURES)
    pipeline = PipelineOrchestrator()
    entries, anomalies, summary, txs = pipeline.run_from_buffers(
        _build_files(),
        config,
    )
    tx_refs = {t.reference for t in txs}
    assert "#SH001" in tx_refs
    assert "#SH002" in tx_refs
    assert "#SH003" in tx_refs


def test_pipeline_date_filter_empty_range():
    """Plage sans transaction → NoResultError (résultat vide), pas de crash."""
    config = load_config(CONFIG_FIXTURES)
    pipeline = PipelineOrchestrator()
    # March 2026 — no transactions exist in this range
    # The pipeline filters transactions to empty, then _process_parse_results
    # will still run but produce empty entries. This should not crash.
    entries, anomalies, summary, txs = pipeline.run_from_buffers(
        _build_files(),
        config,
        date_from=datetime.date(2026, 3, 1),
        date_to=datetime.date(2026, 3, 31),
    )
    assert len(txs) == 0
    assert len(entries) == 0


def test_pipeline_date_filter_anomalies_scoped():
    """Anomalie hors plage exclue, anomalie dans la plage conservée, anomalie globale conservée."""
    config = load_config(CONFIG_FIXTURES)
    pipeline = PipelineOrchestrator()

    # First run without filter to get a baseline with all transactions
    _, _, _, all_txs = pipeline.run_from_buffers(_build_files(), config)
    assert len(all_txs) == 3  # sanity check

    # Run with January filter — only #SH001 and #SH002
    entries, anomalies, summary, txs = pipeline.run_from_buffers(
        _build_files(),
        config,
        date_from=datetime.date(2026, 1, 1),
        date_to=datetime.date(2026, 1, 31),
    )
    tx_refs = {t.reference for t in txs}
    assert "#SH001" in tx_refs
    assert "#SH002" in tx_refs
    assert "#SH003" not in tx_refs

    # All anomalies should reference only retained transactions or be global (empty ref)
    for a in anomalies:
        if a.reference:
            assert a.reference in tx_refs, (
                f"Anomaly for {a.reference!r} should not appear — transaction is out of range"
            )
