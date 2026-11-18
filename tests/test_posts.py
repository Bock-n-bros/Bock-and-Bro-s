"""Tests for posts with photos, the feed and posts on venue and profile pages."""

from datetime import datetime, timedelta, timezone

import pytest

import db
import logic

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 100


@pytest.fixture
def post_db(tmp_path, monkeypatch):
    """Use an isolated database and uploads folder for every post test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "posts.db")
    monkeypatch.setattr(db, "UPLOADS_DIR", tmp_path / "uploads")
    db.init_db()
    return db


def make_user(database, username, role="customer"):
    """Create a profile and return the public user dictionary."""
    database.create_user(f"sub-{username}", f"{username}@example.com", username, role)
    return logic.find_google_user(database, f"sub-{username}")


def make_venue(database, name="Park Bar"):
    """Create a minimal venue and return its id."""
    return database.insert_venue({
        "name": name, "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "yes", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue",
    })


def at(minutes):
    """Return a fixed UTC time a number of minutes after a base time."""
    return datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def texts(posts):
    """Return just the text of each post."""
    return [post["text"] for post in posts]


def uploaded_files():
    """Return the files currently in the uploads folder."""
    return sorted(db.UPLOADS_DIR.glob("*")) if db.UPLOADS_DIR.exists() else []


def test_customer_and_bar_owner_can_post_with_photo(post_db):
    anna = make_user(post_db, "anna")
    bar = make_user(post_db, "parkbar", role="business")
    park = make_venue(post_db)

    first = logic.create_post(post_db, anna, park, "Sunset Super Bock", PNG, "view.PNG")
    second = logic.create_post(post_db, bar, park, "Benfica tonight at 20:00", JPG, "match.jpg")

    assert first.success and second.success
    posts = logic.get_venue_posts(post_db, park)
    assert {post["username"] for post in posts} == {"anna", "parkbar"}
    assert {post["role"] for post in posts} == {"customer", "business"}
    assert len(uploaded_files()) == 2
    image = post_db.get_image_file(posts[0]["image_path"])
    assert image is not None and image.read_bytes() in (PNG, JPG)


def test_text_only_photo_only_and_webp_are_allowed(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)

    assert logic.create_post(post_db, anna, park, "Just text").success
    assert logic.create_post(post_db, anna, park, "", WEBP, "pic.webp").success
    assert post_db.count_posts() == 2


@pytest.mark.parametrize(
    ("text", "image", "name"),
    [
        ("", None, None),                       # empty post
        ("   ", None, None),                    # only spaces
        ("x" * 501, None, None),                # too long
        ("Hi", b"GIF89a" + b"\x00" * 50, "anim.gif"),   # wrong type
        ("Hi", b"not an image at all", "fake.png"),      # renamed file
        ("Hi", b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024), "big.jpg"),  # over 5 MB
    ],
)
def test_invalid_posts_are_refused_and_nothing_is_saved(post_db, text, image, name):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)

    result = logic.create_post(post_db, anna, park, text, image, name)

    assert not result.success
    assert post_db.count_posts() == 0
    assert uploaded_files() == []


def test_post_must_have_an_existing_venue(post_db):
    anna = make_user(post_db, "anna")

    assert not logic.create_post(post_db, anna, None, "Where am I?").success
    assert not logic.create_post(post_db, anna, 9999, "Where am I?").success
    assert post_db.count_posts() == 0


def test_logged_out_user_cannot_post(post_db):
    park = make_venue(post_db)

    assert not logic.create_post(post_db, None, park, "Hello").success
    assert post_db.count_posts() == 0


def test_text_is_trimmed_and_500_characters_is_allowed(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)

    logic.create_post(post_db, anna, park, "  cheers  ", now=at(1))
    assert logic.create_post(post_db, anna, park, "y" * 500, now=at(2)).success

    assert texts(logic.get_user_posts(post_db, anna["id"])) == ["y" * 500, "cheers"]


def test_feed_shows_own_followed_people_and_followed_bars_newest_first(post_db):
    anna = make_user(post_db, "anna")
    ben = make_user(post_db, "ben")
    cleo = make_user(post_db, "cleo")
    park = make_venue(post_db, "Park Bar")
    other = make_venue(post_db, "Other Bar")
    logic.follow_user(post_db, anna, ben["id"])
    logic.follow_venue(post_db, anna, park)

    logic.create_post(post_db, anna, other, "mine", now=at(1))
    logic.create_post(post_db, ben, other, "from ben", now=at(2))
    logic.create_post(post_db, cleo, park, "cleo at a bar anna follows", now=at(3))
    logic.create_post(post_db, cleo, other, "cleo elsewhere", now=at(4))

    assert texts(logic.get_feed(post_db, anna)) == [
        "cleo at a bar anna follows", "from ben", "mine",
    ]


def test_feed_of_someone_who_follows_nobody_shows_only_own_posts(post_db):
    anna = make_user(post_db, "anna")
    ben = make_user(post_db, "ben")
    park = make_venue(post_db)
    logic.create_post(post_db, ben, park, "ben's post")

    assert logic.get_feed(post_db, anna) == []
    assert logic.get_feed(post_db, None) == []


def test_unfollowing_removes_posts_from_feed(post_db):
    anna = make_user(post_db, "anna")
    ben = make_user(post_db, "ben")
    park = make_venue(post_db)
    logic.follow_user(post_db, anna, ben["id"])
    logic.create_post(post_db, ben, park, "hello")

    logic.unfollow_user(post_db, anna, ben["id"])

    assert logic.get_feed(post_db, anna) == []


def test_post_shows_venue_name_and_no_email(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db, "Park Bar")
    logic.create_post(post_db, anna, park, "**bold** <b>hi</b>")

    post = logic.get_venue_posts(post_db, park)[0]

    assert post["venue_name"] == "Park Bar"
    assert post["text"] == "**bold** <b>hi</b>"
    assert "example.com" not in str(post)


def test_image_lookup_cannot_leave_the_uploads_folder(post_db):
    assert post_db.get_image_file("../posts.db") is None
    assert post_db.get_image_file(None) is None


def test_post_time_is_shown_in_lisbon_time():
    assert logic.format_post_time("2026-07-18T20:30:00+00:00") == "18 Jul 2026, 21:30"
