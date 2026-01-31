"""Moteur d'écritures comptables."""

from __future__ import annotations

from compta_ecom.engine.accounting import (
    generate_all_payout_entries,
    generate_entries,
)

__all__ = [
    "generate_all_payout_entries",
    "generate_entries",
]
