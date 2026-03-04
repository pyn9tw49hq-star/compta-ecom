"""Tests — CORS hardening (#38)."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient


def _make_client(cors_env: str | None = None) -> TestClient:
    """Crée un TestClient avec CORS_ORIGINS configuré."""
    # Purge le module pour forcer la re-lecture de l'env var
    import importlib
    import sys

    config_dir = str(
        __import__("pathlib").Path(__file__).parent.parent / "fixtures" / "config"
    )
    os.environ["CONFIG_DIR"] = config_dir

    if cors_env is not None:
        os.environ["CORS_ORIGINS"] = cors_env
    elif "CORS_ORIGINS" in os.environ:
        del os.environ["CORS_ORIGINS"]

    # Force reload pour que le module relise os.getenv
    for mod_name in list(sys.modules):
        if mod_name.startswith("api.app"):
            del sys.modules[mod_name]

    from api.app.main import app

    return TestClient(app)


def test_cors_strips_spaces():
    """Les origines avec espaces sont correctement strippées."""
    client = _make_client(" https://a.com , https://b.com ")
    response = client.options(
        "/api/process",
        headers={
            "Origin": "https://a.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "https://a.com"


def test_cors_allows_configured_origin():
    """Une requête avec un Origin configuré reçoit Access-Control-Allow-Origin."""
    client = _make_client("https://myapp.vercel.app")
    response = client.options(
        "/api/process",
        headers={
            "Origin": "https://myapp.vercel.app",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://myapp.vercel.app"
    )


def test_cors_rejects_unknown_origin():
    """Une requête avec un Origin non configuré ne reçoit pas l'en-tête ACAO."""
    client = _make_client("https://allowed.com")
    response = client.options(
        "/api/process",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "https://evil.com"


def test_cors_default_localhost():
    """Sans CORS_ORIGINS, le défaut est http://localhost:3000."""
    client = _make_client(None)
    response = client.options(
        "/api/process",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    )


def test_cors_empty_entries_filtered():
    """Les entrées vides dans CORS_ORIGINS sont ignorées (virgule en trop)."""
    client = _make_client("https://a.com,,https://b.com,")
    response = client.options(
        "/api/process",
        headers={
            "Origin": "https://b.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "https://b.com"


def test_cors_options_returns_allowed_methods():
    """Le preflight OPTIONS retourne les méthodes autorisées."""
    client = _make_client("https://test.com")
    response = client.options(
        "/api/process",
        headers={
            "Origin": "https://test.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    allowed = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allowed
