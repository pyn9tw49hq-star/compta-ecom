from pathlib import Path

import pytest

from compta_ecom.config.loader import AppConfig, ChannelConfig, DirectPaymentConfig, PspConfig


@pytest.fixture
def fixtures_dir() -> Path:
    """Chemin vers le répertoire de fixtures."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_config() -> AppConfig:
    """AppConfig valide minimale pour les tests."""
    config = AppConfig(
        clients={"shopify": "411SHOPIFY", "manomano": "411MANO"},
        fournisseurs={"manomano": "FMANO"},
        psp={
            "card": PspConfig(compte="51150007", commission="62700002"),
            "paypal": PspConfig(compte="51150004", commission="62700001"),
            "klarna": PspConfig(compte="51150011", commission="62700003"),
        },
        transit="58000000",
        banque="51200000",
        comptes_speciaux={"ADJUSTMENT": "51150002"},
        comptes_vente_prefix="707",
        canal_codes={"shopify": "01", "manomano": "02"},
        comptes_tva_prefix="4457",
        comptes_port_prefix="7085",
        zones_port={"france": "00", "hors_ue": "01", "ue": "02"},
        vat_table={
            "250": {"name": "France", "rate": 20.0, "alpha2": "FR"},
            "276": {"name": "Allemagne", "rate": 19.0, "alpha2": "DE"},
            "380": {"name": "Italie", "rate": 22.0, "alpha2": "IT"},
        },
        alpha2_to_numeric={"FR": "250", "DE": "276", "IT": "380"},
        channels={
            "shopify": ChannelConfig(
                files={"sales": "Ventes Shopify*.csv"},
                encoding="utf-8",
                separator=",",
            ),
            "manomano": ChannelConfig(
                files={"ca": "CA Manomano*.csv", "payouts": "Detail versement Manomano*.csv"},
                encoding="utf-8",
                separator=";",
                default_country_code="250",
            ),
        },
    )
    config.clients["decathlon"] = "CDECATHLON"
    config.clients["leroy_merlin"] = "411LM"
    config.fournisseurs["decathlon"] = "FDECATHLON"
    config.fournisseurs["leroy_merlin"] = "FADEO"
    config.canal_codes["decathlon"] = "03"
    config.canal_codes["leroy_merlin"] = "04"
    config.channels["decathlon"] = ChannelConfig(
        files={"data": "Decathlon*.csv"},
        encoding="utf-8",
        separator=";",
        default_country_code="250",
        commission_vat_rate=0.0,
        amounts_are_ttc=True,
    )
    config.channels["leroy_merlin"] = ChannelConfig(
        files={"data": "Leroy Merlin*.csv"},
        encoding="utf-8",
        separator=";",
        default_country_code="250",
        commission_vat_rate=20.0,
    )
    config.comptes_charges_marketplace = {
        "decathlon": {"commission": "62220800", "abonnement": "61311112"},
        "leroy_merlin": {"commission": "62220900", "abonnement": "61311113", "tva_deductible": "44566001"},
    }
    config.direct_payments = {
        "klarna": DirectPaymentConfig(compte="46740000", sales_payment_method="Klarna"),
        "bank_deposit": DirectPaymentConfig(compte="58010000", sales_payment_method="Bank Deposit"),
    }
    return config
