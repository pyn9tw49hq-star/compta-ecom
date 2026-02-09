"""Fixtures pour les tests d'intégration API."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """TestClient FastAPI avec configuration de test."""
    config_dir = str(Path(__file__).parent.parent / "fixtures" / "config")
    os.environ["CONFIG_DIR"] = config_dir

    from api.app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def shopify_files() -> list[tuple[str, tuple[str, bytes, str]]]:
    """Fichiers Shopify pour upload multipart."""
    fixtures = Path(__file__).parent.parent / "fixtures" / "shopify"
    return [
        ("files", ("ventes.csv", (fixtures / "ventes.csv").read_bytes(), "text/csv")),
        ("files", ("transactions.csv", (fixtures / "transactions.csv").read_bytes(), "text/csv")),
        ("files", ("versements.csv", (fixtures / "versements.csv").read_bytes(), "text/csv")),
    ]
