"""Tests d'intégration API — validation des paramètres date_from/date_to."""

from __future__ import annotations


def test_api_date_validation_422_missing_date_to(client, shopify_files):
    """date_from sans date_to → 422."""
    response = client.post(
        "/api/process",
        files=shopify_files,
        data={"date_from": "2026-01-01"},
    )
    assert response.status_code == 422
    assert "ensemble" in response.json()["detail"]


def test_api_date_validation_422_missing_date_from(client, shopify_files):
    """date_to sans date_from → 422."""
    response = client.post(
        "/api/process",
        files=shopify_files,
        data={"date_to": "2026-01-31"},
    )
    assert response.status_code == 422
    assert "ensemble" in response.json()["detail"]


def test_api_date_from_after_to_422(client, shopify_files):
    """date_from > date_to → 422."""
    response = client.post(
        "/api/process",
        files=shopify_files,
        data={"date_from": "2026-02-01", "date_to": "2026-01-01"},
    )
    assert response.status_code == 422
    assert "antérieure" in response.json()["detail"]


def test_api_date_invalid_format_422(client, shopify_files):
    """Format de date invalide → 422."""
    response = client.post(
        "/api/process",
        files=shopify_files,
        data={"date_from": "not-a-date", "date_to": "2026-01-31"},
    )
    assert response.status_code == 422
    assert "YYYY-MM-DD" in response.json()["detail"]


def test_api_date_filter_returns_200(client, shopify_files):
    """Filtre de date valide → 200."""
    response = client.post(
        "/api/process",
        files=shopify_files,
        data={"date_from": "2026-01-01", "date_to": "2026-12-31"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert len(data["entries"]) > 0


def test_api_download_excel_with_dates(client, shopify_files):
    """/api/download/excel avec date_from/date_to → 200 et contenu xlsx."""
    response = client.post(
        "/api/download/excel",
        files=shopify_files,
        data={"date_from": "2026-01-01", "date_to": "2026-12-31"},
    )
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert len(response.content) > 0
