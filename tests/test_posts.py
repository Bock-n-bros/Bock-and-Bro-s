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


def test_text_only_and_photo_only_posts_work_but_webp_is_refused(post_db):
    anna = make_user(post_db, "anna")
    park = make_venue(post_db)

    text_result = logic.create_post(post_db, anna, park, "Just text")
    photo_result = logic.create_post(post_db, anna, park, "", PNG, "pic.png")
    assert text_result.success
    assert photo_result.success
    assert post_db.get_user_posts(anna["id"])[1]["image_id"] is None
    rejected_webp = logic.create_post(post_db, anna, park, "", image_bytes("WEBP"), "pic.webp")
    assert not rejected_webp.success
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


def test_author_can_delete_their_own_post(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    post_id = logic.create_post(post_db, writer, venue_id, "Pulling the plug").post_id

    result = logic.delete_post(post_db, writer, post_id)

    assert result.success
    assert post_db.get_post_details(post_id) == []
    assert post_db.count_posts() == 0


def test_another_user_cannot_delete_someone_elses_post(post_db):
    writer = make_user(post_db, "writer")
    stranger = make_user(post_db, "stranger")
    venue_id = make_venue(post_db)
    post_id = logic.create_post(post_db, writer, venue_id, "Not yours").post_id

    result = logic.delete_post(post_db, stranger, post_id)

    assert not result.success
    assert "your own" in result.message
    assert post_db.count_posts() == 1


def test_logged_out_user_cannot_delete_a_post(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    post_id = logic.create_post(post_db, writer, venue_id, "Still here").post_id

    result = logic.delete_post(post_db, None, post_id)

    assert not result.success
    assert post_db.count_posts() == 1


def test_deleting_an_unknown_post_is_refused(post_db):
    writer = make_user(post_db, "writer")

    result = logic.delete_post(post_db, writer, 999)

    assert not result.success
    assert "could not be found" in result.message


def test_deleting_a_post_removes_its_comments_and_likes(post_db):
    writer = make_user(post_db, "writer")
    reader = make_user(post_db, "reader")
    venue_id = make_venue(post_db)
    post_id = logic.create_post(post_db, writer, venue_id, "Say something").post_id
    logic.add_comment(post_db, reader, post_id, "Nice one")
    logic.toggle_like(post_db, reader, post_id)
    assert post_db.count_comments(post_id) == 1
    assert post_db.count_likes(post_id) == 1

    assert logic.delete_post(post_db, writer, post_id).success

    assert post_db.count_comments(post_id) == 0
    assert post_db.count_likes(post_id) == 0


def test_deleting_a_post_removes_its_photo(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    post_id = logic.create_post(post_db, writer, venue_id, "With a photo",
                                image_bytes=PNG, image_name="beer.png").post_id
    assert post_db.count_images() == 1

    assert logic.delete_post(post_db, writer, post_id).success

    assert post_db.count_images() == 0


def test_deleting_a_post_keeps_a_profile_picture_using_the_same_image(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    logic.set_profile_picture(post_db, writer, PNG, "me.png")
    post_id = logic.create_post(post_db, writer, venue_id, "Separate photo",
                                image_bytes=JPG, image_name="beer.jpg").post_id

    assert logic.delete_post(post_db, writer, post_id).success

    assert post_db.get_profile_image_id(writer["id"]) is not None


def test_deleting_one_post_leaves_other_posts_alone(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    keep_id = logic.create_post(post_db, writer, venue_id, "Keep me").post_id
    drop_id = logic.create_post(post_db, writer, venue_id, "Drop me").post_id

    assert logic.delete_post(post_db, writer, drop_id).success

    assert [post["id"] for post in post_db.get_user_posts(writer["id"])] == [keep_id]


def photo_ids(database, post_id):
    """Return a post's photo ids in order."""
    return database.get_post_image_ids(post_id)


def test_a_post_can_hold_several_photos_in_upload_order(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)

    result = logic.create_post(post_db, writer, venue_id, "Three of us",
                               images=[(PNG, "one.png"), (JPG, "two.jpg"), (PNG, "three.PNG")])

    assert result.success
    assert len(photo_ids(post_db, result.post_id)) == 3
    assert post_db.count_images() == 3


def test_the_first_photo_becomes_the_cover(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)

    post_id = logic.create_post(post_db, writer, venue_id, "Cover",
                                images=[(PNG, "first.png"), (JPG, "second.jpg")]).post_id

    assert post_db.get_post_details(post_id)[0]["image_id"] == photo_ids(post_db, post_id)[0]


def test_more_than_the_maximum_number_of_photos_is_refused(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    too_many = [(PNG, f"photo-{number}.png") for number in range(logic.MAX_POST_PHOTOS + 1)]

    result = logic.create_post(post_db, writer, venue_id, "Too many", images=too_many)

    assert not result.success
    assert str(logic.MAX_POST_PHOTOS) in result.message
    assert post_db.count_posts() == 0
    assert post_db.count_images() == 0


def test_the_maximum_number_of_photos_is_allowed(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    allowed = [(PNG, f"photo-{number}.png") for number in range(logic.MAX_POST_PHOTOS)]

    result = logic.create_post(post_db, writer, venue_id, "Just enough", images=allowed)

    assert result.success
    assert len(photo_ids(post_db, result.post_id)) == logic.MAX_POST_PHOTOS


def test_one_bad_photo_refuses_the_whole_post_and_saves_nothing(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)

    result = logic.create_post(post_db, writer, venue_id, "One is broken",
                               images=[(PNG, "good.png"), (b"not an image", "bad.png")])

    assert not result.success
    assert post_db.count_posts() == 0
    assert post_db.count_images() == 0


def test_a_single_photo_post_still_works_the_old_way(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)

    post_id = logic.create_post(post_db, writer, venue_id, "Just one", PNG, "one.png").post_id

    assert photo_ids(post_db, post_id) == [post_db.get_post_details(post_id)[0]["image_id"]]
    assert post_db.count_images() == 1


def test_feed_posts_carry_their_photo_ids(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    logic.create_post(post_db, writer, venue_id, "Two photos",
                      images=[(PNG, "a.png"), (JPG, "b.jpg")])

    feed = logic.get_feed(post_db, writer)

    assert len(feed[0]["image_ids"]) == 2
    assert logic.get_app_post_photos(feed[0]) == feed[0]["image_ids"]


def test_a_post_saved_before_this_feature_keeps_its_photo(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    post_id = logic.create_post(post_db, writer, venue_id, "Old post", PNG, "old.png").post_id
    # Undo the join rows, leaving the row shape an earlier version of the app wrote.
    post_db._query("DELETE FROM post_images WHERE post_id = ?", (post_id,))
    assert photo_ids(post_db, post_id) == []

    post_db._initialized_key = None
    post_db.init_db()

    assert len(photo_ids(post_db, post_id)) == 1


def test_running_the_backfill_twice_does_not_duplicate_photos(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    post_id = logic.create_post(post_db, writer, venue_id, "Once only", PNG, "one.png").post_id

    post_db._initialized_key = None
    post_db.init_db()

    assert len(photo_ids(post_db, post_id)) == 1


def test_deleting_a_post_removes_all_of_its_photos(post_db):
    writer = make_user(post_db, "writer")
    venue_id = make_venue(post_db)
    post_id = logic.create_post(post_db, writer, venue_id, "Three photos",
                                images=[(PNG, "a.png"), (JPG, "b.jpg"), (PNG, "c.png")]).post_id
    assert post_db.count_images() == 3

    assert logic.delete_post(post_db, writer, post_id).success

    assert post_db.count_images() == 0
    assert photo_ids(post_db, post_id) == []


def test_post_images_is_covered_by_row_level_security(post_db):
    assert "post_images" in post_db._rls_table_names()
