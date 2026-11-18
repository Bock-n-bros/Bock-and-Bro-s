"""Add missing seed venues to the local database."""

from pathlib import Path

import db
import logic


VENUES_CSV = Path(__file__).resolve().parent / "data" / "venues.csv"


def load_demo_venues():
    """Add CSV venues whose names are not already stored."""
    return logic.load_venues(db, VENUES_CSV)


if __name__ == "__main__":
    db.init_db()
    loaded = load_demo_venues()
    print(f"Database is ready. Loaded {loaded} venues.")
