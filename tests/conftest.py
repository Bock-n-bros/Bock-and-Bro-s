"""Keep pytest temporary files inside the project workspace."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path(request):
    """Provide an automatically cleaned temporary directory for a test."""
    with tempfile.TemporaryDirectory(
        prefix="test-", dir=Path(__file__).resolve().parents[1]
    ) as directory:
        yield Path(directory)
