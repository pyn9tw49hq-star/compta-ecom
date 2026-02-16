"""Test de benchmark de performance — NFR1 : pipeline complet < 30 s pour ~400 transactions."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from compta_ecom.config.loader import load_config
from compta_ecom.pipeline import PipelineOrchestrator

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
CONFIG_FIXTURES = FIXTURES_DIR / "config"

# ---------------------------------------------------------------------------
# Headers CSV par canal
# ---------------------------------------------------------------------------

SHOPIFY_SALES_HEADER = (
    "Name,Created at,Subtotal,Shipping,Taxes,Total,Tax 1 Name,Tax 1 Value,Payment Method,Shipping Country"
)
SHOPIFY_TX_HEADER = "Order,Type,Payment Method Name,Amount,Fee,Net,Payout Date,Payout ID"
SHOPIFY_PAYOUTS_HEADER = "Payout Date,Charges,Refunds,Fees,Total"

MANOMANO_CA_HEADER = (
    "reference;type;createdAt;amountVatIncl;commissionVatIncl;commissionVatExcl;"
    "vatOnCommission;netAmount;productPriceVatExcl;vatOnProduct;shippingPriceVatExcl;vatOnShipping"
)
MANOMANO_VERSEMENTS_HEADER = "REFERENCE;TYPE;PAYOUT_REFERENCE;PAYOUT_DATE;AMOUNT"

DECATHLON_HEADER = "Numéro de commande;Type;Date de commande;Date du cycle de paiement;Montant"


# ---------------------------------------------------------------------------
# Générateurs de fixtures CSV réalistes (~400 transactions)
# ---------------------------------------------------------------------------


def _generate_shopify_csvs(input_dir: Path, count: int) -> None:
    """Génère *count* ventes Shopify avec transactions et versements correspondants."""
    sales_lines: list[str] = [SHOPIFY_SALES_HEADER]
    tx_lines: list[str] = [SHOPIFY_TX_HEADER]

    total_charges = 0.0
    total_fees = 0.0

    for i in range(1, count + 1):
        ref = f"#PERF-SH{i:04d}"
        subtotal = 80.0 + (i % 40)
        shipping = 5.0 + (i % 3)
        tva = round((subtotal + shipping) * 0.2, 2)
        total = round(subtotal + shipping + tva, 2)
        fee = round(total * 0.03, 2)
        net = round(total - fee, 2)
        day = (i % 28) + 1

        sales_lines.append(
            f"{ref},2026-01-{day:02d},{subtotal:.2f},{shipping:.2f},{tva:.2f},{total:.2f},"
            f"FR TVA 20%,{tva:.2f},Shopify Payments,FR"
        )
        tx_lines.append(f"{ref},charge,card,{total:.2f},{fee:.2f},{net:.2f},2026-01-28,PAY-SH1")

        total_charges += total
        total_fees += fee

    total_payout = round(total_charges - total_fees, 2)
    payout_lines = [
        SHOPIFY_PAYOUTS_HEADER,
        f"2026-01-28,{total_charges:.2f},0.00,-{total_fees:.2f},{total_payout:.2f}",
    ]

    (input_dir / "ventes.csv").write_text("\n".join(sales_lines) + "\n", encoding="utf-8")
    (input_dir / "transactions.csv").write_text("\n".join(tx_lines) + "\n", encoding="utf-8")
    (input_dir / "versements.csv").write_text("\n".join(payout_lines) + "\n", encoding="utf-8")


def _generate_manomano_csvs(input_dir: Path, count: int) -> None:
    """Génère *count* commandes ManoMano avec versements correspondants."""
    ca_lines: list[str] = [MANOMANO_CA_HEADER]
    payout_lines: list[str] = [MANOMANO_VERSEMENTS_HEADER]

    for i in range(1, count + 1):
        ref = f"PERF-MM{i:04d}"
        product_ht = 60.0 + (i % 50)
        tva_product = round(product_ht * 0.2, 2)
        ttc = round(product_ht + tva_product, 2)
        commission_ht = round(product_ht * 0.15, 2)
        commission_tva = round(commission_ht * 0.2, 2)
        commission_ttc = round(commission_ht + commission_tva, 2)
        net = round(ttc - commission_ttc, 2)

        ca_lines.append(
            f"{ref};ORDER;2026-01-{(i % 28) + 1:02d};{ttc:.2f};{commission_ttc:.2f};"
            f"{commission_ht:.2f};{commission_tva:.2f};{net:.2f};"
            f"{product_ht:.2f};{tva_product:.2f};0.00;0.00"
        )
        payout_lines.append(f"{ref};ORDER;PAY-MM1;2026-01-31;{net:.2f}")

    (input_dir / "ca.csv").write_text("\n".join(ca_lines) + "\n", encoding="utf-8")
    (input_dir / "versements_manomano.csv").write_text("\n".join(payout_lines) + "\n", encoding="utf-8")


def _generate_decathlon_csvs(input_dir: Path, count: int) -> None:
    """Génère *count* commandes Décathlon (format Mirakl)."""
    lines: list[str] = [DECATHLON_HEADER]

    for i in range(1, count + 1):
        ref = f"PERF-DEC{i:04d}"
        montant = 90.0 + (i % 30)
        shipping = 8.0
        commission = round((montant + shipping) * 0.12, 2)
        paiement = round(montant + shipping - commission, 2)
        day = (i % 28) + 1

        lines.append(f"{ref};Montant;2026-01-{day:02d};2026-01-28;{montant:.2f}")
        lines.append(f"{ref};Frais de port;2026-01-{day:02d};2026-01-28;{shipping:.2f}")
        lines.append(f"{ref};Commission;2026-01-{day:02d};2026-01-28;-{commission:.2f}")
        lines.append(f"{ref};Taxe sur la commission;2026-01-{day:02d};2026-01-28;0.00")
        lines.append(f"{ref};Paiement;2026-01-{day:02d};2026-01-28;{paiement:.2f}")

    (input_dir / "decathlon_data.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Test de performance
# ---------------------------------------------------------------------------

NFR1_MAX_SECONDS = 30.0


@pytest.mark.slow
class TestPerformanceNFR1:
    """NFR1 — Le pipeline complet doit traiter ~400 transactions en moins de 30 s."""

    def test_pipeline_under_30_seconds(self, tmp_path: Path) -> None:
        """~400 transactions réparties sur 3 canaux → temps total < 30 s."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # ~400 transactions : 150 Shopify + 130 ManoMano + 120 Décathlon
        _generate_shopify_csvs(input_dir, count=150)
        _generate_manomano_csvs(input_dir, count=130)
        _generate_decathlon_csvs(input_dir, count=120)

        config = load_config(CONFIG_FIXTURES)
        output = tmp_path / "output.xlsx"

        orchestrator = PipelineOrchestrator()

        start = time.perf_counter()
        orchestrator.run(input_dir, output, config)
        elapsed = time.perf_counter() - start

        assert output.exists(), "Le fichier Excel de sortie n'a pas été produit"
        assert elapsed < NFR1_MAX_SECONDS, (
            f"NFR1 échoué : pipeline exécuté en {elapsed:.2f} s (limite : {NFR1_MAX_SECONDS} s)"
        )
