"""Tests d'intégration — Shopify orphan refund prior-period detection (Issue #1)."""

from __future__ import annotations

from io import BytesIO

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.controls.matching_checker import MatchingChecker
from compta_ecom.models import Anomaly, NormalizedTransaction
from compta_ecom.parsers.shopify import ShopifyParser

SALES_HEADER = "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country"
TX_HEADER = "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID"
PAYOUTS_HEADER = "Payout Date,Charges,Refunds,Fees,Total"


def _to_bytesio(csv_text: str) -> BytesIO:
    return BytesIO(csv_text.encode("utf-8"))


def _parse_shopify(
    sales_csv: str, tx_csv: str, payouts_csv: str, config: AppConfig
) -> tuple[list[NormalizedTransaction], list[Anomaly]]:
    """Parse Shopify from in-memory CSV strings, return (transactions, anomalies)."""
    parser = ShopifyParser()
    files = {
        "sales": _to_bytesio(sales_csv),
        "transactions": _to_bytesio(tx_csv),
        "payouts": _to_bytesio(payouts_csv),
    }
    result = parser.parse(files, config)
    return result.transactions, result.anomalies


class TestShopifyOrphanRefundPriorPeriod:
    """Remboursement orphelin antérieur à la période → prior_period_refund info."""

    def test_orphan_refund_prior_period(self, sample_config: AppConfig) -> None:
        """Refund ref #500 with sales starting at #1000 → prior_period_refund anomaly."""
        sales_csv = (
            f"{SALES_HEADER}\n"
            "#1000,2026-01-15,100.00,10.00,22.00,132.00,FR TVA 20%,22.00,Shopify Payments,FR\n"
        )
        tx_csv = (
            f"{TX_HEADER}\n"
            "#1000,charge,card,132.00,3.96,128.04,2026-01-23,P001\n"
            "#500,refund,card,-50.00,-1.50,-48.50,2026-01-24,P002\n"
        )
        payouts_csv = (
            f"{PAYOUTS_HEADER}\n"
            "2026-01-23,132.00,0.00,-3.96,128.04\n"
            "2026-01-24,0.00,-50.00,1.50,-48.50\n"
        )

        transactions, anomalies = _parse_shopify(sales_csv, tx_csv, payouts_csv, sample_config)

        # Should have prior_period_refund (info), NOT orphan_settlement
        prior_refund = [a for a in anomalies if a.type == "prior_period_refund"]
        assert len(prior_refund) == 1
        assert prior_refund[0].severity == "info"
        assert "#500" in (prior_refund[0].actual_value or "")

        # No orphan_settlement for the refund
        orphan_settlements = [a for a in anomalies if a.type == "orphan_settlement"]
        assert len(orphan_settlements) == 0

        # The NormalizedTransaction should have type="refund"
        refund_txs = [t for t in transactions if t.reference == "#500"]
        assert len(refund_txs) == 1
        assert refund_txs[0].type == "refund"


class TestShopifyOrphanRefundCurrentPeriod:
    """Remboursement orphelin de la période courante → orphan_refund warning."""

    def test_orphan_refund_current_period(self, sample_config: AppConfig) -> None:
        """Refund ref #1500 with sales starting at #1000 → orphan_refund warning."""
        sales_csv = (
            f"{SALES_HEADER}\n"
            "#1000,2026-01-15,100.00,10.00,22.00,132.00,FR TVA 20%,22.00,Shopify Payments,FR\n"
        )
        tx_csv = (
            f"{TX_HEADER}\n"
            "#1000,charge,card,132.00,3.96,128.04,2026-01-23,P001\n"
            "#1500,refund,card,-75.00,-2.25,-72.75,2026-01-24,P002\n"
        )
        payouts_csv = (
            f"{PAYOUTS_HEADER}\n"
            "2026-01-23,132.00,0.00,-3.96,128.04\n"
            "2026-01-24,0.00,-75.00,2.25,-72.75\n"
        )

        transactions, anomalies = _parse_shopify(sales_csv, tx_csv, payouts_csv, sample_config)

        # Should have orphan_refund (warning), NOT prior_period_refund
        orphan_refunds = [a for a in anomalies if a.type == "orphan_refund"]
        assert len(orphan_refunds) == 1
        assert orphan_refunds[0].severity == "warning"
        assert orphan_refunds[0].reference == "#1500"

        prior_refund = [a for a in anomalies if a.type == "prior_period_refund"]
        assert len(prior_refund) == 0


class TestShopifyMixedOrphansSeparateMessages:
    """Orphan charge + orphan refund antérieurs → 2 anomalies distinctes."""

    def test_mixed_orphans_separate_messages(self, sample_config: AppConfig) -> None:
        """Prior-period charge + prior-period refund → prior_period_settlement + prior_period_refund."""
        sales_csv = (
            f"{SALES_HEADER}\n"
            "#1000,2026-01-15,100.00,10.00,22.00,132.00,FR TVA 20%,22.00,Shopify Payments,FR\n"
        )
        tx_csv = (
            f"{TX_HEADER}\n"
            "#1000,charge,card,132.00,3.96,128.04,2026-01-23,P001\n"
            "#400,charge,card,80.00,2.40,77.60,2026-01-23,P001\n"
            "#500,refund,card,-50.00,-1.50,-48.50,2026-01-24,P002\n"
        )
        payouts_csv = (
            f"{PAYOUTS_HEADER}\n"
            "2026-01-23,212.00,0.00,-6.36,205.64\n"
            "2026-01-24,0.00,-50.00,1.50,-48.50\n"
        )

        transactions, anomalies = _parse_shopify(sales_csv, tx_csv, payouts_csv, sample_config)

        # Two distinct anomalies: one for charges, one for refunds
        prior_settlement = [a for a in anomalies if a.type == "prior_period_settlement"]
        prior_refund = [a for a in anomalies if a.type == "prior_period_refund"]

        assert len(prior_settlement) == 1
        assert prior_settlement[0].severity == "info"
        assert "#400" in (prior_settlement[0].actual_value or "")

        assert len(prior_refund) == 1
        assert prior_refund[0].severity == "info"
        assert "#500" in (prior_refund[0].actual_value or "")


class TestNoDuplicatePriorPeriodRefund:
    """Pas de doublon entre parser et matching_checker pour prior_period_refund."""

    def test_no_duplicate_prior_period_refund(self, sample_config: AppConfig) -> None:
        """matching_checker must not re-emit prior_period_refund for parser-handled orphans."""
        sales_csv = (
            f"{SALES_HEADER}\n"
            "#1000,2026-01-15,100.00,10.00,22.00,132.00,FR TVA 20%,22.00,Shopify Payments,FR\n"
        )
        tx_csv = (
            f"{TX_HEADER}\n"
            "#1000,charge,card,132.00,3.96,128.04,2026-01-23,P001\n"
            "#500,refund,card,-50.00,-1.50,-48.50,2026-01-24,P002\n"
        )
        payouts_csv = (
            f"{PAYOUTS_HEADER}\n"
            "2026-01-23,132.00,0.00,-3.96,128.04\n"
            "2026-01-24,0.00,-50.00,1.50,-48.50\n"
        )

        transactions, parser_anomalies = _parse_shopify(sales_csv, tx_csv, payouts_csv, sample_config)

        # Parser should emit exactly 1 prior_period_refund
        parser_prior = [a for a in parser_anomalies if a.type == "prior_period_refund"]
        assert len(parser_prior) == 1

        # matching_checker should NOT emit another prior_period_refund for the same refs
        checker_anomalies = MatchingChecker.check(transactions, sample_config)
        checker_prior = [a for a in checker_anomalies if a.type == "prior_period_refund"]
        assert len(checker_prior) == 0

        # Also no orphan_refund from checker for the same ref
        checker_orphan = [a for a in checker_anomalies if a.type == "orphan_refund"]
        assert len(checker_orphan) == 0
