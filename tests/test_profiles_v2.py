"""Tests for profile pictures and public People search details."""

from io import BytesIO
from pathlib import Path
import ast

import pytest
from PIL import Image

import db
import logic


def make_image(format_name="PNG", size=(24, 18)):
    """Build a small valid image for profile-picture tests."""
    buffer = BytesIO()
    Image.new("RGB", size, (30, 100, 170)).save(buffer, format=format_name)
    return buffer.getvalue()


@pytest.fixture
def profile_db(tmp_path, monkeypatch):
    """Use an isolated local database for each profile test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "profiles.db")
    monkeypatch.setattr(db, "_database_url", lambda: None)
    db.close_connection()
    db.init_db()
    return db


def make_user(database, username, role="customer"):
    """Create a user and return the public user dictionary."""
    database.create_user(f"sub-{username}", f"{username}@example.com", username, role)
    return logic.find_google_user(database, f"sub-{username}")


def make_venue(database):
    """Create a small venue for the post metadata query."""
    return database.insert_venue({
        "name": "Park Bar", "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "yes", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue",
    })


@pytest.mark.parametrize(("format_name", "mime_type", "file_name"), [
    ("PNG", "image/png", "avatar.png"), ("JPEG", "image/jpeg", "avatar.jpg"),
])
def test_profile_picture_round_trips_and_is_resized_to_400_pixels(profile_db, format_name, mime_type, file_name):
    anna = make_user(profile_db, "anna")
    result = logic.set_profile_picture(profile_db, anna, make_image(format_name, size=(401, 200)), file_name)

    profile = logic.get_profile(profile_db, anna, anna["id"])
    avatar = logic.get_profile_avatar(profile_db, profile)
    image = Image.open(BytesIO(avatar["bytes"]))

    assert result.success
    assert avatar["mime_type"] == mime_type
    assert image.width == 400


def test_removing_profile_picture_uses_username_initial_fallback(profile_db):
    anna = make_user(profile_db, "anna")
    assert logic.set_profile_picture(profile_db, anna, make_image(), "avatar.png").success

    assert logic.remove_profile_picture(profile_db, anna).success
    avatar = logic.get_profile_avatar(profile_db, logic.get_profile(profile_db, anna, anna["id"]))

    assert avatar["bytes"] is None
    assert avatar["initial"] == "A"
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "border-radius:50%" in app_source


def test_replacing_profile_picture_updates_the_user_reference(profile_db):
    anna = make_user(profile_db, "anna")
    assert logic.set_profile_picture(profile_db, anna, make_image(), "first.png").success
    first_id = profile_db.get_profile_image_id(anna["id"])

    assert logic.set_profile_picture(profile_db, anna, make_image("JPEG"), "second.jpg").success
    second_id = profile_db.get_profile_image_id(anna["id"])

    assert second_id != first_id
    assert profile_db.get_image(first_id) is None
    assert logic.get_profile_avatar(profile_db, logic.get_profile(profile_db, anna, anna["id"]))["mime_type"] == "image/jpeg"


def test_profile_picture_at_five_megabytes_is_accepted(profile_db):
    anna = make_user(profile_db, "anna")
    image = make_image()
    exact_limit = image + b"\x00" * (5 * 1024 * 1024 - len(image))

    result = logic.set_profile_picture(profile_db, anna, exact_limit, "avatar.png")

    assert result.success
    assert profile_db.get_profile_image_id(anna["id"]) is not None


@pytest.mark.parametrize("format_name", ["GIF"])
def test_profile_picture_rejects_unsupported_types(profile_db, format_name):
    anna = make_user(profile_db, "anna")

    result = logic.set_profile_picture(profile_db, anna, make_image(format_name), "avatar." + format_name.lower())

    assert not result.success
    assert profile_db.get_profile_image_id(anna["id"]) is None


def test_profile_picture_rejects_more_than_five_megabytes(profile_db):
    anna = make_user(profile_db, "anna")
    image = make_image()
    oversized = image + b"\x00" * (5 * 1024 * 1024 + 1 - len(image))

    result = logic.set_profile_picture(profile_db, anna, oversized, "avatar.png")

    assert not result.success
    assert profile_db.get_profile_image_id(anna["id"]) is None


def test_profile_picture_is_available_in_search_posts_and_conversation_list(profile_db):
    anna = make_user(profile_db, "anna")
    ben = make_user(profile_db, "ben")
    assert logic.set_profile_picture(profile_db, anna, make_image(), "avatar.png").success
    venue_id = make_venue(profile_db)
    post_id = logic.create_post(profile_db, anna, venue_id, "Hello").post_id
    logic.start_direct_conversation(profile_db, ben, anna["id"])

    search_match = logic.search_people(profile_db, ben, "anna")[0]
    post = profile_db.get_user_posts(anna["id"])[0]
    conversation = logic.list_conversations(profile_db, ben)[0]

    assert search_match["image_id"] == post["author_image_id"] == profile_db.get_profile_image_id(anna["id"])
    assert conversation["other_image_id"] == search_match["image_id"]
    assert post["id"] == post_id
    assert "email" not in search_match
    assert logic.search_people(profile_db, ben, "anna@example.com") == []


def test_business_badge_is_textual_and_only_for_business_accounts():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    people_list = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                       and node.name == "show_person_list")
    source = ast.get_source_segment(app_path.read_text(encoding="utf-8"), people_list)

    assert 'person["role"] == "business"' in source
    assert '"Bar"' in source
    assert 'caption("Bar")' in source


@pytest.mark.parametrize(("format_name", "file_name"), [("HEIF", "IMG_1234.HEIC"), ("WEBP", "avatar.webp")])
def test_profile_picture_accepts_iphone_heic_and_webp_as_jpeg(profile_db, format_name, file_name):
    anna = make_user(profile_db, "anna")

    result = logic.set_profile_picture(profile_db, anna, make_image(format_name, size=(500, 500)), file_name)

    avatar = logic.get_profile_avatar(profile_db, logic.get_profile(profile_db, anna, anna["id"]))
    assert result.success
    assert avatar["mime_type"] == "image/jpeg"
    assert Image.open(BytesIO(avatar["bytes"])).width == 400
