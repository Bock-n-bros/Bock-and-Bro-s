"""Seed venue data when the venues table is empty."""

from pathlib import Path

import db
import logic


VENUES_CSV = Path(__file__).resolve().parent / "data" / "venues.csv"


def load_demo_venues():
    """Load CSV venues only into an empty venues table."""
    return logic.load_venues(db, VENUES_CSV)


if __name__ == "__main__":
    db.init_db()
    loaded = load_demo_venues()
    print(f"Database is ready. Loaded {loaded} venues.")
