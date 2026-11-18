"""Tests for community photos on venue pages."""

from datetime import datetime, timezone
from io import BytesIO
import ast
from pathlib import Path

from PIL import Image

import db
import logic


def make_image():
    """Return a small valid PNG image."""
    output = BytesIO()
    Image.new("RGB", (8, 6), (12, 34, 56)).save(output, format="PNG")
    return output.getvalue()


def make_user(database, username):
    """Create a user and return its public profile."""
    database.create_user(f"sub-{username}", f"{username}@example.com", username, "customer")
    return logic.find_google_user(database, f"sub-{username}")


def make_venue(database, name):
    """Create a venue and return its id."""
    return database.insert_venue({
        "name": name, "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "yes", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue",
    })


def test_community_photos_only_include_tagged_images_and_omit_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "photos.db")
    db.init_db()
    user = make_user(db, "anna")
    park = make_venue(db, "Park Bar")
    cafe = make_venue(db, "Cafe")
    photo = make_image()
    logic.create_post(db, user, park, "park photo", photo, "park.png")
    logic.create_post(db, user, cafe, "cafe photo", photo, "cafe.png")
    logic.create_post(db, user, park, "text only")

    posts = logic.get_venue_community_photos(db, park)

    assert [post["text"] for post in posts] == ["park photo"]
    assert posts[0]["username"] == "anna"
    assert posts[0]["image_id"] is not None
    assert "bytes" not in posts[0]
    assert "image_bytes" not in posts[0]


def test_community_photos_are_newest_first_and_limited_to_twelve(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "photos.db")
    db.init_db()
    user = make_user(db, "anna")
    venue = make_venue(db, "Park Bar")
    image = make_image()
    for index in range(13):
        logic.create_post(db, user, venue, str(index), image, "photo.png",
                          now=datetime(2026, 11, 18, 20, index, tzinfo=timezone.utc))

    posts = logic.get_venue_community_photos(db, venue)

    assert len(posts) == 12
    assert posts[0]["text"] == "12"
    assert posts[-1]["text"] == "1"
    assert posts[0]["created_at"]


def test_community_photos_do_not_change_review_average(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "photos.db")
    db.init_db()
    user = make_user(db, "anna")
    venue = make_venue(db, "Park Bar")
    review = {"atmosphere": 4, "value": 3, "quality": 5,
              "super_bock_price": None, "comment": "Nice"}
    logic.submit_review(db, user, venue, **review)
    before = logic.get_venue_review_summary(venue)

    logic.create_post(db, user, venue, "community photo", make_image(), "photo.png")

    after = logic.get_venue_review_summary(venue)
    assert after == before


def test_community_photo_lookup_is_empty_when_venue_has_no_images(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "photos.db")
    db.init_db()
    user = make_user(db, "anna")
    venue = make_venue(db, "Park Bar")
    logic.create_post(db, user, venue, "text only")

    assert logic.get_venue_community_photos(db, venue) == []


def test_venue_photo_section_returns_before_rendering_when_empty():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    renderer = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "show_venue_community_photos")
    guard = next(node for node in renderer.body if isinstance(node, ast.If))

    assert isinstance(guard, ast.If)
    assert "not photos" in ast.unparse(guard.test)
    assert isinstance(guard.body[0], ast.Return)


def test_community_photo_post_query_does_not_load_image_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "photos.db")
    db.init_db()
    user = make_user(db, "anna")
    venue = make_venue(db, "Park Bar")
    logic.create_post(db, user, venue, "photo", make_image(), "photo.png")
    called = []
    monkeypatch.setattr(db, "get_post_image", lambda image_id: called.append(image_id))

    posts = logic.get_venue_community_photos(db, venue)

    assert posts[0]["image_id"] is not None
    assert called == []
