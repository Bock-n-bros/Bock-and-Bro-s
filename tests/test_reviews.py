"""Tests for review permissions, validation, storage, summaries, and sorting."""

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

import db
import logic


def test_app_does_not_import_or_call_db():
    """Keep database access behind logic functions."""
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    assert not any(
        (isinstance(node, ast.Import) and any(alias.name == "db" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "db")
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "db"
        for node in ast.walk(tree)
    )


def test_old_session_without_user_id_is_invalid():
    assert not logic.has_valid_session_user({"username": "Alice", "role": "customer"})
    assert logic.has_valid_session_user({"id": 1, "username": "Alice", "role": "customer"})


@pytest.mark.parametrize(
    ("created_at", "updated_at", "expected"),
    [
        ("2026-11-08T21:12:37.069531+00:00", "2026-11-08T21:12:37.069531+00:00", "8 Nov 2026"),
        ("2026-11-07T21:12:37+00:00", "2026-11-08T21:12:37+00:00", "Updated 8 Nov 2026"),
    ],
)
def test_review_date_display(created_at, updated_at, expected):
    assert logic.format_review_date({"created_at": created_at, "updated_at": updated_at}) == expected


@pytest.fixture
def review_db(tmp_path, monkeypatch):
    """Use an isolated database for every review test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "reviews.db")
    db.init_db()
    return db


def make_venue(database, name="Demo Bar", **changes):
    """Create and return a minimal test venue."""
    venue = {
        "name": name,
        "neighbourhood": "Bairro Alto",
        "address": "1 Test Street",
        "venue_type": "bar",
        "shows_football": "yes",
        "latitude": 38.72,
        "longitude": -9.14,
        "description": "Test venue",
    }
    venue.update(changes)
    return database.insert_venue(venue)


def make_user(database, username, role="customer"):
    """Create and return a test user."""
    return database.create_user(username, "not-a-real-password-hash", role)


def review(**changes):
    """Return a valid review with selected fields changed."""
    values = {"atmosphere": 3, "value": 3, "quality": 3,
              "super_bock_price": None, "comment": "Good place"}
    values.update(changes)
    return values


def submit(database, user, venue_id, **changes):
    """Submit a review using a user session dictionary."""
    return logic.submit_review(database, user, venue_id, **review(**changes))


def test_customer_can_submit_review(review_db):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    result = submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id)
    assert result.success
    assert review_db.count_reviews(venue_id) == 1


@pytest.mark.parametrize("user", [{"id": 1, "username": "Biz", "role": "business"}, None])
def test_non_customer_cannot_submit_review(review_db, user):
    venue_id = make_venue(review_db)
    result = submit(review_db, user, venue_id)
    assert not result.success
    assert review_db.count_reviews(venue_id) == 0


@pytest.mark.parametrize("field", ["atmosphere", "value", "quality"])
@pytest.mark.parametrize("score", [1, 5])
def test_scores_accept_integer_boundaries(review_db, field, score):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    assert submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
                  **{field: score}).success


@pytest.mark.parametrize("field", ["atmosphere", "value", "quality"])
@pytest.mark.parametrize("score", [0, 6, 2.5, "bad"])
def test_scores_reject_out_of_range_or_non_whole_values(review_db, field, score):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    result = submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
                    **{field: score})
    assert not result.success
    assert review_db.count_reviews(venue_id) == 0


@pytest.mark.parametrize("price", [None, 0.50, 10.00])
def test_price_accepts_optional_and_boundary_values(review_db, price):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    assert submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
                  super_bock_price=price).success


@pytest.mark.parametrize("price", [0.20, 15.00])
def test_price_rejects_values_outside_range(review_db, price):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    result = submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
                    super_bock_price=price)
    assert not result.success
    assert review_db.count_reviews(venue_id) == 0


@pytest.mark.parametrize("comment", [None, "x" * 500])
def test_comment_accepts_optional_and_500_characters(review_db, comment):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    assert submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
                  comment=comment).success


def test_comment_rejects_501_characters(review_db):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    result = submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
                    comment="x" * 501)
    assert not result.success
    assert review_db.count_reviews(venue_id) == 0


def test_comment_is_trimmed(review_db):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
           comment="  Nice  ")
    assert review_db.get_user_review(user_id, venue_id)["comment"] == "Nice"


def test_fetches_current_users_review(review_db):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
           comment="My review")
    assert review_db.get_user_review(user_id, venue_id)["comment"] == "My review"


def test_review_persists_after_database_reopen(review_db, monkeypatch, tmp_path):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
           comment="Still here")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "reviews.db")
    db.init_db()
    assert db.get_user_review(user_id, venue_id)["comment"] == "Still here"


def test_comment_markup_is_stored_and_returned_exactly(review_db):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    comment = "**bold** <b>hi</b>"
    submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, venue_id,
           comment=comment)
    assert review_db.get_user_review(user_id, venue_id)["comment"] == comment


def test_unknown_venue_is_rejected_without_saving(review_db):
    user_id = make_user(review_db, "Alice")
    result = submit(review_db, {"id": user_id, "username": "Alice", "role": "customer"}, 999)
    assert not result.success
    assert review_db.count_reviews() == 0


def test_reviews_fetch_with_username_and_newest_first(review_db):
    venue_id = make_venue(review_db)
    alice = make_user(review_db, "Alice")
    bob = make_user(review_db, "Bob")
    review_db.save_review(venue_id, alice, review(), "2026-01-01T12:00:00+00:00")
    review_db.save_review(venue_id, bob, review(), "2026-01-02T12:00:00+00:00")
    rows = review_db.get_reviews_for_venue(venue_id)
    assert [row["username"] for row in rows] == ["Bob", "Alice"]


def test_two_customers_have_independent_reviews(review_db):
    venue_id = make_venue(review_db)
    alice = make_user(review_db, "Alice")
    bob = make_user(review_db, "Bob")
    assert submit(review_db, {"id": alice, "username": "Alice", "role": "customer"}, venue_id,
                  comment="Alice's review").success
    assert submit(review_db, {"id": bob, "username": "Bob", "role": "customer"}, venue_id,
                  comment="Bob's review").success
    assert review_db.count_reviews(venue_id) == 2
    submit(review_db, {"id": alice, "username": "Alice", "role": "customer"}, venue_id,
           comment="Alice updated")
    assert review_db.get_user_review(bob, venue_id)["comment"] == "Bob's review"
    assert review_db.count_reviews(venue_id) == 2


def test_review_update_preserves_created_at_and_changes_updated_at(review_db):
    venue_id = make_venue(review_db)
    user_id = make_user(review_db, "Alice")
    user = {"id": user_id, "username": "Alice", "role": "customer"}
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    updated = datetime(2026, 1, 2, tzinfo=timezone.utc)
    logic.submit_review(review_db, user, venue_id, **review(), now=created)
    logic.submit_review(review_db, user, venue_id, **review(comment="Updated"), now=updated)
    saved = review_db.get_user_review(user_id, venue_id)
    assert saved["created_at"] == created.isoformat()
    assert saved["updated_at"] == updated.isoformat()


def test_review_summary_averages_and_counts(review_db):
    venue_id = make_venue(review_db)
    alice, bob = make_user(review_db, "Alice"), make_user(review_db, "Bob")
    review_db.save_review(venue_id, alice, review(atmosphere=4, value=3, quality=5, super_bock_price=2.00))
    review_db.save_review(venue_id, bob, review(atmosphere=5, value=4, quality=4, super_bock_price=None))
    summary = review_db.get_review_summary(venue_id)
    assert summary == {"atmosphere": 4.5, "value": 3.5, "quality": 4.5,
                       "overall": 4.2, "review_count": 2, "average_super_bock_price": 2.00}


def test_overall_rounds_from_unrounded_category_averages(review_db):
    venue_id = make_venue(review_db)
    user_ids = [make_user(review_db, f"User{i}") for i in range(100)]
    for index, user_id in enumerate(user_ids):
        # Exact means are 1.25, 1.25, and 1.46. Rounding each first gives
        # 1.3, 1.3, and 1.5, whose average rounds to 1.4 instead of 1.3.
        atmosphere = 1 if index < 75 else 2
        value = 1 if index < 75 else 2
        quality = 1 if index < 54 else 2
        review_db.save_review(venue_id, user_id, review(atmosphere=atmosphere, value=value, quality=quality))
    summary = review_db.get_review_summary(venue_id)
    assert summary["overall"] == 1.3


def test_summary_without_reviews_has_no_scores(review_db):
    venue_id = make_venue(review_db)
    summary = review_db.get_review_summary(venue_id)
    assert summary["overall"] is None
    assert summary["review_count"] == 0
    assert summary["average_super_bock_price"] is None


@pytest.mark.parametrize(
    ("sort_by", "expected"),
    [
        ("name", ["Alpha", "Bravo", "Charlie", "Zulu"]),
        ("overall", ["Bravo", "Alpha", "Charlie", "Zulu"]),
        ("atmosphere", ["Bravo", "Alpha", "Charlie", "Zulu"]),
        ("price", ["Bravo", "Alpha", "Charlie", "Zulu"]),
        ("reviews", ["Bravo", "Alpha", "Charlie", "Zulu"]),
    ],
)
def test_sort_options_and_missing_data_last(review_db, sort_by, expected):
    ids = {name: make_venue(review_db, name) for name in ["Zulu", "Alpha", "Charlie", "Bravo"]}
    alice, bob = make_user(review_db, "Alice"), make_user(review_db, "Bob")
    # Bravo: strongest/highest count, Alpha: next, Charlie: no price, Zulu: no reviews.
    review_db.save_review(ids["Bravo"], alice, review(atmosphere=5, value=5, quality=5, super_bock_price=1.00))
    review_db.save_review(ids["Bravo"], bob, review(atmosphere=5, value=5, quality=5, super_bock_price=1.00))
    review_db.save_review(ids["Alpha"], alice, review(atmosphere=4, value=4, quality=4, super_bock_price=2.00))
    review_db.save_review(ids["Charlie"], bob, review(atmosphere=3, value=3, quality=3))
    assert [v["name"] for v in logic.sort_venues(review_db.get_all_venues(), review_db, sort_by)] == expected


def test_sort_applies_after_filters(review_db):
    low = make_venue(review_db, "Alpha Bar")
    high = make_venue(review_db, "Zulu Bar")
    make_venue(review_db, "Filtered Cafe", venue_type="café")
    user_id = make_user(review_db, "Alice")
    review_db.save_review(low, user_id, review(atmosphere=2, value=2, quality=2))
    review_db.save_review(high, user_id, review(atmosphere=5, value=5, quality=5))
    results = logic.find_venues(review_db, venue_type="bar", sort_by="overall")
    assert [venue["name"] for venue in results] == ["Zulu Bar", "Alpha Bar"]
