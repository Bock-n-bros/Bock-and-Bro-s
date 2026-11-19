"""Tests for in-app notifications, post tags and notification emails (spec 14)."""

from datetime import datetime, timedelta, timezone

import pytest

import db
import logic
import mail


@pytest.fixture
def alert_db(tmp_path, monkeypatch):
    """Use an isolated database for every notification test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "alerts.db")
    db.init_db()
    return db


@pytest.fixture
def sent(monkeypatch):
    """Pretend SMTP is configured and capture emails instead of sending them."""
    outbox = []
    monkeypatch.setattr(mail, "smtp_configured", lambda: True)
    monkeypatch.setattr(mail, "send_notification",
                        lambda recipient, subject, body: outbox.append((recipient, subject, body)))
    return outbox


def make_user(database, username, role="customer"):
    """Create a profile and return the public user dictionary."""
    database.create_user(f"sub-{username}", f"{username}@example.com", username, role)
    return logic.find_google_user(database, f"sub-{username}")


def make_venue(database):
    """Create a minimal venue and return its id."""
    return database.insert_venue({
        "name": "Park Bar", "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "yes", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue",
    })


def at(minutes):
    """Return a fixed UTC time a number of minutes after a base time."""
    return datetime(2026, 11, 19, 20, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def texts(database, user):
    """Return the user's notification sentences, newest first."""
    return [alert["text"] for alert in logic.get_alerts(database, user)]


def test_like_and_comment_notify_the_post_author(alert_db):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id

    logic.toggle_like(alert_db, ben, post, now=at(1))
    logic.add_comment(alert_db, ben, post, "Nice!", now=at(2))

    assert texts(alert_db, anna) == ["ben commented on your post", "ben liked your post"]
    assert all(alert["post_id"] == post for alert in logic.get_alerts(alert_db, anna))


def test_own_actions_do_not_notify(alert_db):
    anna = make_user(alert_db, "anna")
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id

    logic.toggle_like(alert_db, anna, post)
    logic.add_comment(alert_db, anna, post, "me again")

    assert logic.get_alerts(alert_db, anna) == []


def test_like_unlike_like_notifies_only_once(alert_db):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id

    for _ in range(3):
        logic.toggle_like(alert_db, ben, post)

    assert texts(alert_db, anna) == ["ben liked your post"]


def test_tagged_users_are_saved_shown_and_notified(alert_db):
    anna, ben, cleo = (make_user(alert_db, name) for name in ("anna", "ben", "cleo"))

    result = logic.create_post(alert_db, anna, None, "Picnic", location_name="Jardim da Estrela",
                               tagged_user_ids=[cleo["id"], ben["id"], ben["id"]])

    assert result.success
    post = logic.get_user_posts(alert_db, anna["id"], anna)[0]
    assert [tag["username"] for tag in post["tags"]] == ["ben", "cleo"]
    assert texts(alert_db, ben) == ["anna tagged you in a post"]
    assert texts(alert_db, cleo) == ["anna tagged you in a post"]


@pytest.mark.parametrize("tagged", [["self"], [9999], list(range(1, 12))])
def test_invalid_tags_are_refused_and_no_post_is_saved(alert_db, tagged):
    anna = make_user(alert_db, "anna")
    tagged = [anna["id"]] if tagged == ["self"] else tagged

    result = logic.create_post(alert_db, anna, make_venue(alert_db), "Hi", tagged_user_ids=tagged)

    assert not result.success
    assert alert_db.count_posts() == 0


def test_being_added_to_a_group_notifies_each_new_member(alert_db):
    anna, ben, cleo, dia = (make_user(alert_db, name) for name in ("anna", "ben", "cleo", "dia"))

    group = logic.create_group_conversation(alert_db, anna, "Friday", [ben["id"], cleo["id"]]).conversation_id
    logic.add_group_member(alert_db, anna, group, dia["id"])

    for person in (ben, cleo, dia):
        assert texts(alert_db, person) == ["anna added you to Friday"]
    assert logic.get_alerts(alert_db, anna) == []


def test_messages_notify_other_members_with_one_unread_alert_per_conversation(alert_db):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    chat = logic.start_direct_conversation(alert_db, anna, ben["id"]).conversation_id

    logic.send_message(alert_db, anna, chat, "Hi", now=at(1))
    logic.send_message(alert_db, anna, chat, "Beer?", now=at(2))

    assert texts(alert_db, ben) == ["anna sent you a message"]
    assert logic.get_alerts(alert_db, anna) == []
    assert len(logic.take_new_alerts(alert_db, ben)) == 1

    logic.send_message(alert_db, anna, chat, "Still there?", now=at(3))

    assert [alert["text"] for alert in logic.take_new_alerts(alert_db, ben)] == ["anna sent you a message"]


def test_group_message_names_the_group(alert_db):
    anna, ben, cleo = (make_user(alert_db, name) for name in ("anna", "ben", "cleo"))
    group = logic.create_group_conversation(alert_db, anna, "Friday", [ben["id"], cleo["id"]]).conversation_id
    logic.mark_alerts_read(alert_db, ben)

    logic.send_message(alert_db, cleo, group, "Who's in?")

    assert texts(alert_db, ben)[0] == "cleo sent a message in Friday"


def test_popups_are_shown_once_and_reading_clears_the_unread_count(alert_db):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id
    logic.toggle_like(alert_db, ben, post)
    logic.add_comment(alert_db, ben, post, "Nice")

    assert logic.count_unread_alerts(alert_db, anna) == 2
    assert len(logic.take_new_alerts(alert_db, anna)) == 2
    assert logic.take_new_alerts(alert_db, anna) == []
    assert logic.count_unread_alerts(alert_db, anna) == 2

    logic.mark_alerts_read(alert_db, anna)

    assert logic.count_unread_alerts(alert_db, anna) == 0
    assert len(logic.get_alerts(alert_db, anna)) == 2


def test_alerts_are_private_to_their_recipient(alert_db):
    anna, ben, cleo = (make_user(alert_db, name) for name in ("anna", "ben", "cleo"))
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id
    logic.toggle_like(alert_db, ben, post)

    assert logic.get_alerts(alert_db, cleo) == []
    assert logic.get_alerts(alert_db, None) == []
    assert "example.com" not in str(logic.get_alerts(alert_db, anna))


def test_email_is_sent_when_opted_in_and_never_quotes_content(alert_db, sent):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id

    logic.add_comment(alert_db, ben, post, "SECRET_COMMENT_123")

    assert len(sent) == 1
    recipient, subject, body = sent[0]
    assert recipient == "anna@example.com"
    assert "ben commented on your post" in subject
    assert "SECRET_COMMENT_123" not in body and "http" in body


def test_no_email_when_user_turned_email_off(alert_db, sent):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    logic.set_email_notifications(alert_db, anna, False)
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id

    logic.toggle_like(alert_db, ben, post)

    assert sent == []
    assert texts(alert_db, anna) == ["ben liked your post"]


def test_message_emails_are_limited_to_one_per_conversation_per_hour(alert_db, sent):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    chat = logic.start_direct_conversation(alert_db, anna, ben["id"]).conversation_id

    logic.send_message(alert_db, anna, chat, "one", now=at(0))
    logic.send_message(alert_db, anna, chat, "two", now=at(30))
    logic.send_message(alert_db, anna, chat, "three", now=at(61))

    assert len(sent) == 2
    assert all(recipient == "ben@example.com" for recipient, _, _ in sent)


def test_tags_and_group_invites_are_always_emailed(alert_db, sent):
    anna, ben, cleo = (make_user(alert_db, name) for name in ("anna", "ben", "cleo"))

    logic.create_group_conversation(alert_db, anna, "Friday", [ben["id"], cleo["id"]], now=at(0))
    logic.create_post(alert_db, anna, make_venue(alert_db), "Hi", tagged_user_ids=[ben["id"]], now=at(1))
    logic.create_post(alert_db, anna, make_venue(alert_db), "Again", tagged_user_ids=[ben["id"]], now=at(2))

    assert [recipient for recipient, _, _ in sent].count("ben@example.com") == 3


def test_email_failure_does_not_break_the_action(alert_db, monkeypatch):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    monkeypatch.setattr(mail, "smtp_configured", lambda: True)

    def broken(*_):
        raise OSError("SMTP down")

    monkeypatch.setattr(mail, "send_notification", broken)
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id

    assert logic.add_comment(alert_db, ben, post, "Nice").success
    assert texts(alert_db, anna) == ["ben commented on your post"]


def test_all_email_categories_are_on_by_default(alert_db):
    anna = make_user(alert_db, "anna")

    assert logic.get_email_categories(alert_db, anna) == set(logic.EMAIL_CATEGORIES)


def test_user_can_choose_which_notifications_are_emailed(alert_db, sent):
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    assert logic.set_email_categories(alert_db, anna, ["messages"]).success
    post = logic.create_post(alert_db, anna, make_venue(alert_db), "Cheers").post_id
    chat = logic.start_direct_conversation(alert_db, ben, anna["id"]).conversation_id

    logic.toggle_like(alert_db, ben, post)
    logic.send_message(alert_db, ben, chat, "Hi")

    assert [subject for _, subject, _ in sent] == ["Bock'n Bros: ben sent you a message"]
    assert texts(alert_db, anna) == ["ben sent you a message", "ben liked your post"]


def test_no_categories_means_no_emails_but_still_in_app(alert_db, sent):
    anna, ben, cleo = (make_user(alert_db, name) for name in ("anna", "ben", "cleo"))
    logic.set_email_categories(alert_db, ben, [])

    logic.create_group_conversation(alert_db, anna, "Friday", [ben["id"], cleo["id"]])

    assert [recipient for recipient, _, _ in sent] == ["cleo@example.com"]
    assert texts(alert_db, ben) == ["anna added you to Friday"]


def test_unknown_category_is_refused(alert_db):
    anna = make_user(alert_db, "anna")

    assert not logic.set_email_categories(alert_db, anna, ["spam"]).success
    assert logic.get_email_categories(alert_db, anna) == set(logic.EMAIL_CATEGORIES)


def test_new_meetup_notifies_group_members_and_respects_meetup_choice(alert_db, sent):
    anna, ben, cleo = (make_user(alert_db, name) for name in ("anna", "ben", "cleo"))
    group = logic.create_group_conversation(alert_db, anna, "Friday", [ben["id"], cleo["id"]]).conversation_id
    logic.set_email_categories(alert_db, cleo, ["messages"])
    sent.clear()

    result = logic.create_event(alert_db, anna, group, make_venue(alert_db), "Drinks", "2026-11-20T20:00")

    assert result.success
    assert texts(alert_db, ben)[0] == "anna planned a meetup in Friday"
    assert texts(alert_db, cleo)[0] == "anna planned a meetup in Friday"
    assert [recipient for recipient, _, _ in sent] == ["ben@example.com"]


def test_notify_bro_respects_the_notify_bro_choice(alert_db, monkeypatch):
    outbox = []
    monkeypatch.setattr(mail, "smtp_configured", lambda: True)
    monkeypatch.setattr(mail, "send_notification", lambda recipient, subject, body: outbox.append(recipient))
    anna, ben = make_user(alert_db, "anna"), make_user(alert_db, "ben")
    chat = logic.start_direct_conversation(alert_db, anna, ben["id"]).conversation_id
    logic.set_email_categories(alert_db, ben, ["posts", "messages"])

    result = logic.notify_conversation(alert_db, anna, chat)

    assert not result.success
    assert outbox == []


def test_alerts_table_from_first_version_is_upgraded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_database_url", lambda: None)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "old.db")
    db.init_db()
    with db._connect() as connection:
        connection.execute("DROP TABLE alerts")
        connection.execute(
            "CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_id INTEGER NOT NULL, "
            "actor_id INTEGER NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('like', 'comment', 'tag', "
            "'group_added', 'message')), post_id INTEGER, conversation_id INTEGER, created_at TEXT NOT NULL, "
            "read_at TEXT, toasted INTEGER NOT NULL DEFAULT 0, emailed_at TEXT)")
        connection.execute("INSERT INTO alerts (recipient_id, actor_id, kind, created_at) VALUES (1, 2, 'like', '2026')")
    monkeypatch.setattr(db, "_initialized_key", None)

    db.init_db()
    db.add_alert(1, 2, "event", conversation_id=None)

    with db._connect() as connection:
        kinds = [row[0] for row in connection.execute("SELECT kind FROM alerts ORDER BY id").fetchall()]
    assert kinds == ["like", "event"]
