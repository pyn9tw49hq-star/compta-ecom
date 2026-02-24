"""Tests pour engine/accounting.py — orchestrateur et vérifications qualité."""

from __future__ import annotations

import datetime
from pathlib import Path

from compta_ecom.config.loader import AppConfig
from compta_ecom.engine.accounting import generate_entries
from compta_ecom.models import NormalizedTransaction, PayoutSummary


def _make_transaction(**overrides: object) -> NormalizedTransaction:
    """Helper pour construire une NormalizedTransaction avec des valeurs par défaut."""
    defaults: dict[str, object] = {
        "reference": "#1118",
        "channel": "shopify",
        "date": datetime.date(2024, 1, 15),
        "type": "sale",
        "amount_ht": 100.0,
        "amount_tva": 20.0,
        "amount_ttc": 120.0,
        "shipping_ht": 0.0,
        "shipping_tva": 0.0,
        "tva_rate": 20.0,
        "country_code": "250",
        "commission_ttc": 0.0,
        "commission_ht": 0.0,
        "net_amount": 120.0,
        "payout_date": None,
        "payout_reference": None,
        "payment_method": None,
        "special_type": None,
    }
    defaults.update(overrides)
    return NormalizedTransaction(**defaults)  # type: ignore[arg-type]


class TestGenerateEntriesSalesConcatenation:
    """Tests that generate_entries produces sale entries for multiple transactions."""

    def test_three_transactions_produce_sale_entries(self, sample_config: AppConfig) -> None:
        """3 transactions → sale entries concaténées dans generate_entries."""
        transactions = [
            _make_transaction(
                reference="#001",
                payment_method="card",
                net_amount=95.0,
                commission_ttc=5.0,
            ),
            _make_transaction(
                reference="#002",
                type="refund",
                payment_method="card",
                net_amount=-95.0,
                commission_ttc=-5.0,
            ),
            _make_transaction(
                reference="#003",
                amount_ht=50.0,
                amount_tva=0.0,
                amount_ttc=50.0,
                country_code="974",
                payment_method="card",
                net_amount=45.0,
                commission_ttc=5.0,
            ),
        ]

        entries, _ = generate_entries(transactions, [], sample_config)

        sale_entries = [e for e in entries if e.entry_type in ("sale", "refund")]
        # #001: sale → 3 lines, #002: refund → 3 lines, #003: 0 VAT → 2 lines
        assert len(sale_entries) == 8

    def test_empty_list(self, sample_config: AppConfig) -> None:
        """Liste vide → résultat vide."""
        entries, anomalies = generate_entries([], [], sample_config)
        assert entries == []
        assert anomalies == []


class TestGenerateEntriesSettlements:
    """Tests that generate_entries produces settlement entries for PSP transactions."""

    def test_mixed_transactions(self, sample_config: AppConfig) -> None:
        """3 transactions (1 sale card + 1 refund PayPal + 1 payment_method=None)."""
        transactions = [
            _make_transaction(
                reference="#S01",
                payment_method="card",
                net_amount=95.0,
                commission_ttc=5.0,
            ),
            _make_transaction(
                reference="#R01",
                type="refund",
                payment_method="paypal",
                net_amount=-95.0,
                commission_ttc=-5.0,
            ),
            _make_transaction(
                reference="#N01",
                payment_method=None,
            ),
        ]

        entries, _ = generate_entries(transactions, [], sample_config)

        settlement_entries = [e for e in entries if e.entry_type == "settlement"]
        commission_entries = [e for e in entries if e.entry_type == "commission"]

        # #S01: 2 settlement + 2 commission (avec intermédiaire), #R01: 2 settlement + 2 commission, #N01: 0
        assert len(settlement_entries) == 4
        assert len(commission_entries) == 4


class TestGenerateEntries:
    """Tests de l'orchestrateur complet generate_entries()."""

    def test_three_types_of_entries(self, sample_config: AppConfig) -> None:
        """generate_entries avec transactions + payouts → 3 types d'écritures."""
        transactions = [
            _make_transaction(
                reference="#S01",
                payment_method="card",
                net_amount=95.0,
                commission_ttc=5.0,
            ),
        ]
        payouts = [
            PayoutSummary(
                payout_date=datetime.date(2026, 1, 23),
                channel="shopify",
                total_amount=95.0,
                charges=100.0,
                refunds=0.0,
                fees=-5.0,
                transaction_references=["#S01"],
                psp_type="card",
                payout_reference="P001",
            ),
        ]

        entries, anomalies = generate_entries(transactions, payouts, sample_config)

        entry_types = {e.entry_type for e in entries}
        assert "sale" in entry_types
        assert "settlement" in entry_types
        assert "payout" in entry_types
        assert len(anomalies) == 0

    def test_special_type_filtered(self, sample_config: AppConfig) -> None:
        """Transaction avec special_type non-SUBSCRIPTION sans payout_date → aucune écriture."""
        transactions = [
            _make_transaction(
                reference="#ADJ01",
                channel="manomano",
                special_type="ADJUSTMENT",
                payment_method=None,
            ),
        ]

        entries, anomalies = generate_entries(transactions, [], sample_config)

        assert len(entries) == 0
        assert len(anomalies) == 0

    def test_subscription_without_payout_date_generates_entries(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION sans payout_date → écritures fee générées (date de création)."""
        transactions = [
            _make_transaction(
                reference="#SUB01",
                channel="manomano",
                special_type="SUBSCRIPTION",
                payment_method=None,
                net_amount=-60.0,
                amount_ht=50.0,
                amount_tva=10.0,
            ),
        ]

        entries, anomalies = generate_entries(transactions, [], sample_config)

        assert len(entries) == 3
        assert all(e.entry_type == "fee" for e in entries)
        assert len(anomalies) == 0

    def test_payout_anomalies_aggregated(self, sample_config: AppConfig) -> None:
        """Anomalies payout (mixed_psp) sont agrégées dans le résultat."""
        transactions: list[NormalizedTransaction] = []
        payouts = [
            PayoutSummary(
                payout_date=datetime.date(2026, 1, 23),
                channel="shopify",
                total_amount=100.0,
                charges=100.0,
                refunds=0.0,
                fees=0.0,
                transaction_references=["#S01"],
                psp_type=None,
                payout_reference="P_MIX",
            ),
        ]

        entries, anomalies = generate_entries(transactions, payouts, sample_config)

        payout_entries = [e for e in entries if e.entry_type == "payout"]
        assert len(payout_entries) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "mixed_psp_payout"


class TestGenerateEntriesMixedMarketplacePSP:
    """Tests dispatch mixte marketplace + PSP (AC14, AC15, AC22)."""

    def test_mixed_scenario_entry_counts(self, sample_config: AppConfig) -> None:
        """Scénario mixte : Shopify sale + ManoMano sale + ManoMano refund non restituée.

        Vérification comptage par entry_type :
        - 3 sale (Shopify sale 3 lignes) + refund (ManoMano refund 3 lignes) = en tout
          sale/refund entries from sale_entries
        - 1 settlement PSP (Shopify) + 1 commission PSP (Shopify) = settlement_entries
        - 2 commission marketplace (ManoMano sale) + 2 commission marketplace (ManoMano refund)
        """
        transactions = [
            # (1) Shopify sale card
            _make_transaction(
                reference="#SHOP01",
                channel="shopify",
                payment_method="card",
                amount_ht=100.0,
                amount_tva=20.0,
                amount_ttc=120.0,
                net_amount=115.0,
                commission_ttc=5.0,
                commission_ht=4.17,
            ),
            # (2) ManoMano sale
            _make_transaction(
                reference="#MM01",
                channel="manomano",
                payment_method=None,
                amount_ht=80.0,
                amount_tva=16.0,
                amount_ttc=96.0,
                net_amount=78.0,
                commission_ttc=18.0,
                commission_ht=15.0,
            ),
            # (3) ManoMano refund — commission non restituée (commission_ttc > 0)
            _make_transaction(
                reference="#MM02",
                channel="manomano",
                type="refund",
                payment_method=None,
                amount_ht=80.0,
                amount_tva=16.0,
                amount_ttc=96.0,
                net_amount=78.0,
                commission_ttc=18.0,
                commission_ht=15.0,
            ),
        ]
        payouts = [
            PayoutSummary(
                payout_date=datetime.date(2026, 1, 23),
                channel="shopify",
                total_amount=115.0,
                charges=120.0,
                refunds=0.0,
                fees=-5.0,
                transaction_references=["#SHOP01"],
                psp_type="card",
                payout_reference="P001",
            ),
        ]

        entries, anomalies = generate_entries(transactions, payouts, sample_config)

        sale_type_entries = [e for e in entries if e.entry_type == "sale"]
        refund_type_entries = [e for e in entries if e.entry_type == "refund"]
        settlement_type_entries = [e for e in entries if e.entry_type == "settlement"]
        commission_type_entries = [e for e in entries if e.entry_type == "commission"]
        payout_type_entries = [e for e in entries if e.entry_type == "payout"]

        # SHOP01: sale → entry_type=sale (3 lines: 411+707+4457)
        # MM01: sale → entry_type=sale (3 lines: 411+707+4457)
        # MM02: refund → entry_type=refund (3 lines: 411+707+4457)
        assert len(sale_type_entries) == 6  # SHOP01(3) + MM01(3)
        assert len(refund_type_entries) == 3  # MM02(3)

        # Shopify settlement: 2 settlement (46710001 + 411)
        assert len(settlement_type_entries) == 2

        # 2 commission PSP (Shopify 627 + 46710001) + 3 commission marketplace (MM01 HT+TVA+client) + 3 commission marketplace (MM02 HT+TVA+client)
        assert len(commission_type_entries) == 8

        # Payout: 2 lines (511 D + 512 C)
        assert len(payout_type_entries) == 2

        assert len(anomalies) == 0

    def test_special_type_in_mixed_batch(self, sample_config: AppConfig) -> None:
        """Transaction avec special_type dans un lot mixte → aucune écriture pour elle."""
        transactions = [
            _make_transaction(
                reference="#SHOP01",
                channel="shopify",
                payment_method="card",
                net_amount=95.0,
                commission_ttc=5.0,
            ),
            _make_transaction(
                reference="#ADJ01",
                channel="manomano",
                special_type="ADJUSTMENT",
                payment_method=None,
            ),
        ]

        entries, _ = generate_entries(transactions, [], sample_config)

        adj_entries = [e for e in entries if e.piece_number == "#ADJ01"]
        assert len(adj_entries) == 0

        shop_entries = [e for e in entries if e.piece_number == "#SHOP01"]
        assert len(shop_entries) > 0


class TestDispatchFinalStory24:
    """Tests dispatch final Story 2.4 — reversements marketplace + filtre PayoutSummary."""

    def test_mixed_complete_scenario(self, sample_config: AppConfig) -> None:
        """Scénario mixte complet : Shopify sale + ManoMano sale + ManoMano refund
        + ManoMano SUBSCRIPTION + ManoMano ADJUSTMENT → comptage par entry_type × channel."""
        payout_date = datetime.date(2024, 1, 20)
        transactions = [
            # Shopify sale
            _make_transaction(
                reference="#SHOP01",
                channel="shopify",
                payment_method="card",
                amount_ht=100.0,
                amount_tva=20.0,
                amount_ttc=120.0,
                net_amount=115.0,
                commission_ttc=5.0,
                commission_ht=4.17,
            ),
            # ManoMano sale with payout_date
            _make_transaction(
                reference="#MM01",
                channel="manomano",
                payment_method=None,
                amount_ht=80.0,
                amount_tva=16.0,
                amount_ttc=96.0,
                net_amount=78.0,
                commission_ttc=18.0,
                commission_ht=15.0,
                payout_date=payout_date,
            ),
            # ManoMano refund with payout_date
            _make_transaction(
                reference="#MM02",
                channel="manomano",
                type="refund",
                payment_method=None,
                amount_ht=80.0,
                amount_tva=16.0,
                amount_ttc=96.0,
                net_amount=-78.0,
                commission_ttc=-18.0,
                commission_ht=-15.0,
                payout_date=payout_date,
            ),
            # ManoMano SUBSCRIPTION
            _make_transaction(
                reference="#SUB01",
                channel="manomano",
                special_type="SUBSCRIPTION",
                payment_method=None,
                net_amount=-60.0,
                amount_ht=50.0,
                amount_tva=10.0,
                commission_ttc=0.0,
                commission_ht=None,
                payout_date=payout_date,
            ),
            # ManoMano ADJUSTMENT
            _make_transaction(
                reference="#ADJ01",
                channel="manomano",
                special_type="ADJUSTMENT",
                payment_method=None,
                net_amount=50.0,
                commission_ttc=0.0,
                commission_ht=None,
                payout_date=payout_date,
            ),
        ]

        entries, anomalies = generate_entries(transactions, [], sample_config)

        # Count by entry_type
        sale_entries = [e for e in entries if e.entry_type == "sale"]
        refund_entries = [e for e in entries if e.entry_type == "refund"]
        settlement_entries = [e for e in entries if e.entry_type == "settlement"]
        commission_entries = [e for e in entries if e.entry_type == "commission"]
        payout_entries = [e for e in entries if e.entry_type == "payout"]
        fee_entries = [e for e in entries if e.entry_type == "fee"]

        # SHOP01: 3 sale, MM01: 3 sale
        assert len(sale_entries) == 6
        # MM02: 3 refund
        assert len(refund_entries) == 3
        # SHOP01 settlement: 2
        assert len(settlement_entries) == 2
        # SHOP01 commission(2: 627+46710001) + MM01 commission(3 HT+TVA+client) + MM02 commission(3 HT+TVA+client)
        assert len(commission_entries) == 8
        # ADJ01 payout(2) — MM01/MM02 n'ont plus de payout 512 (#16: commission in charges_mp)
        assert len(payout_entries) == 2
        # SUB01 fee(3) - charge HT + TVA + 411MANO TTC
        assert len(fee_entries) == 3

        # Verify marketplace payout entries by channel
        mm_payouts = [e for e in payout_entries if e.channel == "manomano"]
        assert len(mm_payouts) == 2

        assert len(anomalies) == 0

    def test_marketplace_no_payout_date_no_payout_entries(
        self, sample_config: AppConfig
    ) -> None:
        """Transaction marketplace régulière avec payout_date=None → vente + commission, pas de payout."""
        transactions = [
            _make_transaction(
                reference="#MM01",
                channel="manomano",
                payment_method=None,
                amount_ht=80.0,
                amount_tva=16.0,
                amount_ttc=96.0,
                net_amount=78.0,
                commission_ttc=18.0,
                commission_ht=15.0,
                payout_date=None,
            ),
        ]

        entries, _ = generate_entries(transactions, [], sample_config)

        sale_entries = [e for e in entries if e.entry_type == "sale"]
        commission_entries = [e for e in entries if e.entry_type == "commission"]
        payout_entries = [e for e in entries if e.entry_type == "payout"]

        assert len(sale_entries) == 3  # 411 + 707 + 4457
        assert len(commission_entries) == 3  # 62220300 + 44566001 + 411MANO (#14)
        assert len(payout_entries) == 0  # No payout_date → no payout

    def test_payout_summary_manomano_generates_entries(
        self, sample_config: AppConfig
    ) -> None:
        """PayoutSummary ManoMano → écritures payout agrégé (580 ↔ 411)."""
        payouts = [
            PayoutSummary(
                payout_date=datetime.date(2026, 1, 23),
                channel="manomano",
                total_amount=-500.0,  # Négatif car paiement sortant du marketplace
                charges=500.0,
                refunds=0.0,
                fees=0.0,
                transaction_references=["#MM01"],
                psp_type=None,
                payout_reference="PAY-MM-001",
            ),
        ]

        entries, anomalies = generate_entries([], payouts, sample_config)

        assert len(entries) == 2
        # 580 (transit) débité, 411MANO (client) crédité
        assert entries[0].account == "58000000"
        assert entries[0].debit == 500.0
        assert entries[1].account == "411MANO"
        assert entries[1].credit == 500.0
        assert len(anomalies) == 0

    def test_payout_summary_shopify_psp_generates_entries(
        self, sample_config: AppConfig
    ) -> None:
        """PayoutSummary Shopify avec psp_type='card' → écriture payout PSP."""
        payouts = [
            PayoutSummary(
                payout_date=datetime.date(2026, 1, 23),
                channel="shopify",
                total_amount=95.0,
                charges=100.0,
                refunds=0.0,
                fees=-5.0,
                transaction_references=["#S01"],
                psp_type="card",
                payout_reference="P001",
            ),
        ]

        entries, anomalies = generate_entries([], payouts, sample_config)

        payout_entries = [e for e in entries if e.entry_type == "payout"]
        assert len(payout_entries) == 2
        assert len(anomalies) == 0
        # Verify accounts: transit (58000000) and intermédiaire (46710001)
        accounts = {e.account for e in payout_entries}
        assert "58000000" in accounts
        assert "46710001" in accounts

    def test_payout_summary_shopify_degraded_mixed_psp(
        self, sample_config: AppConfig
    ) -> None:
        """PayoutSummary Shopify dégradé (psp_type=None) → anomalie mixed_psp_payout préservée."""
        payouts = [
            PayoutSummary(
                payout_date=datetime.date(2026, 1, 23),
                channel="shopify",
                total_amount=100.0,
                charges=100.0,
                refunds=0.0,
                fees=0.0,
                transaction_references=["#S01"],
                psp_type=None,
                payout_reference="P_MIX",
            ),
        ]

        entries, anomalies = generate_entries([], payouts, sample_config)

        payout_entries = [e for e in entries if e.entry_type == "payout"]
        assert len(payout_entries) == 0
        assert len(anomalies) == 1
        assert anomalies[0].type == "mixed_psp_payout"

    def test_non_regression_shopify_full_flow(self, sample_config: AppConfig) -> None:
        """Non-régression : Shopify sale + PayoutSummary → sale + settlement + payout PSP."""
        transactions = [
            _make_transaction(
                reference="#S01",
                channel="shopify",
                payment_method="card",
                net_amount=95.0,
                commission_ttc=5.0,
                commission_ht=4.17,
            ),
        ]
        payouts = [
            PayoutSummary(
                payout_date=datetime.date(2026, 1, 23),
                channel="shopify",
                total_amount=95.0,
                charges=100.0,
                refunds=0.0,
                fees=-5.0,
                transaction_references=["#S01"],
                psp_type="card",
                payout_reference="P001",
            ),
        ]

        entries, anomalies = generate_entries(transactions, payouts, sample_config)

        entry_types = {e.entry_type for e in entries}
        assert "sale" in entry_types
        assert "settlement" in entry_types
        assert "payout" in entry_types
        assert len(anomalies) == 0

    def test_special_type_non_marketplace_ignored(self, sample_config: AppConfig) -> None:
        """Ligne spéciale avec channel not in config.fournisseurs → ignorée."""
        transactions = [
            _make_transaction(
                reference="#SPE01",
                channel="shopify",
                special_type="ADJUSTMENT",
                payment_method=None,
                payout_date=datetime.date(2024, 1, 20),
                net_amount=50.0,
            ),
        ]

        entries, _ = generate_entries(transactions, [], sample_config)

        # shopify is not in fournisseurs → no entries generated
        assert len(entries) == 0


class TestDecathlonSkipIndividualPayout:
    """Tests du skip payout individuel Décathlon (accounting.py L66)."""

    def test_decathlon_sale_no_individual_payout(self, sample_config: AppConfig) -> None:
        """Vente Décathlon régulière → sale + commission mais aucun payout individuel."""
        transactions = [
            _make_transaction(
                reference="#DEC01",
                channel="decathlon",
                payment_method=None,
                amount_ht=83.33,
                amount_tva=16.67,
                amount_ttc=100.0,
                net_amount=85.0,
                commission_ttc=-15.0,
                commission_ht=-15.0,
                payout_date=datetime.date(2024, 1, 20),
                payout_reference="CYC-2024-01",
            ),
        ]

        entries, anomalies = generate_entries(transactions, [], sample_config)

        sale_entries = [e for e in entries if e.entry_type == "sale"]
        commission_entries = [e for e in entries if e.entry_type == "commission"]
        payout_entries = [e for e in entries if e.entry_type == "payout"]

        # sale : CDECATHLON + 70703250 + 4457250 = 3 lignes
        assert len(sale_entries) == 3
        # commission : 62220800 D / CDECATHLON C (commission_ttc < 0) = 2 lignes
        assert len(commission_entries) == 2
        # payout : 0 — comportement spécifique Décathlon
        assert len(payout_entries) == 0
        assert len(anomalies) == 0

        # Aucune écriture ne touche le compte banque ni FDECATHLON en payout
        all_accounts = {e.account for e in entries if e.entry_type == "payout"}
        assert "51200000" not in all_accounts
        assert "FDECATHLON" not in all_accounts

    def test_decathlon_sale_with_payout_summary(self, sample_config: AppConfig) -> None:
        """Flux complet Décathlon : vente (pas de payout individuel) + PayoutSummary agrégé."""
        transactions = [
            _make_transaction(
                reference="#DEC01",
                channel="decathlon",
                payment_method=None,
                amount_ht=83.33,
                amount_tva=16.67,
                amount_ttc=100.0,
                net_amount=85.0,
                commission_ttc=-15.0,
                commission_ht=-15.0,
                payout_date=datetime.date(2024, 1, 20),
                payout_reference="CYC-2024-01",
            ),
        ]
        payouts = [
            PayoutSummary(
                payout_date=datetime.date(2024, 1, 20),
                channel="decathlon",
                total_amount=-85.0,
                charges=100.0,
                refunds=0.0,
                fees=-15.0,
                transaction_references=["#DEC01"],
                psp_type=None,
                payout_reference="CYC-2024-01",
            ),
        ]

        entries, anomalies = generate_entries(transactions, payouts, sample_config)

        sale_entries = [e for e in entries if e.entry_type == "sale"]
        commission_entries = [e for e in entries if e.entry_type == "commission"]
        payout_entries = [e for e in entries if e.entry_type == "payout"]

        # sale : 3 lignes
        assert len(sale_entries) == 3
        # commission : 2 lignes
        assert len(commission_entries) == 2
        # payout : 2 lignes (uniquement le PayoutSummary agrégé)
        assert len(payout_entries) == 2
        assert len(anomalies) == 0

        # Les 2 écritures payout touchent transit (580) et client (CDECATHLON)
        payout_accounts = {e.account for e in payout_entries}
        assert "58000000" in payout_accounts
        assert "CDECATHLON" in payout_accounts
        # Aucune écriture payout sur banque ni fournisseur
        assert "51200000" not in payout_accounts
        assert "FDECATHLON" not in payout_accounts

    def test_decathlon_subscription_still_generates_fee(self, sample_config: AppConfig) -> None:
        """SUBSCRIPTION Décathlon → écritures fee toujours générées (branche L44-45 non impactée)."""
        transactions = [
            _make_transaction(
                reference="#SUBDEC01",
                channel="decathlon",
                special_type="SUBSCRIPTION",
                payment_method=None,
                amount_ht=0.0,
                amount_tva=0.0,
                amount_ttc=0.0,
                net_amount=-39.90,
                commission_ttc=0.0,
                commission_ht=None,
                payout_date=datetime.date(2024, 1, 20),
                payout_reference="CYC-2024-01",
            ),
        ]

        entries, anomalies = generate_entries(transactions, [], sample_config)

        fee_entries = [e for e in entries if e.entry_type == "fee"]
        sale_entries = [e for e in entries if e.entry_type == "sale"]
        payout_entries = [e for e in entries if e.entry_type == "payout"]

        # fee : CDECATHLON ↔ 61311112 = 2 lignes
        assert len(fee_entries) == 2
        # sale : 0 (le continue L46 bypass le bloc sale)
        assert len(sale_entries) == 0
        # payout : 0
        assert len(payout_entries) == 0
        assert len(anomalies) == 0

        # Les comptes touchés sont client et compte de charge abonnement, entry_type="fee"
        fee_accounts = {e.account for e in fee_entries}
        assert "CDECATHLON" in fee_accounts
        assert "61311112" in fee_accounts

    def test_leroy_merlin_no_individual_payout(self, sample_config: AppConfig) -> None:
        """Leroy Merlin : pas de payout individuel 512 (même comportement que Décathlon)."""
        transactions = [
            _make_transaction(
                reference="#LM01",
                channel="leroy_merlin",
                payment_method=None,
                amount_ht=50.0,
                amount_tva=10.0,
                amount_ttc=60.0,
                net_amount=48.0,
                commission_ttc=-12.0,
                commission_ht=-10.0,
                payout_date=datetime.date(2024, 1, 25),
            ),
        ]

        entries, anomalies = generate_entries(transactions, [], sample_config)

        sale_entries = [e for e in entries if e.entry_type == "sale"]
        commission_entries = [e for e in entries if e.entry_type == "commission"]
        payout_entries = [e for e in entries if e.entry_type == "payout"]

        # sale : 411LM + 70704250 + 4457250 = 3 lignes
        assert len(sale_entries) == 3
        # commission : 62220900 D (HT) + 44566001 D (TVA) + 411LM C (TTC) = 3 lignes
        assert len(commission_entries) == 3
        # payout : 0 — même comportement que Décathlon (skip payout individuel)
        assert len(payout_entries) == 0
        assert len(anomalies) == 0

        # Aucune écriture ne touche le compte banque 512
        all_accounts = {e.account for e in entries}
        assert "51200000" not in all_accounts


class TestNoPandasInEngine:
    """Vérification automatisée : aucun import pandas dans engine/."""

    def test_no_pandas_import(self) -> None:
        """Aucun fichier dans engine/ ne doit importer pandas."""
        engine_dir = Path(__file__).parents[2] / "src" / "compta_ecom" / "engine"
        for py_file in engine_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "import pandas" not in content, (
                f"{py_file.name} contient un import pandas interdit"
            )
            assert "from pandas" not in content, (
                f"{py_file.name} contient un import pandas interdit"
            )
