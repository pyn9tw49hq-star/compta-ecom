"""Tests d'intégration — auto-détection du séparateur CSV."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from compta_ecom.config.loader import load_config
from compta_ecom.pipeline import PipelineOrchestrator

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
CONFIG_FIXTURES = FIXTURES_DIR / "config"

# ---------------------------------------------------------------------------
# Headers (reprises de test_pipeline_final.py)
# ---------------------------------------------------------------------------

# Shopify — normalement séparé par ","
SHOPIFY_SALES_HEADER = "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country"
SHOPIFY_TX_HEADER = "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID"
SHOPIFY_PAYOUTS_HEADER = "Payout Date,Charges,Refunds,Fees,Total"

# ManoMano — normalement séparé par ";"
MANOMANO_CA_HEADER = "reference;type;createdAt;amountVatIncl;commissionVatIncl;commissionVatExcl;vatOnCommission;netAmount;productPriceVatExcl;vatOnProduct;shippingPriceVatExcl;vatOnShipping"
MANOMANO_VERSEMENTS_HEADER = "REFERENCE;TYPE;PAYOUT_REFERENCE;PAYOUT_DATE;AMOUNT"

# Décathlon — normalement séparé par ";"
DECATHLON_HEADER = "Numéro de commande;Type;Date de commande;Date du cycle de paiement;Montant"


def _swap_sep(text: str, old: str, new: str) -> str:
    """Remplace le séparateur dans un CSV brut (headers + lignes de données)."""
    return text.replace(old, new)


# ---------------------------------------------------------------------------
# 1. Shopify ventes avec ";" au lieu de ","
# ---------------------------------------------------------------------------

class TestShopifySemicolonSales:
    def test_shopify_semicolon_sales_parses(self, tmp_path: Path) -> None:
        """Fichier ventes Shopify sauvé par Excel FR (sep=;) → parse OK."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Ventes avec ";" au lieu de ","
        sales_csv = _swap_sep(
            f"{SHOPIFY_SALES_HEADER}\n"
            "#SH001,2026-01-15,100.00,0.00,20.00,120.00,FR TVA 20%,20.00,Shopify Payments,FR\n",
            ",", ";"
        )
        (input_dir / "ventes.csv").write_text(sales_csv, encoding="utf-8")

        # Transactions et versements normaux (virgule)
        (input_dir / "transactions.csv").write_text(
            f"{SHOPIFY_TX_HEADER}\n"
            "#SH001,charge,card,120.00,3.60,116.40,2026-01-23,P001\n"
        )
        (input_dir / "versements.csv").write_text(
            f"{SHOPIFY_PAYOUTS_HEADER}\n"
            "2026-01-23,120.00,0.00,-3.60,116.40\n"
        )

        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"
        orchestrator = PipelineOrchestrator()
        orchestrator.run(input_dir, output, config)
        assert output.exists()


# ---------------------------------------------------------------------------
# 2. Shopify transactions avec ";" au lieu de ","
# ---------------------------------------------------------------------------

class TestShopifySemicolonTransactions:
    def test_shopify_semicolon_transactions_parses(self, tmp_path: Path) -> None:
        """Fichier transactions Shopify sauvé par Excel FR (sep=;) → parse OK."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Ventes normales
        (input_dir / "ventes.csv").write_text(
            f"{SHOPIFY_SALES_HEADER}\n"
            "#SH001,2026-01-15,100.00,0.00,20.00,120.00,FR TVA 20%,20.00,Shopify Payments,FR\n"
        )

        # Transactions avec ";"
        tx_csv = _swap_sep(
            f"{SHOPIFY_TX_HEADER}\n"
            "#SH001,charge,card,120.00,3.60,116.40,2026-01-23,P001\n",
            ",", ";"
        )
        (input_dir / "transactions.csv").write_text(tx_csv, encoding="utf-8")

        (input_dir / "versements.csv").write_text(
            f"{SHOPIFY_PAYOUTS_HEADER}\n"
            "2026-01-23,120.00,0.00,-3.60,116.40\n"
        )

        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"
        orchestrator = PipelineOrchestrator()
        orchestrator.run(input_dir, output, config)
        assert output.exists()


# ---------------------------------------------------------------------------
# 3. ManoMano CA avec "," au lieu de ";"
# ---------------------------------------------------------------------------

class TestManoManoCommaCa:
    def test_manomano_comma_ca_parses(self, tmp_path: Path) -> None:
        """Fichier CA ManoMano sauvé avec "," au lieu de ";" → parse OK."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # CA avec virgules
        ca_csv = _swap_sep(
            f"{MANOMANO_CA_HEADER}\n"
            "M001;ORDER;2026-01-15;120.00;18.00;15.00;3.00;102.00;100.00;20.00;0.00;0.00\n",
            ";", ","
        )
        (input_dir / "ca.csv").write_text(ca_csv, encoding="utf-8")

        # Versements normaux (point-virgule)
        (input_dir / "versements_manomano.csv").write_text(
            f"{MANOMANO_VERSEMENTS_HEADER}\n"
            "M001;ORDER;PAY001;2026-01-31;102.00\n"
        )

        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"
        orchestrator = PipelineOrchestrator()
        orchestrator.run(input_dir, output, config)
        assert output.exists()


# ---------------------------------------------------------------------------
# 4. Mirakl (Décathlon) avec "," au lieu de ";"
# ---------------------------------------------------------------------------

class TestMiraklComma:
    def test_mirakl_comma_parses(self, tmp_path: Path) -> None:
        """Fichier Décathlon sauvé avec "," au lieu de ";" → parse OK."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        deca_csv = _swap_sep(
            f"{DECATHLON_HEADER}\n"
            "DEC001;Montant;2026-01-10;2026-01-25;100.00\n"
            "DEC001;Frais de port;2026-01-10;2026-01-25;10.00\n"
            "DEC001;Commission;2026-01-10;2026-01-25;-15.00\n"
            "DEC001;Taxe sur la commission;2026-01-10;2026-01-25;0.00\n"
            "DEC001;Paiement;2026-01-10;2026-01-25;95.00\n",
            ";", ","
        )
        (input_dir / "decathlon_data.csv").write_text(deca_csv, encoding="utf-8")

        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"
        orchestrator = PipelineOrchestrator()
        orchestrator.run(input_dir, output, config)
        assert output.exists()


# ---------------------------------------------------------------------------
# 5. BytesIO Shopify avec ";" via run_from_buffers
# ---------------------------------------------------------------------------

class TestRunFromBuffersWrongSeparator:
    def test_run_from_buffers_wrong_separator(self) -> None:
        """Pipeline run_from_buffers avec fichiers Shopify en ";" → parse OK."""
        sales_csv = _swap_sep(
            f"{SHOPIFY_SALES_HEADER}\n"
            "#SH001,2026-01-15,100.00,0.00,20.00,120.00,FR TVA 20%,20.00,Shopify Payments,FR\n",
            ",", ";"
        )
        tx_csv = _swap_sep(
            f"{SHOPIFY_TX_HEADER}\n"
            "#SH001,charge,card,120.00,3.60,116.40,2026-01-23,P001\n",
            ",", ";"
        )
        payouts_csv = _swap_sep(
            f"{SHOPIFY_PAYOUTS_HEADER}\n"
            "2026-01-23,120.00,0.00,-3.60,116.40\n",
            ",", ";"
        )

        files = {
            "ventes.csv": sales_csv.encode("utf-8"),
            "transactions.csv": tx_csv.encode("utf-8"),
            "versements.csv": payouts_csv.encode("utf-8"),
        }

        config = load_config(CONFIG_FIXTURES)
        orchestrator = PipelineOrchestrator()
        entries, anomalies, summary, txns = orchestrator.run_from_buffers(files, config)
        assert len(entries) > 0
        assert len(txns) > 0
