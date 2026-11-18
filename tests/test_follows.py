"""Tests for following users and bars, friends and profile pages."""

import pytest

import db
import logic


@pytest.fixture
def follow_db(tmp_path, monkeypatch):
    """Use an isolated database for every follow test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "follows.db")
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


def names(people):
    """Return just the usernames from a list of users."""
    return [person["username"] for person in people]


def test_follow_shows_up_in_both_profiles(follow_db):
    anna = make_user(follow_db, "anna")
    ben = make_user(follow_db, "ben")

    assert logic.follow_user(follow_db, anna, ben["id"]).success

    assert names(logic.get_profile(follow_db, anna, anna["id"])["following"]) == ["ben"]
    ben_profile = logic.get_profile(follow_db, anna, ben["id"])
    assert names(ben_profile["followers"]) == ["anna"]
    assert ben_profile["is_followed_by_me"] is True
    assert ben_profile["follows_me"] is False


def test_following_twice_counts_once(follow_db):
    anna = make_user(follow_db, "anna")
    ben = make_user(follow_db, "ben")

    logic.follow_user(follow_db, anna, ben["id"])
    assert logic.follow_user(follow_db, anna, ben["id"]).success

    assert len(logic.get_profile(follow_db, anna, ben["id"])["followers"]) == 1


def test_cannot_follow_yourself_unknown_user_or_while_logged_out(follow_db):
    anna = make_user(follow_db, "anna")

    assert not logic.follow_user(follow_db, anna, anna["id"]).success
    assert not logic.follow_user(follow_db, anna, 9999).success
    assert not logic.follow_user(follow_db, None, anna["id"]).success
    assert logic.get_profile(follow_db, anna, anna["id"])["followers"] == []


def test_unfollow_removes_follow_and_is_safe_to_repeat(follow_db):
    anna = make_user(follow_db, "anna")
    ben = make_user(follow_db, "ben")
    logic.follow_user(follow_db, anna, ben["id"])

    assert logic.unfollow_user(follow_db, anna, ben["id"]).success
    assert logic.unfollow_user(follow_db, anna, ben["id"]).success

    assert logic.get_profile(follow_db, anna, ben["id"])["followers"] == []


def test_friends_are_people_who_follow_each_other(follow_db):
    anna = make_user(follow_db, "anna")
    ben = make_user(follow_db, "ben")
    cleo = make_user(follow_db, "cleo")
    dan = make_user(follow_db, "dan")
    logic.follow_user(follow_db, anna, ben["id"])
    logic.follow_user(follow_db, ben, anna["id"])
    logic.follow_user(follow_db, anna, cleo["id"])
    logic.follow_user(follow_db, dan, anna["id"])

    profile = logic.get_profile(follow_db, anna, anna["id"])

    assert names(profile["friends"]) == ["ben"]
    assert names(profile["following"]) == ["ben", "cleo"]
    assert names(profile["followers"]) == ["ben", "dan"]


def test_unfollowing_ends_the_friendship(follow_db):
    anna = make_user(follow_db, "anna")
    ben = make_user(follow_db, "ben")
    logic.follow_user(follow_db, anna, ben["id"])
    logic.follow_user(follow_db, ben, anna["id"])

    logic.unfollow_user(follow_db, ben, anna["id"])

    assert logic.get_profile(follow_db, anna, anna["id"])["friends"] == []


def test_customers_can_follow_bar_owners_and_back(follow_db):
    anna = make_user(follow_db, "anna")
    bar = make_user(follow_db, "parkbar", role="business")

    logic.follow_user(follow_db, anna, bar["id"])
    logic.follow_user(follow_db, bar, anna["id"])

    assert names(logic.get_profile(follow_db, bar, bar["id"])["friends"]) == ["anna"]


def test_following_a_bar_lists_it_on_the_profile(follow_db):
    anna = make_user(follow_db, "anna")
    park = make_venue(follow_db, "Park Bar")
    make_venue(follow_db, "Pensão Amor")

    assert logic.follow_venue(follow_db, anna, park).success
    assert logic.follow_venue(follow_db, anna, park).success

    bars = logic.get_profile(follow_db, anna, anna["id"])["bars"]
    assert [bar["name"] for bar in bars] == ["Park Bar"]
    assert logic.get_venue_follow_status(follow_db, anna, park) == {"is_following": True, "followers": 1}


def test_unfollow_bar_and_unknown_bar(follow_db):
    anna = make_user(follow_db, "anna")
    park = make_venue(follow_db)
    logic.follow_venue(follow_db, anna, park)

    assert logic.unfollow_venue(follow_db, anna, park).success
    assert not logic.follow_venue(follow_db, anna, 9999).success
    assert not logic.follow_venue(follow_db, None, park).success
    assert logic.get_profile(follow_db, anna, anna["id"])["bars"] == []
    assert logic.get_venue_follow_status(follow_db, anna, park)["followers"] == 0


def test_profile_of_unknown_user_is_none(follow_db):
    anna = make_user(follow_db, "anna")

    assert logic.get_profile(follow_db, anna, 9999) is None
    assert logic.get_profile(follow_db, None, anna["id"]) is None


def test_profile_never_contains_email(follow_db):
    anna = make_user(follow_db, "anna")
    ben = make_user(follow_db, "ben")
    logic.follow_user(follow_db, anna, ben["id"])
    logic.follow_user(follow_db, ben, anna["id"])

    assert "example.com" not in str(logic.get_profile(follow_db, anna, ben["id"]))
