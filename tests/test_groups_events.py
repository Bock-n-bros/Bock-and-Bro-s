"""Tests for group conversations and Bock a Bro meetups."""

from datetime import datetime, timezone

import pytest

import db
import logic


@pytest.fixture
def group_db(tmp_path, monkeypatch):
    """Use an isolated local database for group and event tests."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "groups.db")
    monkeypatch.setattr(db, "_database_url", lambda: None)
    db.close_connection()
    db.init_db()
    return db


def make_user(database, username):
    """Create a user and return the public profile."""
    database.create_user(f"sub-{username}", f"{username}@example.com", username, "customer")
    return logic.find_google_user(database, f"sub-{username}")


def make_users(database, count):
    """Create a list of users with deterministic names."""
    return [make_user(database, f"person{number:02d}") for number in range(count)]


def make_venue(database):
    """Create a Lisbon venue for an event."""
    return database.insert_venue({
        "name": "Park Bar", "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "yes", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue",
    })


def make_group(database, users, name="Friday beers"):
    """Create a group with the first user as its owner."""
    result = logic.create_group_conversation(database, users[0], name, [person["id"] for person in users[1:]])
    assert result.success
    return result.conversation_id


def test_group_name_accepts_50_characters_rejects_51_and_allows_no_name(group_db):
    users = make_users(group_db, 3)

    accepted = logic.create_group_conversation(group_db, users[0], "x" * 50, [users[1]["id"], users[2]["id"]])
    rejected = logic.create_group_conversation(group_db, users[0], "x" * 51, [users[1]["id"], users[2]["id"]])
    unnamed = logic.create_group_conversation(group_db, users[0], "   ", [users[1]["id"], users[2]["id"]])

    assert accepted.success
    assert not rejected.success
    assert unnamed.success
    listing = logic.list_conversations(group_db, users[0])
    assert next(item["title"] for item in listing if item["id"] == unnamed.conversation_id) == "person00, person01, person02"


def test_groups_allow_20_members_and_reject_21(group_db):
    users = make_users(group_db, 21)

    accepted = logic.create_group_conversation(group_db, users[0], "Full house", [user["id"] for user in users[1:20]])
    rejected = logic.create_group_conversation(group_db, users[0], "Too many", [user["id"] for user in users[1:]])

    assert accepted.success
    assert len(group_db.get_conversation_members(accepted.conversation_id)) == 20
    assert not rejected.success


def test_only_creator_manages_group_others_can_leave(group_db):
    users = make_users(group_db, 4)
    conversation_id = make_group(group_db, users[:3])

    assert not logic.add_group_member(group_db, users[1], conversation_id, users[3]["id"]).success
    assert logic.rename_group(group_db, users[1], conversation_id, "New name").success is False
    assert logic.remove_group_member(group_db, users[1], conversation_id, users[2]["id"]).success is False
    assert logic.add_group_member(group_db, users[0], conversation_id, users[3]["id"]).success
    assert logic.remove_group_member(group_db, users[0], conversation_id, users[3]["id"]).success
    assert logic.rename_group(group_db, users[0], conversation_id, "New name").success
    assert logic.leave_group(group_db, users[1], conversation_id).success
    assert not group_db.is_conversation_member(conversation_id, users[1]["id"])


def test_group_members_can_send_and_outsiders_cannot_read(group_db):
    users = make_users(group_db, 4)
    conversation_id = make_group(group_db, users[:3])

    assert logic.send_message(group_db, users[1], conversation_id, "See you there").success
    assert logic.get_conversation_messages(group_db, users[2], conversation_id)[0]["text"] == "See you there"
    assert logic.get_conversation_messages(group_db, users[3], conversation_id) is None


def test_event_creation_and_dates_are_formatted_and_split_into_past(group_db):
    users = make_users(group_db, 3)
    conversation_id = make_group(group_db, users)
    venue_id = make_venue(group_db)
    now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
    past = logic.create_event(group_db, users[0], conversation_id, venue_id,
                              "Watch the match", "2026-11-08T20:00:00+00:00", now=now)
    upcoming = logic.create_event(group_db, users[0], conversation_id, venue_id,
                                  "After work", "2026-11-10T20:00:00+00:00", now=now)

    events = logic.get_conversation_events(group_db, users[1], conversation_id, now=now)

    assert past.success and upcoming.success
    assert [event["id"] for event in events["past"]] == [past.event_id]
    assert [event["id"] for event in events["upcoming"]] == [upcoming.event_id]
    assert logic.format_event_time(events["past"][0]["starts_at"]) == "8 Nov 2026, 20:00"


def test_event_requires_membership_and_existing_group_and_venue(group_db):
    users = make_users(group_db, 4)
    conversation_id = make_group(group_db, users[:3])
    direct = logic.start_direct_conversation(group_db, users[0], users[3]["id"]).conversation_id
    venue_id = make_venue(group_db)
    starts_at = "2026-11-10T20:00:00+00:00"

    assert not logic.create_event(group_db, users[3], conversation_id, venue_id, "Outside", starts_at).success
    assert not logic.create_event(group_db, users[0], direct, venue_id, "Not a group", starts_at).success
    assert not logic.create_event(group_db, users[0], conversation_id, 99999, "Unknown place", starts_at).success
    event = logic.create_event(group_db, users[0], conversation_id, venue_id, "Plan", starts_at)
    assert event.success
    assert logic.get_conversation_events(group_db, users[3], conversation_id) is None
    assert not logic.respond_to_event(group_db, users[3], event.event_id, "going").success


def test_event_capacity_blocks_next_yes_and_responses_can_change(group_db):
    users = make_users(group_db, 4)
    conversation_id = make_group(group_db, users)
    event = logic.create_event(group_db, users[0], conversation_id, make_venue(group_db),
                               "Table for two", "2026-11-10T20:00:00+00:00", max_attendees=2)

    assert logic.respond_to_event(group_db, users[0], event.event_id, "going").success
    assert logic.respond_to_event(group_db, users[1], event.event_id, "going").success
    full = logic.respond_to_event(group_db, users[2], event.event_id, "going")
    assert not full.success and "full" in full.message.casefold()
    assert logic.respond_to_event(group_db, users[1], event.event_id, "not_going").success
    assert logic.respond_to_event(group_db, users[2], event.event_id, "going").success
    assert logic.respond_to_event(group_db, users[1], event.event_id, "going").success is False
    assert [person["user_id"] for person in logic.get_event_attendees(group_db, users[0], event.event_id)] == [users[0]["id"], users[2]["id"]]


def test_only_event_creator_can_cancel(group_db):
    users = make_users(group_db, 3)
    conversation_id = make_group(group_db, users)
    event = logic.create_event(group_db, users[0], conversation_id, make_venue(group_db),
                               "Board games", "2026-11-10T20:00:00+00:00")

    assert not logic.cancel_event(group_db, users[1], event.event_id).success
    assert logic.cancel_event(group_db, users[0], event.event_id).success
    assert logic.get_conversation_events(group_db, users[1], conversation_id)["upcoming"] == []
