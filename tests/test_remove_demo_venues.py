"""Tests for the one-off demo venue cleanup script."""

import pytest

import db
import logic
import remove_demo_venues


@pytest.fixture
def cleanup_db(tmp_path, monkeypatch):
    """Always run cleanup tests against a disposable SQLite database."""
    db.close_connection()
    monkeypatch.setattr(db, "_database_url", lambda: None)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "cleanup.db")
    monkeypatch.setattr(db, "_initialized_key", None)
    db.init_db()
    assert db._backend()[0] == "sqlite"
    yield db
    db.close_connection()


def venue(name):
    """Build a minimal valid venue row."""
    return {
        "name": name, "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "no", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue.",
    }


def test_script_deletes_only_unreferenced_demo_venues(cleanup_db, capsys):
    empty_id = cleanup_db.insert_venue(venue("Demo Empty"))
    reviewed_id = cleanup_db.insert_venue(venue("Demo Reviewed"))
    followed_id = cleanup_db.insert_venue(venue("Demo Followed"))
    non_demo_id = cleanup_db.insert_venue(venue("The Demo Room"))
    no_space_id = cleanup_db.insert_venue(venue("DemoRoom"))
    reviewer = cleanup_db.create_user(
        "reviewer-sub", "reviewer@example.com", "reviewer", "customer"
    )
    follower = cleanup_db.create_user(
        "follower-sub", "follower@example.com", "follower", "customer"
    )
    cleanup_db.save_review(reviewed_id, reviewer, {
        "atmosphere": 4, "value": 4, "quality": 4,
        "super_bock_price": None, "comment": None,
    })
    cleanup_db.add_venue_follow(follower, followed_id)

    remove_demo_venues.main()

    names_left = {venue_row["name"] for venue_row in cleanup_db.get_all_venues()}
    assert empty_id not in {row["id"] for row in cleanup_db.get_all_venues()}
    assert names_left == {
        "Demo Reviewed", "Demo Followed", "The Demo Room", "DemoRoom",
    }
    assert capsys.readouterr().out.strip() == "Deleted: Demo Empty"


def test_seed_csv_contains_no_demo_venues():
    from pathlib import Path

    csv_path = Path(__file__).resolve().parents[1] / "data" / "venues.csv"
    rows, errors = logic.validate_venues_csv(csv_path)

    assert errors == []
    assert all(not row["name"].startswith("Demo ") for row in rows)
