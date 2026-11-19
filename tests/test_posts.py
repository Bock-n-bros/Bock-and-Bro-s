"""Tests for posts with photos, the feed and posts on venue and profile pages."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest

import db
import logic

from PIL import Image


def image_bytes(format_name="PNG", size=(8, 6), color=(20, 80, 120)):
    """Create a small valid image for upload tests."""
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=format_name)
    return buffer.getvalue()


PNG = image_bytes()
JPG = image_bytes("JPEG")


@pytest.fixture
def post_db(tmp_path, monkeypatch):
    """Use an isolated database for every post test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "posts.db")
    monkeypatch.setattr(db, "_database_url", lambda: None)
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
    fetched = post_db.get_post_image(posts[0]["image_id"])
    assert fetched["mime_type"] in ("image/png", "image/jpeg")
    assert fetched["bytes"]


def test_text_only_and_photo_only_posts_work_and_webp_is_accepted(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)

    text_result = logic.create_post(post_db, anna, park, "Just text")
    photo_result = logic.create_post(post_db, anna, park, "", PNG, "pic.png")
    assert text_result.success
    assert photo_result.success
    assert post_db.get_user_posts(anna["id"])[1]["image_id"] is None
    webp_result = logic.create_post(post_db, anna, park, "", image_bytes("WEBP"), "pic.webp")
    assert webp_result.success
    assert post_db.count_posts() == 3


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
    assert post_db.count_images() == 0


def test_image_mime_and_bytes_round_trip_including_null_bytes(post_db, monkeypatch):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)
    original = image_bytes(color=(0, 0, 0))
    assert original.count(b"\x00") > 1
    monkeypatch.setattr(post_db, "_prepare_image", lambda data, mime_type: data)
    result = logic.create_post(post_db, anna, park, "photo", original, "photo.png")
    post = post_db.get_user_posts(anna["id"])[0]
    stored = post_db.get_post_image(post["image_id"])
    assert result.success
    assert stored["mime_type"] == "image/png"
    assert stored["bytes"] == original


def test_image_size_boundary_is_checked_before_processing(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)
    maximum = 5 * 1024 * 1024
    exact_limit = PNG + b"\x00" * (maximum - len(PNG))
    too_large = exact_limit + b"\x00"
    assert logic.create_post(post_db, anna, park, "ok", exact_limit, "ok.png").success
    rejected = logic.create_post(post_db, anna, park, "too big", too_large, "big.png")
    assert not rejected.success
    assert post_db.count_images() == 1


@pytest.mark.parametrize(("width", "expected"), [(1200, 1200), (1201, 1200)])
def test_image_width_boundary(post_db, width, expected):
    anna = make_user(post_db, f"anna{width}")
    park = make_venue(post_db)
    raw = image_bytes(size=(width, 10))
    result = logic.create_post(post_db, anna, park, "wide", raw, "wide.png")
    post = post_db.get_user_posts(anna["id"])[0]
    stored = post_db.get_post_image(post["image_id"])
    assert result.success
    assert Image.open(BytesIO(stored["bytes"])).width == expected


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


def test_feed_query_returns_image_reference_without_binary_data(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)
    logic.create_post(post_db, anna, park, "with photo", PNG, "photo.png")
    post = logic.get_feed(post_db, anna)[0]
    assert post["image_id"] is not None
    assert "bytes" not in post
    assert "image_bytes" not in post


def test_image_lookup_cannot_leave_the_uploads_folder(post_db):
    assert post_db.get_image_file("../posts.db") is None
    assert post_db.get_image_file(None) is None


def test_post_time_is_shown_in_lisbon_time():
    assert logic.format_post_time("2026-07-18T20:30:00+00:00") == "18 Jul 2026, 21:30"


def test_iphone_heic_photo_is_accepted_and_stored_as_jpeg(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)
    heic = image_bytes("HEIF", size=(1600, 1200))

    result = logic.create_post(post_db, anna, park, "From my iPhone", heic, "IMG_1234.HEIC")

    assert result.success
    stored = post_db.get_post_image(post_db.get_user_posts(anna["id"])[0]["image_id"])
    assert stored["mime_type"] == "image/jpeg"
    image = Image.open(BytesIO(stored["bytes"]))
    assert image.format == "JPEG"
    assert image.width == 1200


def test_phone_photo_is_rotated_using_its_exif_orientation(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)
    buffer = BytesIO()
    exif = Image.Exif()
    exif[0x0112] = 6  # "rotate 90 degrees": how phones mark portrait photos
    Image.new("RGB", (40, 20), (200, 120, 30)).save(buffer, format="JPEG", exif=exif)

    assert logic.create_post(post_db, anna, park, "portrait", buffer.getvalue(), "IMG_0001.JPG").success

    stored = post_db.get_post_image(post_db.get_user_posts(anna["id"])[0]["image_id"])
    assert Image.open(BytesIO(stored["bytes"])).size == (20, 40)


def test_renamed_file_with_heic_extension_is_refused(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)

    result = logic.create_post(post_db, anna, park, "fake", b"not an image at all", "IMG_9999.HEIC")

    assert not result.success
    assert post_db.count_images() == 0
