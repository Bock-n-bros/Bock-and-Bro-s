"""Keep pytest temporary files inside the project workspace."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def use_local_database(monkeypatch):
    """Keep the complete test suite independent from any configured Supabase URL."""
    import db
    monkeypatch.setattr(db, "_database_url", lambda: None)
    db.close_connection()


@pytest.fixture
def tmp_path(request):
    """Provide an automatically cleaned temporary directory for a test."""
    with tempfile.TemporaryDirectory(
        prefix="test-", dir=Path(__file__).resolve().parents[1]
    ) as directory:
        try:
            yield Path(directory)
        finally:
            import db
            db.close_connection()
