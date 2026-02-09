"""Tests d'intégration — POST /api/process."""

from __future__ import annotations

from pathlib import Path

from compta_ecom.config.loader import load_config
from compta_ecom.pipeline import PipelineOrchestrator


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_process_shopify_returns_200(client, shopify_files):
    """Upload Shopify → 200 avec entries, anomalies, summary."""
    response = client.post("/api/process", files=shopify_files)
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert "anomalies" in data
    assert "summary" in data
    assert len(data["entries"]) > 0


def test_process_shopify_entry_fields(client, shopify_files):
    """Chaque entrée contient les 10 champs attendus."""
    response = client.post("/api/process", files=shopify_files)
    data = response.json()
    expected_keys = {
        "date",
        "journal",
        "compte",
        "libelle",
        "debit",
        "credit",
        "piece",
        "lettrage",
        "canal",
        "type_ecriture",
    }
    for entry in data["entries"]:
        assert set(entry.keys()) == expected_keys


def test_process_shopify_anomaly_fields(client, shopify_files):
    """Chaque anomalie contient les 5 champs attendus."""
    response = client.post("/api/process", files=shopify_files)
    data = response.json()
    expected_keys = {"type", "severity", "canal", "reference", "detail"}
    for anomaly in data["anomalies"]:
        assert set(anomaly.keys()) == expected_keys


def test_process_shopify_summary_structure(client, shopify_files):
    """Le summary contient transactions_par_canal, ecritures_par_type, totaux."""
    response = client.post("/api/process", files=shopify_files)
    data = response.json()
    summary = data["summary"]
    assert "transactions_par_canal" in summary
    assert "ecritures_par_type" in summary
    assert "totaux" in summary
    assert "debit" in summary["totaux"]
    assert "credit" in summary["totaux"]


def test_process_shopify_balance(client, shopify_files):
    """Total débit == total crédit."""
    response = client.post("/api/process", files=shopify_files)
    data = response.json()
    totaux = data["summary"]["totaux"]
    assert totaux["debit"] == totaux["credit"]


def test_process_shopify_coherence_with_pipeline(client, shopify_files):
    """Le JSON retourné est cohérent avec run_from_buffers() directement."""
    # Via API
    response = client.post("/api/process", files=shopify_files)
    api_data = response.json()

    # Via pipeline directement
    config = load_config(FIXTURES / "config")
    files_dict = {
        "ventes.csv": (FIXTURES / "shopify" / "ventes.csv").read_bytes(),
        "transactions.csv": (FIXTURES / "shopify" / "transactions.csv").read_bytes(),
        "versements.csv": (FIXTURES / "shopify" / "versements.csv").read_bytes(),
    }
    pipeline = PipelineOrchestrator()
    entries, anomalies, summary = pipeline.run_from_buffers(files_dict, config)

    # Même nombre d'écritures
    assert len(api_data["entries"]) == len(entries)
    # Même nombre d'anomalies
    assert len(api_data["anomalies"]) == len(anomalies)
    # Mêmes totaux
    assert api_data["summary"]["totaux"]["debit"] == summary["totaux"]["debit"]
    assert api_data["summary"]["totaux"]["credit"] == summary["totaux"]["credit"]


def test_process_date_format_iso(client, shopify_files):
    """Les dates sont en format ISO YYYY-MM-DD."""
    response = client.post("/api/process", files=shopify_files)
    data = response.json()
    for entry in data["entries"]:
        # Format YYYY-MM-DD
        assert len(entry["date"]) == 10
        assert entry["date"][4] == "-"
        assert entry["date"][7] == "-"


def test_process_invalid_extension(client):
    """Un fichier non-CSV retourne 422."""
    files = [("files", ("data.txt", b"some content", "text/plain"))]
    response = client.post("/api/process", files=files)
    assert response.status_code == 422
    assert "csv" in response.json()["detail"].lower()


def test_process_no_channel_detected(client):
    """Fichier CSV inconnu (aucun canal) → 422."""
    files = [("files", ("inconnu.csv", b"col1,col2\nval1,val2", "text/csv"))]
    response = client.post("/api/process", files=files)
    assert response.status_code == 422


def test_process_too_many_files(client):
    """Plus de 20 fichiers → 422."""
    files = [("files", (f"file_{i}.csv", b"col1\nval1", "text/csv")) for i in range(21)]
    response = client.post("/api/process", files=files)
    assert response.status_code == 422
    assert "20" in response.json()["detail"]


def test_process_file_too_large(client):
    """Fichier > 10 MB → 413."""
    big_content = b"x" * (10 * 1024 * 1024 + 1)
    files = [("files", ("big.csv", big_content, "text/csv"))]
    response = client.post("/api/process", files=files)
    assert response.status_code == 413
