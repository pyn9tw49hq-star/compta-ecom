"""Tests d'intégration — Refunds découverts dans les payout details (absents de Transactions Shopify)."""

from __future__ import annotations

from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounts import verify_balance
from compta_ecom.engine.accounting import generate_entries
from compta_ecom.engine.settlement_entries import generate_settlement_entries
from compta_ecom.models import NormalizedTransaction, ParseResult
from compta_ecom.parsers.shopify import ShopifyParser

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "shopify"


@pytest.fixture()
def parse_result_with_detail_refund(sample_config: AppConfig) -> ParseResult:
    """Parse les fixtures où le refund est dans payout details mais pas dans transactions."""
    parser = ShopifyParser()
    detail_dir = FIXTURES_DIR / "detail_versements_payout_detail_refund"
    files = {
        "sales": FIXTURES_DIR / "ventes_payout_detail_refund.csv",
        "transactions": FIXTURES_DIR / "transactions_payout_detail_refund.csv",
        "payouts": FIXTURES_DIR / "versements_payout_detail_refund.csv",
        "payout_details": sorted(detail_dir.glob("*.csv")),
    }
    return parser.parse(files, sample_config)


@pytest.fixture()
def all_transactions(parse_result_with_detail_refund: ParseResult) -> list[NormalizedTransaction]:
    return parse_result_with_detail_refund.transactions


@pytest.fixture()
def detail_refund_tx(all_transactions: list[NormalizedTransaction]) -> NormalizedTransaction:
    """Le refund créé à partir du payout detail."""
    matches = [t for t in all_transactions if t.type == "refund" and t.special_type == "payout_detail_refund"]
    assert len(matches) == 1, f"Expected 1 payout_detail_refund, got {len(matches)}"
    return matches[0]


class TestPayoutDetailRefundParsing:
    """Vérification que le refund est bien détecté dans les payout details."""

    def test_refund_created(self, all_transactions: list[NormalizedTransaction]) -> None:
        """Un refund est créé à partir du payout detail pour #PD002."""
        refunds = [t for t in all_transactions if t.type == "refund"]
        assert len(refunds) == 1

    def test_refund_special_type(self, detail_refund_tx: NormalizedTransaction) -> None:
        """Le refund porte special_type='payout_detail_refund'."""
        assert detail_refund_tx.special_type == "payout_detail_refund"

    def test_refund_reference(self, detail_refund_tx: NormalizedTransaction) -> None:
        """Le refund porte la référence de la commande d'origine."""
        assert detail_refund_tx.reference == "#PD002"

    def test_refund_amounts(self, detail_refund_tx: NormalizedTransaction) -> None:
        """Le montant TTC est correctement extrait (valeur absolue)."""
        assert detail_refund_tx.amount_ttc == 60.00

    def test_refund_tva_from_sale(self, detail_refund_tx: NormalizedTransaction) -> None:
        """Le taux TVA est récupéré depuis la vente d'origine."""
        assert detail_refund_tx.tva_rate == 20.0
        assert detail_refund_tx.amount_ht == 50.00
        assert detail_refund_tx.amount_tva == 10.00

    def test_refund_psp_data(self, detail_refund_tx: NormalizedTransaction) -> None:
        """Les données PSP proviennent du payout detail."""
        assert detail_refund_tx.payment_method == "card"
        assert detail_refund_tx.net_amount == -60.00
        assert detail_refund_tx.commission_ttc == 0.00
        assert detail_refund_tx.payout_reference == "RP101"

    def test_refund_date_is_transaction_date(self, detail_refund_tx: NormalizedTransaction) -> None:
        """La date du refund est la date de la transaction (pas du payout)."""
        import datetime

        assert detail_refund_tx.date == datetime.date(2026, 1, 26)

    def test_sales_count(self, all_transactions: list[NormalizedTransaction]) -> None:
        """Les 2 ventes sont toujours présentes."""
        sales = [t for t in all_transactions if t.type == "sale"]
        assert len(sales) == 2


class TestPayoutDetailRefundAccountingEntries:
    """Vérification que seules les écritures RG sont générées (pas d'avoir VE)."""

    def test_settlement_entries_generated(
        self,
        detail_refund_tx: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Les écritures RG (settlement) sont générées pour le refund."""
        entries = generate_settlement_entries(detail_refund_tx, sample_config)
        assert len(entries) > 0
        for e in entries:
            assert e.journal == "RG"

    def test_settlement_intermed_account(
        self,
        detail_refund_tx: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Le compte intermédiaire 46710001 est au crédit (refund TTC)."""
        entries = generate_settlement_entries(detail_refund_tx, sample_config)
        intermed_entries = [e for e in entries if e.account == "46710001"]
        assert len(intermed_entries) == 1  # commission=0 → only TTC pair
        assert intermed_entries[0].credit == 60.00
        assert intermed_entries[0].debit == 0.0

    def test_settlement_client_account(
        self,
        detail_refund_tx: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Le compte client 411 est au débit (contrepartie)."""
        entries = generate_settlement_entries(detail_refund_tx, sample_config)
        client_entries = [e for e in entries if e.account == "411SHOPIFY"]
        assert len(client_entries) == 1
        assert client_entries[0].debit == 60.00
        assert client_entries[0].credit == 0.0

    def test_no_commission_line_when_zero(
        self,
        detail_refund_tx: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Pas de ligne commission 627 quand fee=0."""
        entries = generate_settlement_entries(detail_refund_tx, sample_config)
        commission_entries = [e for e in entries if e.account.startswith("627")]
        assert len(commission_entries) == 0

    def test_settlement_balance(
        self,
        detail_refund_tx: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Balance débit = crédit sur les écritures settlement."""
        entries = generate_settlement_entries(detail_refund_tx, sample_config)
        verify_balance(entries)

    def test_lettrage_intermed(
        self,
        detail_refund_tx: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Lettrage sur compte intermédiaire 46710001 = payout_reference."""
        entries = generate_settlement_entries(detail_refund_tx, sample_config)
        intermed_entries = [e for e in entries if e.account == "46710001"]
        assert intermed_entries[0].lettrage == "RP101"

    def test_lettrage_client(
        self,
        detail_refund_tx: NormalizedTransaction,
        sample_config: AppConfig,
    ) -> None:
        """Lettrage sur compte 411 = order reference."""
        entries = generate_settlement_entries(detail_refund_tx, sample_config)
        client_entries = [e for e in entries if e.account == "411SHOPIFY"]
        assert client_entries[0].lettrage == "#PD002"

    def test_no_sale_entries_in_full_pipeline(
        self,
        parse_result_with_detail_refund: ParseResult,
        sample_config: AppConfig,
    ) -> None:
        """Dans le pipeline complet, le refund payout_detail ne génère PAS d'écritures VE de type refund."""
        entries, _ = generate_entries(
            parse_result_with_detail_refund.transactions,
            parse_result_with_detail_refund.payouts,
            sample_config,
        )
        # Les écritures VE de type "refund" pour #PD002 doivent être absentes
        # (les VE de type "sale" pour #PD002 sont normales — c'est la vente d'origine)
        ve_refund_entries = [
            e for e in entries
            if e.piece_number == "#PD002" and e.journal == "VE" and e.entry_type == "refund"
        ]
        rg_entries = [
            e for e in entries
            if e.piece_number == "#PD002" and e.journal == "RG" and e.entry_type in ("settlement", "commission")
        ]
        assert len(ve_refund_entries) == 0, f"Expected no VE refund entries for payout_detail_refund, got {len(ve_refund_entries)}"
        assert len(rg_entries) > 0, "Expected RG entries for payout_detail_refund"

    def test_lettrage_intermed_balanced_in_full_pipeline(
        self,
        parse_result_with_detail_refund: ParseResult,
        sample_config: AppConfig,
    ) -> None:
        """Le lettrage 46710001 est soldé : settlement + payout entries ont le même lettrage."""
        from collections import defaultdict

        entries, _ = generate_entries(
            parse_result_with_detail_refund.transactions,
            parse_result_with_detail_refund.payouts,
            sample_config,
        )
        # Grouper les écritures 46710001 par lettrage
        groups: dict[str, list] = defaultdict(list)
        for e in entries:
            if e.account == "46710001" and e.lettrage:
                groups[e.lettrage].append(e)

        # Vérifier que chaque groupe 46710001 est soldé
        for lettrage, group in groups.items():
            total_debit = round(sum(e.debit for e in group), 2)
            total_credit = round(sum(e.credit for e in group), 2)
            diff = round(abs(total_debit - total_credit), 2)
            assert diff <= 0.01, (
                f"Lettrage 46710001 '{lettrage}' déséquilibré : "
                f"débits={total_debit}€, crédits={total_credit}€, écart={diff}€"
            )

    def test_anomaly_info_generated(
        self,
        parse_result_with_detail_refund: ParseResult,
    ) -> None:
        """Une anomalie info 'payout_detail_refund_discovered' est générée."""
        anomalies = [
            a for a in parse_result_with_detail_refund.anomalies
            if a.type == "payout_detail_refund_discovered"
        ]
        assert len(anomalies) == 1
        assert anomalies[0].severity == "info"
        assert "#PD002" in anomalies[0].detail


class TestPayoutDetailRefundDeduplication:
    """Vérification que les refunds ne sont pas dupliqués."""

    def test_no_duplicate_when_refund_in_both(self, sample_config: AppConfig) -> None:
        """Si un refund est dans Transactions ET dans payout details, il n'est pas doublé."""
        parser = ShopifyParser()
        detail_dir = FIXTURES_DIR / "detail_versements_payout_detail_refund"

        # Créer un fichier transactions qui contient AUSSI le refund
        # On utilise les fixtures existantes du test refund classique
        files = {
            "sales": FIXTURES_DIR / "ventes_refund.csv",
            "transactions": FIXTURES_DIR / "transactions_refund.csv",
            "payouts": FIXTURES_DIR / "versements_refund.csv",
        }
        result_without_details = parser.parse(files, sample_config)
        refund_count_without = len([t for t in result_without_details.transactions if t.type == "refund"])

        # Maintenant avec payout_details contenant les mêmes refunds
        # Les refunds sont déjà dans transactions_refund.csv avec payout_reference=RP002
        # On crée un detail file avec le même payout_id
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            detail_path = Path(tmpdir) / "detail_RP002.csv"
            detail_path.write_text(
                "Transaction Date,Type,Order,Amount,Fee,Net,Payout Date,Payout ID,Payment Method Name\n"
                "2026-01-26,refund,#R001,-132.00,-3.84,-128.16,2026-01-26,RP002,card\n"
                "2026-01-26,refund,#R002,-60.00,2.10,-62.10,2026-01-26,RP002,card\n"
            )
            files_with_details = {
                "sales": FIXTURES_DIR / "ventes_refund.csv",
                "transactions": FIXTURES_DIR / "transactions_refund.csv",
                "payouts": FIXTURES_DIR / "versements_refund.csv",
                "payout_details": [detail_path],
            }
            result_with_details = parser.parse(files_with_details, sample_config)
            refund_count_with = len([t for t in result_with_details.transactions if t.type == "refund"])

        assert refund_count_with == refund_count_without, (
            f"Refund count changed from {refund_count_without} to {refund_count_with} when payout details added"
        )

    def test_multiple_partial_refunds_same_order(self, sample_config: AppConfig) -> None:
        """Deux refunds partiels pour la même commande dans le même payout sont tous deux créés."""
        import tempfile

        parser = ShopifyParser()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Ventes
            sales_path = Path(tmpdir) / "ventes.csv"
            sales_path.write_text(
                "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country\n"
                "#MP001,2026-01-18,100.00,0.00,20.00,120.00,FR TVA 20%,20.00,Shopify Payments,FR\n"
            )
            # Transactions (charge uniquement, pas de refund)
            tx_path = Path(tmpdir) / "transactions.csv"
            tx_path.write_text(
                "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
                "#MP001,charge,card,120.00,3.50,116.50,2026-01-25,RP200\n"
            )
            # Versements
            payouts_path = Path(tmpdir) / "versements.csv"
            payouts_path.write_text(
                "Payout Date,Charges,Refunds,Fees,Total\n"
                "2026-01-25,120.00,0.00,-3.50,116.50\n"
                "2026-01-28,0.00,-70.00,0.00,-70.00\n"
            )
            # Detail avec 2 refunds partiels pour la même commande
            detail_path = Path(tmpdir) / "detail_RP300.csv"
            detail_path.write_text(
                "Transaction Date,Type,Order,Amount,Fee,Net,Payout Date,Payout ID,Payment Method Name\n"
                "2026-01-27,refund,#MP001,-30.00,0.00,-30.00,2026-01-28,RP300,card\n"
                "2026-01-27,refund,#MP001,-40.00,0.00,-40.00,2026-01-28,RP300,card\n"
            )

            files = {
                "sales": sales_path,
                "transactions": tx_path,
                "payouts": payouts_path,
                "payout_details": [detail_path],
            }
            result = parser.parse(files, sample_config)

        refunds = [t for t in result.transactions if t.type == "refund"]
        assert len(refunds) == 2, f"Expected 2 partial refunds, got {len(refunds)}"
        amounts = sorted(r.amount_ttc for r in refunds)
        assert amounts == [30.00, 40.00]


class TestPayoutDetailRefundWithCommission:
    """Vérification du refund avec commission non-nulle."""

    def test_refund_with_nonzero_fee(self, sample_config: AppConfig) -> None:
        """Refund avec fee > 0 (commission conservée par PSP) génère bien une ligne 627."""
        import tempfile

        parser = ShopifyParser()

        with tempfile.TemporaryDirectory() as tmpdir:
            sales_path = Path(tmpdir) / "ventes.csv"
            sales_path.write_text(
                "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country\n"
                "#FC001,2026-01-18,50.00,0.00,10.00,60.00,FR TVA 20%,10.00,Shopify Payments,FR\n"
            )
            tx_path = Path(tmpdir) / "transactions.csv"
            tx_path.write_text(
                "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
                "#FC001,charge,card,60.00,2.10,57.90,2026-01-25,RP400\n"
            )
            payouts_path = Path(tmpdir) / "versements.csv"
            payouts_path.write_text(
                "Payout Date,Charges,Refunds,Fees,Total\n"
                "2026-01-25,60.00,0.00,-2.10,57.90\n"
                "2026-01-28,0.00,-60.00,2.10,-62.10\n"
            )
            detail_path = Path(tmpdir) / "detail_RP500.csv"
            detail_path.write_text(
                "Transaction Date,Type,Order,Amount,Fee,Net,Payout Date,Payout ID,Payment Method Name\n"
                "2026-01-27,refund,#FC001,-60.00,2.10,-62.10,2026-01-28,RP500,card\n"
            )

            files = {
                "sales": sales_path,
                "transactions": tx_path,
                "payouts": payouts_path,
                "payout_details": [detail_path],
            }
            result = parser.parse(files, sample_config)

        refunds = [t for t in result.transactions if t.type == "refund" and t.special_type == "payout_detail_refund"]
        assert len(refunds) == 1
        refund = refunds[0]
        assert refund.commission_ttc == 2.10
        assert refund.net_amount == -62.10

        # Vérifier que les écritures settlement incluent bien la ligne 627
        entries = generate_settlement_entries(refund, sample_config)
        commission_entries = [e for e in entries if e.account.startswith("627")]
        assert len(commission_entries) == 1
        assert commission_entries[0].debit == 2.10  # commission conservée par PSP

        # Avec compte intermédiaire : 46710001 C TTC (60) + 411 D TTC + 627 D (2.10) + 46710001 C (2.10)
        intermed_entries = [e for e in entries if e.account == "46710001"]
        assert len(intermed_entries) == 2  # TTC + commission
        client_entries = [e for e in entries if e.account == "411SHOPIFY"]
        assert len(client_entries) == 1
        assert client_entries[0].debit == 60.00  # net + commission = -62.10 + 2.10 = -60.00

        verify_balance(entries)

    def test_refund_with_negative_fee(self, sample_config: AppConfig) -> None:
        """Refund avec fee < 0 (commission restituée par PSP) génère 627 au crédit."""
        import tempfile

        parser = ShopifyParser()

        with tempfile.TemporaryDirectory() as tmpdir:
            sales_path = Path(tmpdir) / "ventes.csv"
            sales_path.write_text(
                "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country\n"
                "#FC002,2026-01-18,100.00,0.00,20.00,120.00,FR TVA 20%,20.00,Shopify Payments,FR\n"
            )
            tx_path = Path(tmpdir) / "transactions.csv"
            tx_path.write_text(
                "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
                "#FC002,charge,card,120.00,3.50,116.50,2026-01-25,RP600\n"
            )
            payouts_path = Path(tmpdir) / "versements.csv"
            payouts_path.write_text(
                "Payout Date,Charges,Refunds,Fees,Total\n"
                "2026-01-25,120.00,0.00,-3.50,116.50\n"
                "2026-01-28,0.00,-120.00,-3.50,-116.50\n"
            )
            detail_path = Path(tmpdir) / "detail_RP700.csv"
            detail_path.write_text(
                "Transaction Date,Type,Order,Amount,Fee,Net,Payout Date,Payout ID,Payment Method Name\n"
                "2026-01-27,refund,#FC002,-120.00,-3.50,-116.50,2026-01-28,RP700,card\n"
            )

            files = {
                "sales": sales_path,
                "transactions": tx_path,
                "payouts": payouts_path,
                "payout_details": [detail_path],
            }
            result = parser.parse(files, sample_config)

        refunds = [t for t in result.transactions if t.type == "refund" and t.special_type == "payout_detail_refund"]
        assert len(refunds) == 1
        refund = refunds[0]
        assert refund.commission_ttc == -3.50

        entries = generate_settlement_entries(refund, sample_config)
        commission_entries = [e for e in entries if e.account.startswith("627")]
        assert len(commission_entries) == 1
        assert commission_entries[0].credit == 3.50  # commission restituée

        # Avec compte intermédiaire : 46710001 au lieu de 511
        intermed_entries = [e for e in entries if e.account == "46710001"]
        assert len(intermed_entries) == 2  # TTC pair + commission pair

        verify_balance(entries)
