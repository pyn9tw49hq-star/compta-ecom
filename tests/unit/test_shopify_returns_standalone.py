"""Tests pour le mode Avoirs Seul — fichier retours Shopify autonome (Story 3.6)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig, ChannelConfig, PspConfig
from compta_ecom.models import ParseError
from compta_ecom.parsers.shopify import ShopifyParser
from compta_ecom.pipeline import PipelineOrchestrator


@pytest.fixture
def shopify_config() -> AppConfig:
    """AppConfig minimale avec required_file_groups pour les tests mode avoirs seul."""
    return AppConfig(
        clients={"shopify": "411SHOPIFY"},
        fournisseurs={},
        psp={
            "card": PspConfig(compte="51150007", commission="62700002"),
        },
        transit="58000000",
        banque="51200000",
        comptes_speciaux={},
        comptes_vente_prefix="707",
        canal_codes={"shopify": "01"},
        comptes_tva_prefix="4457",
        comptes_port_prefix="7085",
        zones_port={"france": "00", "hors_ue": "01", "ue": "02"},
        vat_table={
            "250": {"name": "France", "rate": 20.0, "alpha2": "FR"},
        },
        alpha2_to_numeric={"FR": "250"},
        channels={
            "shopify": ChannelConfig(
                files={
                    "sales": "ventes.csv",
                    "transactions": "transactions.csv",
                    "payouts": "versements.csv",
                    "payout_details": "detail_versements*.csv",
                    "returns": "returns.csv",
                },
                encoding="utf-8",
                separator=",",
                multi_files=["payout_details"],
                optional_files=["returns", "payout_details"],
                required_file_groups=[
                    ["sales", "transactions", "payouts"],
                    ["returns"],
                ],
            ),
        },
    )


RETURNS_CSV = (
    "Jour,ID de vente,Nom de la commande,Titre du produit au moment de la vente,"
    "Retours bruts,Réductions retournées,Retours nets,Expédition retournée,"
    "Taxes retournées,Frais de retour,Total des retours\n"
    "2026-01-20,S001,#RET001,Produit A,-120.00,0.00,-100.00,0.00,-20.00,0.00,-120.00\n"
    "2026-01-21,S002,#RET002,Produit B,-60.00,0.00,-50.00,-10.00,-12.00,0.00,-72.00\n"
)

SALES_CSV = (
    "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,"
    "Tax 1 Value,Payment Method,Shipping Country\n"
    "#SALE001,2026-01-15,100.00,10.00,22.00,132.00,FR TVA 20%,"
    "22.00,Shopify Payments,FR\n"
)

TX_CSV = (
    "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
    "#SALE001,charge,card,132.00,3.84,128.16,2026-01-23,P001\n"
)

PAYOUTS_CSV = (
    "Payout Date,Charges,Refunds,Fees,Total\n"
    "2026-01-23,132.00,0.00,-3.84,128.16\n"
)


class TestStandaloneReturnsParser:
    """Tests du parser Shopify en mode avoirs seul."""

    def test_returns_only_produces_avoirs(self, shopify_config: AppConfig) -> None:
        """Avec uniquement le fichier returns, le parser produit des returns_avoir."""
        files: dict[str, BytesIO] = {
            "returns": BytesIO(RETURNS_CSV.encode()),
        }
        parser = ShopifyParser()
        result = parser.parse(files, shopify_config)  # type: ignore[arg-type]
        assert len(result.transactions) == 2
        for tx in result.transactions:
            assert tx.type == "refund"
            assert tx.special_type == "returns_avoir"
            assert tx.channel == "shopify"

    def test_returns_only_no_payouts(self, shopify_config: AppConfig) -> None:
        """En mode avoirs seul, aucun PayoutSummary n'est généré."""
        files: dict[str, BytesIO] = {
            "returns": BytesIO(RETURNS_CSV.encode()),
        }
        parser = ShopifyParser()
        result = parser.parse(files, shopify_config)  # type: ignore[arg-type]
        assert len(result.payouts) == 0

    def test_returns_only_country_fallback_france(self, shopify_config: AppConfig) -> None:
        """Sans sales_data, tous les retours fallback à country_code 250 (France)."""
        files: dict[str, BytesIO] = {
            "returns": BytesIO(RETURNS_CSV.encode()),
        }
        parser = ShopifyParser()
        result = parser.parse(files, shopify_config)  # type: ignore[arg-type]
        for tx in result.transactions:
            assert tx.country_code == "250"
        # Anomalie return_no_matching_sale pour chaque retour
        warnings = [a for a in result.anomalies if a.type == "return_no_matching_sale"]
        assert len(warnings) == 2

    def test_returns_only_amounts(self, shopify_config: AppConfig) -> None:
        """Vérification des montants en mode avoirs seul."""
        files: dict[str, BytesIO] = {
            "returns": BytesIO(RETURNS_CSV.encode()),
        }
        parser = ShopifyParser()
        result = parser.parse(files, shopify_config)  # type: ignore[arg-type]
        ret001 = next(t for t in result.transactions if t.reference == "#RET001")
        assert ret001.amount_ht == 100.0
        assert ret001.amount_ttc == 120.0
        assert ret001.shipping_ht == 0.0

    def test_no_sales_no_returns_raises_parse_error(self, shopify_config: AppConfig) -> None:
        """Sans sales ni returns, ParseError est levée."""
        files: dict[str, BytesIO] = {
            "transactions": BytesIO(TX_CSV.encode()),
        }
        parser = ShopifyParser()
        with pytest.raises(ParseError, match="au moins le fichier Ventes ou le fichier Retours"):
            parser.parse(files, shopify_config)  # type: ignore[arg-type]


class TestStandaloneReturnsPipeline:
    """Tests du pipeline complet en mode avoirs seul (run_from_buffers)."""

    def test_pipeline_returns_only(self, shopify_config: AppConfig) -> None:
        """Pipeline avec uniquement returns → écritures d'avoir générées."""
        orch = PipelineOrchestrator()
        files = {"returns.csv": RETURNS_CSV.encode()}
        entries, anomalies, summary, txs = orch.run_from_buffers(files, shopify_config)
        assert len(entries) > 0
        # Toutes les transactions sont des returns_avoir
        for tx in txs:
            assert tx.special_type == "returns_avoir"
        # Écritures d'avoir : entry_type == "refund"
        entry_types = {e.entry_type for e in entries}
        assert "refund" in entry_types
        assert "settlement" not in entry_types

    def test_pipeline_returns_only_no_sale_entries(self, shopify_config: AppConfig) -> None:
        """En mode avoirs seul, pas d'écritures de vente."""
        orch = PipelineOrchestrator()
        files = {"returns.csv": RETURNS_CSV.encode()}
        entries, _, _, _ = orch.run_from_buffers(files, shopify_config)
        sale_entries = [e for e in entries if e.entry_type == "sale"]
        assert len(sale_entries) == 0

    def test_pipeline_returns_only_lettrage_empty_on_411(self, shopify_config: AppConfig) -> None:
        """En mode avoirs seul, les écritures 411 ont un lettrage vide (pas de settlement)."""
        orch = PipelineOrchestrator()
        files = {"returns.csv": RETURNS_CSV.encode()}
        entries, _, _, _ = orch.run_from_buffers(files, shopify_config)
        entries_411 = [e for e in entries if e.account.startswith("411")]
        assert len(entries_411) > 0
        for e in entries_411:
            assert e.lettrage == "", f"411 entry should have empty lettrage, got '{e.lettrage}'"


class TestRetrocompatibilityModeComplet:
    """Le mode complet (sales+transactions+payouts) fonctionne comme avant."""

    def test_mode_complet_unchanged(self, shopify_config: AppConfig) -> None:
        """Pipeline mode complet → même comportement qu'avant."""
        orch = PipelineOrchestrator()
        files = {
            "ventes.csv": SALES_CSV.encode(),
            "transactions.csv": TX_CSV.encode(),
            "versements.csv": PAYOUTS_CSV.encode(),
        }
        entries, anomalies, summary, txs = orch.run_from_buffers(files, shopify_config)
        assert len(entries) > 0
        sales = [t for t in txs if t.type == "sale" and t.special_type is None]
        assert len(sales) == 1

    def test_mode_complet_with_returns(self, shopify_config: AppConfig) -> None:
        """Pipeline mode complet + returns → comportement story 3.5."""
        orch = PipelineOrchestrator()
        returns_csv = (
            "Jour,ID de vente,Nom de la commande,Titre du produit au moment de la vente,"
            "Retours bruts,Réductions retournées,Retours nets,Expédition retournée,"
            "Taxes retournées,Frais de retour,Total des retours\n"
            "2026-01-20,S001,#SALE001,Produit A,-132.00,0.00,-110.00,0.00,-22.00,0.00,-132.00\n"
        )
        files = {
            "ventes.csv": SALES_CSV.encode(),
            "transactions.csv": TX_CSV.encode(),
            "versements.csv": PAYOUTS_CSV.encode(),
            "returns.csv": returns_csv.encode(),
        }
        entries, anomalies, summary, txs = orch.run_from_buffers(files, shopify_config)
        avoirs = [t for t in txs if t.special_type == "returns_avoir"]
        assert len(avoirs) == 1
        # La vente normale est aussi présente
        sales = [t for t in txs if t.type == "sale" and t.special_type is None]
        assert len(sales) == 1

    def test_mode_complet_with_returns_lettrage_preserved(self, shopify_config: AppConfig) -> None:
        """En mode complet + returns, le lettrage 411 des avoirs est conservé quand un refund_settlement existe."""
        orch = PipelineOrchestrator()
        # TX includes a refund for #SALE001 → gets retagged as refund_settlement
        tx_with_refund = (
            "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID\n"
            "#SALE001,charge,card,132.00,3.84,128.16,2026-01-23,P001\n"
            "#SALE001,refund,card,-132.00,0.00,-132.00,2026-01-25,P002\n"
        )
        payouts_with_refund = (
            "Payout Date,Charges,Refunds,Fees,Total\n"
            "2026-01-23,132.00,0.00,-3.84,128.16\n"
            "2026-01-25,0.00,-132.00,0.00,-132.00\n"
        )
        returns_csv = (
            "Jour,ID de vente,Nom de la commande,Titre du produit au moment de la vente,"
            "Retours bruts,Réductions retournées,Retours nets,Expédition retournée,"
            "Taxes retournées,Frais de retour,Total des retours\n"
            "2026-01-20,S001,#SALE001,Produit A,-132.00,0.00,-110.00,0.00,-22.00,0.00,-132.00\n"
        )
        files = {
            "ventes.csv": SALES_CSV.encode(),
            "transactions.csv": tx_with_refund.encode(),
            "versements.csv": payouts_with_refund.encode(),
            "returns.csv": returns_csv.encode(),
        }
        entries, _, _, txs = orch.run_from_buffers(files, shopify_config)
        # Verify refund_settlement was created
        settlements = [t for t in txs if t.special_type == "refund_settlement"]
        assert len(settlements) > 0, "Should have a refund_settlement transaction"
        # 411 avoir entries should have non-empty lettrage (refund_settlement provides the counterpart)
        avoir_411 = [e for e in entries if e.account.startswith("411") and e.entry_type == "refund"]
        assert len(avoir_411) > 0
        for e in avoir_411:
            assert e.lettrage != "", "411 avoir should keep lettrage when settlement exists"


class TestPipelineDispatchGroups:
    """Tests du dispatch pipeline avec required_file_groups."""

    def test_dispatch_returns_only_accepted(self, shopify_config: AppConfig) -> None:
        """Un seul fichier returns doit passer le dispatch."""
        orch = PipelineOrchestrator()
        buffers = {"returns.csv": b"dummy"}
        result = orch._detect_files_from_buffers(buffers, shopify_config.channels)
        assert "shopify" in result
        assert "returns" in result["shopify"]

    def test_dispatch_mode_complet_accepted(self, shopify_config: AppConfig) -> None:
        """Les 3 fichiers obligatoires du mode complet passent le dispatch."""
        orch = PipelineOrchestrator()
        buffers = {
            "ventes.csv": b"dummy",
            "transactions.csv": b"dummy",
            "versements.csv": b"dummy",
        }
        result = orch._detect_files_from_buffers(buffers, shopify_config.channels)
        assert "shopify" in result
        assert "sales" in result["shopify"]
        assert "transactions" in result["shopify"]
        assert "payouts" in result["shopify"]

    def test_dispatch_incomplete_group_rejected(self, shopify_config: AppConfig) -> None:
        """Un fichier sales seul ne satisfait aucun groupe → canal ignoré."""
        orch = PipelineOrchestrator()
        buffers = {"ventes.csv": b"dummy"}
        result = orch._detect_files_from_buffers(buffers, shopify_config.channels)
        assert "shopify" not in result

    def test_dispatch_no_overmatch(self, shopify_config: AppConfig) -> None:
        """payout_details pattern must not match unrelated filenames."""
        orch = PipelineOrchestrator()
        buffers = {"returns.csv": b"dummy"}
        result = orch._detect_files_from_buffers(buffers, shopify_config.channels)
        assert "shopify" in result
        # returns.csv must not match payout_details pattern
        assert "payout_details" not in result["shopify"]

    def test_dispatch_legacy_channel_without_groups(self, shopify_config: AppConfig) -> None:
        """Un canal sans required_file_groups utilise la logique legacy."""
        # manomano has no required_file_groups
        config_no_groups = AppConfig(
            clients={},
            fournisseurs={},
            psp={},
            transit="58000000",
            banque="51200000",
            comptes_speciaux={},
            comptes_vente_prefix="707",
            canal_codes={},
            comptes_tva_prefix="4457",
            vat_table={},
            channels={
                "test_channel": ChannelConfig(
                    files={"data": "test*.csv"},
                    encoding="utf-8",
                    separator=",",
                ),
            },
        )
        orch = PipelineOrchestrator()
        buffers = {"test_data.csv": b"dummy"}
        result = orch._detect_files_from_buffers(buffers, config_no_groups.channels)
        assert "test_channel" in result


class TestBufferPatternMatching:
    """Tests de détection des fichiers utilisateur réels en mode buffer."""

    @pytest.fixture
    def prod_like_config(self) -> AppConfig:
        """Config avec patterns production (accent wildcard + flat payout_details)."""
        return AppConfig(
            clients={"shopify": "411SHOPIFY"},
            fournisseurs={},
            psp={"card": PspConfig(compte="51150007", commission="62700002")},
            transit="58000000",
            banque="51200000",
            comptes_speciaux={},
            comptes_vente_prefix="707",
            canal_codes={"shopify": "01"},
            comptes_tva_prefix="4457",
            vat_table={},
            channels={
                "shopify": ChannelConfig(
                    files={
                        "sales": "Ventes Shopify*.csv",
                        "transactions": "Transactions Shopify*.csv",
                        "payouts": "D?tails versements*.csv",
                        "payout_details": "Detail transactions par versements*.csv",
                        "returns": "Total des retours*.csv",
                    },
                    encoding="utf-8",
                    separator=",",
                    multi_files=["payout_details"],
                    optional_files=["returns", "payout_details"],
                    required_file_groups=[
                        ["sales", "transactions", "payouts"],
                        ["returns"],
                    ],
                ),
            },
        )

    def test_payouts_sans_accent(self, prod_like_config: AppConfig) -> None:
        """'Details versements.csv' (sans accent) matche le pattern 'D?tails versements*.csv'."""
        orch = PipelineOrchestrator()
        buffers = {
            "Ventes Shopify.csv": b"dummy",
            "Transactions Shopify.csv": b"dummy",
            "Details versements.csv": b"dummy",
        }
        result = orch._detect_files_from_buffers(buffers, prod_like_config.channels)
        assert "shopify" in result
        assert "payouts" in result["shopify"]

    def test_payouts_avec_accent(self, prod_like_config: AppConfig) -> None:
        """'Détails versements.csv' (avec accent) matche aussi le pattern."""
        orch = PipelineOrchestrator()
        buffers = {
            "Ventes Shopify.csv": b"dummy",
            "Transactions Shopify.csv": b"dummy",
            "D\u00e9tails versements.csv": b"dummy",
        }
        result = orch._detect_files_from_buffers(buffers, prod_like_config.channels)
        assert "shopify" in result
        assert "payouts" in result["shopify"]

    def test_payout_details_flat_files(self, prod_like_config: AppConfig) -> None:
        """Fichiers plats 'Detail transactions par versements N.csv' matchent en buffer mode."""
        orch = PipelineOrchestrator()
        buffers = {
            "Ventes Shopify.csv": b"dummy",
            "Transactions Shopify.csv": b"dummy",
            "Details versements.csv": b"dummy",
            "Detail transactions par versements 1.csv": b"d1",
            "Detail transactions par versements 2.csv": b"d2",
            "Detail transactions par versements 3.csv": b"d3",
        }
        result = orch._detect_files_from_buffers(buffers, prod_like_config.channels)
        assert "shopify" in result
        assert "payout_details" in result["shopify"]
        # multi_files → list
        assert isinstance(result["shopify"]["payout_details"], list)
        assert len(result["shopify"]["payout_details"]) == 3

    def test_payout_details_no_overmatch_transactions(self, prod_like_config: AppConfig) -> None:
        """'Transactions Shopify.csv' ne matche PAS le pattern payout_details."""
        orch = PipelineOrchestrator()
        buffers = {
            "Ventes Shopify.csv": b"dummy",
            "Transactions Shopify.csv": b"dummy",
            "Details versements.csv": b"dummy",
        }
        result = orch._detect_files_from_buffers(buffers, prod_like_config.channels)
        assert "shopify" in result
        assert "payout_details" not in result["shopify"]


class TestCaseInsensitiveBufferMatching:
    """Tests que _detect_files_from_buffers matche les noms de fichiers indépendamment de la casse."""

    def test_manomano_lowercase_filename_matches_titlecase_pattern(self) -> None:
        """'ca manomano.csv' (minuscule) matche le pattern 'CA Manomano*.csv' (titre)."""
        config = AppConfig(
            clients={},
            fournisseurs={},
            psp={},
            transit="58000000",
            banque="51200000",
            comptes_speciaux={},
            comptes_vente_prefix="707",
            canal_codes={},
            comptes_tva_prefix="4457",
            vat_table={},
            channels={
                "manomano": ChannelConfig(
                    files={
                        "ca": "CA Manomano*.csv",
                        "payouts": "Detail versement Manomano*.csv",
                    },
                    encoding="utf-8",
                    separator=";",
                ),
            },
        )
        orch = PipelineOrchestrator()
        buffers = {
            "ca manomano.csv": b"dummy",
            "detail versement manomano.csv": b"dummy",
        }
        result = orch._detect_files_from_buffers(buffers, config.channels)
        assert "manomano" in result
        assert "ca" in result["manomano"]
        assert "payouts" in result["manomano"]

    def test_uppercase_filename_matches_titlecase_pattern(self) -> None:
        """'CA MANOMANO.csv' (majuscule) matche le pattern 'CA Manomano*.csv'."""
        config = AppConfig(
            clients={},
            fournisseurs={},
            psp={},
            transit="58000000",
            banque="51200000",
            comptes_speciaux={},
            comptes_vente_prefix="707",
            canal_codes={},
            comptes_tva_prefix="4457",
            vat_table={},
            channels={
                "manomano": ChannelConfig(
                    files={"ca": "CA Manomano*.csv"},
                    encoding="utf-8",
                    separator=";",
                ),
            },
        )
        orch = PipelineOrchestrator()
        buffers = {"CA MANOMANO.csv": b"dummy"}
        result = orch._detect_files_from_buffers(buffers, config.channels)
        assert "manomano" in result
        assert "ca" in result["manomano"]


class TestConfigValidation:
    """Tests de la validation de required_file_groups dans loader.py."""

    def test_load_config_with_groups(self) -> None:
        """La config avec required_file_groups se charge correctement."""
        from compta_ecom.config.loader import load_config

        config_dir = Path(__file__).parent.parent / "fixtures" / "config"
        config = load_config(config_dir)
        shopify = config.channels["shopify"]
        assert shopify.required_file_groups == [
            ["sales", "transactions", "payouts"],
            ["returns"],
        ]
        # manomano has no groups
        assert config.channels["manomano"].required_file_groups == []

    def test_channel_config_default_empty_groups(self) -> None:
        """ChannelConfig sans required_file_groups a une liste vide par défaut."""
        cc = ChannelConfig(files={"a": "a.csv"}, encoding="utf-8", separator=",")
        assert cc.required_file_groups == []
