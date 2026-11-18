"""Tests for direct messages between customers and bar owners."""

from datetime import datetime, timedelta, timezone

import pytest

import db
import logic


@pytest.fixture
def message_db(tmp_path, monkeypatch):
    """Use an isolated database for every messaging test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "messages.db")
    db.init_db()
    return db


def make_user(database, username, role="customer"):
    """Create a profile and return the public user dictionary."""
    database.create_user(f"sub-{username}", f"{username}@example.com", username, role)
    return logic.find_google_user(database, f"sub-{username}")


def at(minutes):
    """Return a fixed UTC time a number of minutes after a base time."""
    return datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def test_customer_and_bar_owner_can_have_a_dialogue(message_db):
    anna = make_user(message_db, "anna")
    bar = make_user(message_db, "parkbar", role="business")

    started = logic.start_direct_conversation(message_db, anna, bar["id"])
    assert started.success
    conversation_id = started.conversation_id

    assert logic.send_message(message_db, anna, conversation_id, "Do you show Benfica tonight?", now=at(1)).success
    assert logic.send_message(message_db, bar, conversation_id, "Yes, from 20:00!", now=at(2)).success

    for reader in (anna, bar):
        messages = logic.get_conversation_messages(message_db, reader, conversation_id)
        assert [(m["username"], m["text"]) for m in messages] == [
            ("anna", "Do you show Benfica tonight?"),
            ("parkbar", "Yes, from 20:00!"),
        ]


def test_starting_again_reopens_the_same_conversation_from_either_side(message_db):
    anna = make_user(message_db, "anna")
    ben = make_user(message_db, "ben")

    first = logic.start_direct_conversation(message_db, anna, ben["id"]).conversation_id
    again = logic.start_direct_conversation(message_db, anna, ben["id"]).conversation_id
    reverse = logic.start_direct_conversation(message_db, ben, anna["id"]).conversation_id

    assert first == again == reverse
    assert len(logic.list_conversations(message_db, anna)) == 1


def test_cannot_message_yourself_or_unknown_user(message_db):
    anna = make_user(message_db, "anna")

    assert not logic.start_direct_conversation(message_db, anna, anna["id"]).success
    assert not logic.start_direct_conversation(message_db, anna, 9999).success
    assert logic.list_conversations(message_db, anna) == []


def test_logged_out_user_cannot_start_send_or_read(message_db):
    anna = make_user(message_db, "anna")
    ben = make_user(message_db, "ben")
    conversation_id = logic.start_direct_conversation(message_db, anna, ben["id"]).conversation_id

    assert not logic.start_direct_conversation(message_db, None, ben["id"]).success
    assert not logic.send_message(message_db, None, conversation_id, "hi").success
    assert logic.get_conversation_messages(message_db, None, conversation_id) is None


def test_outsider_cannot_read_or_send(message_db):
    anna = make_user(message_db, "anna")
    ben = make_user(message_db, "ben")
    eve = make_user(message_db, "eve")
    conversation_id = logic.start_direct_conversation(message_db, anna, ben["id"]).conversation_id
    logic.send_message(message_db, anna, conversation_id, "Private plan", now=at(1))

    assert logic.get_conversation_messages(message_db, eve, conversation_id) is None
    result = logic.send_message(message_db, eve, conversation_id, "Let me in")
    assert not result.success
    assert len(logic.get_conversation_messages(message_db, anna, conversation_id)) == 1
    assert logic.list_conversations(message_db, eve) == []


@pytest.mark.parametrize("text", ["", "   ", "\n", None, "x" * 1001])
def test_invalid_messages_are_refused_and_not_saved(message_db, text):
    anna = make_user(message_db, "anna")
    ben = make_user(message_db, "ben")
    conversation_id = logic.start_direct_conversation(message_db, anna, ben["id"]).conversation_id

    assert not logic.send_message(message_db, anna, conversation_id, text).success
    assert logic.get_conversation_messages(message_db, anna, conversation_id) == []


def test_message_is_trimmed_and_1000_characters_is_allowed(message_db):
    anna = make_user(message_db, "anna")
    ben = make_user(message_db, "ben")
    conversation_id = logic.start_direct_conversation(message_db, anna, ben["id"]).conversation_id

    assert logic.send_message(message_db, anna, conversation_id, "  hi  ", now=at(1)).success
    assert logic.send_message(message_db, anna, conversation_id, "y" * 1000, now=at(2)).success
    texts = [m["text"] for m in logic.get_conversation_messages(message_db, anna, conversation_id)]
    assert texts == ["hi", "y" * 1000]


def test_formatting_characters_are_stored_exactly(message_db):
    anna = make_user(message_db, "anna")
    ben = make_user(message_db, "ben")
    conversation_id = logic.start_direct_conversation(message_db, anna, ben["id"]).conversation_id

    logic.send_message(message_db, anna, conversation_id, "**bold** <b>hi</b>")
    assert logic.get_conversation_messages(message_db, ben, conversation_id)[0]["text"] == "**bold** <b>hi</b>"


def test_conversation_list_shows_other_person_and_newest_activity_first(message_db):
    anna = make_user(message_db, "anna")
    ben = make_user(message_db, "ben")
    bar = make_user(message_db, "parkbar", role="business")
    with_ben = logic.start_direct_conversation(message_db, anna, ben["id"], now=at(0)).conversation_id
    with_bar = logic.start_direct_conversation(message_db, anna, bar["id"], now=at(0)).conversation_id
    logic.send_message(message_db, anna, with_bar, "Table for 4?", now=at(1))
    logic.send_message(message_db, ben, with_ben, "Beer later?", now=at(5))

    conversations = logic.list_conversations(message_db, anna)

    assert [(c["title"], c["last_message"]) for c in conversations] == [
        ("ben", "Beer later?"),
        ("parkbar", "Table for 4?"),
    ]
    assert conversations[1]["other_role"] == "business"


def test_message_rows_never_contain_email(message_db):
    anna = make_user(message_db, "anna")
    ben = make_user(message_db, "ben")
    conversation_id = logic.start_direct_conversation(message_db, anna, ben["id"]).conversation_id
    logic.send_message(message_db, anna, conversation_id, "hi")

    rows = logic.get_conversation_messages(message_db, ben, conversation_id)
    rows += logic.list_conversations(message_db, ben)
    rows += logic.search_people(message_db, ben, "ann")
    assert all("email" not in row and "example.com" not in str(row) for row in rows)


def test_search_people_finds_others_case_insensitively(message_db):
    anna = make_user(message_db, "anna")
    make_user(message_db, "Annabel")
    make_user(message_db, "parkbar", role="business")

    found = [person["username"] for person in logic.search_people(message_db, anna, " ANN ")]

    assert found == ["Annabel"]
    assert logic.search_people(message_db, anna, "   ") == []


def test_search_treats_underscore_literally(message_db):
    anna = make_user(message_db, "anna")
    make_user(message_db, "bar_one")
    make_user(message_db, "barxone")

    assert [p["username"] for p in logic.search_people(message_db, anna, "r_o")] == ["bar_one"]


def test_message_time_is_shown_in_lisbon_time():
    assert logic.format_message_time("2026-11-18T21:30:00+00:00") == "18 Nov, 21:30"
    assert logic.format_message_time("2026-07-18T21:30:00+00:00") == "18 Jul, 22:30"
