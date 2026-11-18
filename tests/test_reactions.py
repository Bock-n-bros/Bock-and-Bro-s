"""Tests for post comments and likes."""

import inspect
from pathlib import Path

import pytest

import db
import logic


@pytest.fixture
def reaction_db(tmp_path, monkeypatch):
    """Create an isolated database for each reactions test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "reactions.db")
    monkeypatch.setattr(db, "_database_url", lambda: None)
    db.init_db()
    return db


def make_user(database, name, role="customer"):
    """Create a test user and return its public profile."""
    database.create_user(f"sub-{name}", f"{name}@example.com", name, role)
    return logic.find_google_user(database, f"sub-{name}")


def make_post(database, user, text="A post"):
    """Create a post at a test venue and return its id."""
    venue_id = database.insert_venue({
        "name": "Park Bar", "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "yes", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue",
    })
    result = logic.create_post(database, user, venue_id, text)
    assert result.success
    return result.post_id


def test_comments_accept_500_characters_and_reject_501(reaction_db):
    user = make_user(reaction_db, "anna")
    post_id = make_post(reaction_db, user)

    accepted = logic.add_comment(reaction_db, user, post_id, "x" * 500)
    rejected = logic.add_comment(reaction_db, user, post_id, "x" * 501)

    assert accepted.success
    assert not rejected.success
    assert reaction_db.count_comments(post_id) == 1


def test_comments_are_oldest_first_with_author_role_and_plain_text(reaction_db):
    anna = make_user(reaction_db, "anna")
    business = make_user(reaction_db, "parkbar", "business")
    post_id = make_post(reaction_db, anna)
    exact_text = "**stjerner** <b>html</b>"

    logic.add_comment(reaction_db, business, post_id, exact_text, now="2026-11-18T10:00:00+00:00")
    logic.add_comment(reaction_db, anna, post_id, "Second", now="2026-11-18T10:01:00+00:00")
    comments = logic.get_comments(reaction_db, post_id)

    assert [comment["text"] for comment in comments] == [exact_text, "Second"]
    assert comments[0]["username"] == "parkbar"
    assert comments[0]["role"] == "business"
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'st.text(comment["text"])' in app_source


def test_comment_author_can_delete_but_other_users_cannot(reaction_db):
    anna = make_user(reaction_db, "anna")
    ben = make_user(reaction_db, "ben")
    post_id = make_post(reaction_db, anna)
    comment_id = logic.add_comment(reaction_db, anna, post_id, "Cheers").comment_id

    denied = logic.delete_comment(reaction_db, ben, comment_id)
    assert not denied.success
    assert reaction_db.count_comments(post_id) == 1
    assert logic.delete_comment(reaction_db, anna, comment_id).success
    assert reaction_db.count_comments(post_id) == 0


def test_business_users_can_comment_and_like(reaction_db):
    author = make_user(reaction_db, "anna")
    business = make_user(reaction_db, "parkbar", "business")
    post_id = make_post(reaction_db, author)

    assert logic.add_comment(reaction_db, business, post_id, "Open tonight").success
    assert logic.toggle_like(reaction_db, business, post_id).liked


def test_like_toggles_off_and_database_rejects_duplicate_rows(reaction_db):
    anna = make_user(reaction_db, "anna")
    post_id = make_post(reaction_db, anna)

    assert logic.toggle_like(reaction_db, anna, post_id).liked
    with pytest.raises(db.DuplicateRecordError):
        reaction_db.add_like(post_id, anna["id"])
    assert reaction_db.count_likes(post_id) == 1
    assert not logic.toggle_like(reaction_db, anna, post_id).liked
    assert reaction_db.count_likes(post_id) == 0


def test_feed_shows_python_like_count_and_current_user_state(reaction_db):
    anna = make_user(reaction_db, "anna")
    ben = make_user(reaction_db, "ben")
    post_id = make_post(reaction_db, anna)
    logic.toggle_like(reaction_db, anna, post_id)
    logic.toggle_like(reaction_db, ben, post_id)

    feed_post = logic.get_feed(reaction_db, anna)[0]

    assert feed_post["like_count"] == 2
    assert feed_post["liked_by_me"] is True
    assert "GROUP BY" not in inspect.getsource(db.get_likes_for_posts).upper()


def test_empty_comment_and_comment_on_unknown_post_are_refused(reaction_db):
    anna = make_user(reaction_db, "anna")
    post_id = make_post(reaction_db, anna)

    assert not logic.add_comment(reaction_db, anna, post_id, "   ").success
    assert not logic.add_comment(reaction_db, anna, 999999, "Hello").success
    assert reaction_db.count_comments(post_id) == 0
