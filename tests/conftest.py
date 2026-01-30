from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Chemin vers le répertoire de fixtures."""
    return Path(__file__).parent / "fixtures"
