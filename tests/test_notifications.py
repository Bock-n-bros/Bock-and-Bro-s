"""Tests for consent-based email notifications using a simulated SMTP server."""

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db
import logic
import mail


def make_user(database, username, email=None):
    """Create a user with a private email address."""
    database.create_user(f"sub-{username}", email or f"{username}@example.com", username, "customer")
    return logic.find_google_user(database, f"sub-{username}")


def make_venue(database):
    """Create a venue for event tests."""
    return database.insert_venue({
        "name": "Park Bar", "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "yes", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue",
    })


def setup_mail(monkeypatch):
    """Configure fake SMTP secrets and capture messages without sending email."""
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.test", 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            assert (user, password) == ("mailer", "fake-password")

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(mail, "_smtp_settings", lambda: {
        "host": "smtp.test", "port": 587, "user": "mailer",
        "password": "fake-password", "from_address": "noreply@example.com",
    })
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    return sent


def test_notification_cooldown_blocks_second_until_one_hour(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    sent = setup_mail(monkeypatch)
    anna = make_user(db, "anna")
    ben = make_user(db, "ben")
    conversation = logic.start_direct_conversation(db, anna, ben["id"]).conversation_id
    now = datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc)

    first = logic.notify_conversation(db, anna, conversation, now=now)
    second = logic.notify_conversation(db, anna, conversation, now=now + timedelta(minutes=59))
    after_hour = logic.notify_conversation(db, anna, conversation, now=now + timedelta(hours=1))

    assert first.success
    assert not second.success and "remaining" in second.message.casefold()
    assert after_hour.success
    assert len(sent) == 2


def test_opted_out_recipient_gets_no_email_and_sender_is_told(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    sent = setup_mail(monkeypatch)
    anna = make_user(db, "anna")
    ben = make_user(db, "ben")
    conversation = logic.start_direct_conversation(db, anna, ben["id"]).conversation_id
    assert db.set_email_notifications(ben["id"], False) is True

    result = logic.notify_conversation(db, anna, conversation)

    assert not result.success
    assert "turned off" in result.message.casefold()
    assert sent == []


def test_nonmember_cannot_notify_conversation(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    sent = setup_mail(monkeypatch)
    anna, ben, eve = (make_user(db, name) for name in ("anna", "ben", "eve"))
    conversation = logic.start_direct_conversation(db, anna, ben["id"]).conversation_id

    result = logic.notify_conversation(db, eve, conversation)

    assert not result.success
    assert sent == []


def test_group_event_notification_targets_only_members_without_response(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    sent = setup_mail(monkeypatch)
    anna, ben, cleo = (make_user(db, name) for name in ("anna", "ben", "cleo"))
    group = logic.create_group_conversation(db, anna, "Friday", [ben["id"], cleo["id"]]).conversation_id
    venue = make_venue(db)
    event_id = logic.create_event(db, anna, group, venue, "Friday drinks", "2026-11-19T20:00").event_id
    logic.respond_to_event(db, ben, event_id, "not_going")
    sent.clear()  # ignore the automatic notification emails (spec 11); this test is about Notify bro

    result = logic.notify_event(db, anna, event_id)

    assert result.success
    assert len(sent) == 1
    assert sent[0]["To"] == "cleo@example.com"
    body = sent[0].get_body(preferencelist=("plain",)).get_content()
    assert all(item in body for item in ("anna", "Friday", "Park Bar", "2026", "http"))
    assert "message text" not in body.casefold()


def test_group_cooldown_is_per_recipient_not_per_sender(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    sent = setup_mail(monkeypatch)
    anna, ben, cleo, dia = (make_user(db, name) for name in ("anna", "ben", "cleo", "dia"))
    group = logic.create_group_conversation(db, anna, "Friday", [ben["id"], cleo["id"], dia["id"]]).conversation_id
    venue = make_venue(db)
    event_id = logic.create_event(db, anna, group, venue, "Drinks", "2026-11-19T20:00").event_id
    sent.clear()  # ignore the automatic notification emails (spec 11); this test is about Notify bro

    first = logic.notify_event(db, anna, event_id)
    second = logic.notify_event(db, ben, event_id)

    assert first.sent_count == 3
    assert second.sent_count == 1
    assert len(sent) == 4


def test_message_email_contains_no_message_text(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    sent = setup_mail(monkeypatch)
    anna = make_user(db, "anna")
    ben = make_user(db, "ben")
    conversation = logic.start_direct_conversation(db, anna, ben["id"]).conversation_id
    logic.send_message(db, anna, conversation, "SECRET_MESSAGE_BODY_4721")
    assert all("SECRET_MESSAGE_BODY_4721" not in item.get_body(preferencelist=("plain",)).get_content()
               for item in sent)  # the automatic message email must not quote the message either
    sent.clear()  # ignore the automatic notification emails (spec 11); this test is about Notify bro

    assert logic.notify_conversation(db, anna, conversation).success
    message = sent[0].get_body(preferencelist=("plain",)).get_content()
    assert "SECRET_MESSAGE_BODY_4721" not in message
    assert "anna" in message and "direct conversation" in message and "http" in message


def test_smtp_failure_is_friendly_and_logged(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    setup_mail(monkeypatch)
    anna = make_user(db, "anna")
    ben = make_user(db, "ben")
    conversation = logic.start_direct_conversation(db, anna, ben["id"]).conversation_id

    def fail(*_):
        raise OSError("private SMTP details")

    monkeypatch.setattr(mail, "send_notification", fail)
    result = logic.notify_conversation(db, anna, conversation)

    assert not result.success
    assert "try again" in result.message.casefold()
    assert "private SMTP details" in caplog.text


def test_email_notification_preference_defaults_on_and_can_be_changed(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    user = make_user(db, "anna")

    assert db.get_email_notifications(user["id"]) is True
    assert db.set_email_notifications(user["id"], False) is True
    assert db.get_email_notifications(user["id"]) is False


def test_notification_database_schema_includes_rls_table(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    backend, _ = db._backend()
    assert any("CREATE TABLE IF NOT EXISTS notifications" in sql
               for sql in db._table_statements(backend))
    users = db._query("PRAGMA table_info(users)").fetchall()
    assert "email_notifications" in {row[1] for row in users}
    assert "notifications" in db._rls_table_names()


def test_email_addresses_do_not_enter_public_app_data(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    anna = make_user(db, "anna", "private-anna@example.com")
    ben = make_user(db, "ben", "private-ben@example.com")
    conversation = logic.start_direct_conversation(db, anna, ben["id"]).conversation_id
    logic.send_message(db, anna, conversation, "hello")
    public_rows = [logic.list_conversations(db, anna),
                   logic.get_conversation_messages(db, ben, conversation),
                   logic.get_profile(db, anna, ben["id"]),
                   logic.search_people(db, anna, "ben")]
    assert "private-anna@example.com" not in str(public_rows)
    assert "private-ben@example.com" not in str(public_rows)


def test_missing_smtp_disables_notify_button_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "notify.db")
    db.init_db()
    anna = make_user(db, "anna")
    ben = make_user(db, "ben")
    conversation = logic.start_direct_conversation(db, anna, ben["id"]).conversation_id
    monkeypatch.setattr(mail, "_smtp_settings", lambda: None)
    assert mail.smtp_configured() is False
    result = logic.notify_conversation(db, anna, conversation)
    assert not result.success and "not set up" in result.message.casefold()
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    renderer = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "show_notify_button")
    source = ast.unparse(renderer)
    assert "Email notifications are not set up" in ast.unparse(tree)
    assert "disabled=True" in source
