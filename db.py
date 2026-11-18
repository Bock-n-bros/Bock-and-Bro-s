"""Store and retrieve application data using SQLite or Postgres."""

import os
import sqlite3
from io import BytesIO
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

DB_PATH = Path(__file__).resolve().parent / "bocknbros.db"
DATABASE_UNAVAILABLE_MESSAGE = "Bock'n Bros can't reach the database right now. Please try again in a few minutes."

_connection = None
_connection_key = None


class DatabaseUnavailable(RuntimeError):
    """Describe a database connection failure without exposing credentials."""

    def __init__(self):
        super().__init__(DATABASE_UNAVAILABLE_MESSAGE)


class DuplicateRecordError(Exception):
    """Describe a uniqueness conflict consistently across database backends."""


def close_connection():
    """Close the shared connection, primarily for application shutdown and tests."""
    global _connection, _connection_key
    if _connection is not None:
        _connection.close()
    _connection = None
    _connection_key = None


def _database_url():
    """Read the configured Postgres URL from secrets or the environment."""
    try:
        import streamlit as st
        value = st.secrets.get("DATABASE_URL")
    except Exception:
        value = None
    return value or os.environ.get("DATABASE_URL")


def _backend():
    """Return the configured backend and its connection setting."""
    url = _database_url()
    return ("postgres", url) if url else ("sqlite", str(DB_PATH))


def _translate_sql(sql, backend):
    """Adapt parameter markers and identity types for the selected backend."""
    if backend == "sqlite":
        return sql
    return sql.replace("?", "%s")


def _open_connection(backend, setting):
    """Open a database connection for the selected backend."""
    if backend == "sqlite":
        return sqlite3.connect(setting)
    import psycopg
    return psycopg.connect(setting)


def _ensure_connection(backend, setting):
    """Reuse the active connection or reconnect after closure/config changes."""
    global _connection, _connection_key
    key = (backend, setting)
    is_closed = _connection is None
    if _connection is not None:
        try:
            if backend == "sqlite":
                _execute(_connection, backend, "SELECT 1")
            else:
                is_closed = bool(_connection.closed)
        except Exception:
            is_closed = True
    if _connection_key != key or is_closed:
        if _connection is not None:
            try:
                _connection.close()
            except Exception:
                pass
        _connection = _open_connection(backend, setting)
        _connection_key = key
    return _connection


def _is_unique_violation(error):
    """Recognize uniqueness errors raised by either supported driver."""
    sqlite_integrity = (error.__class__.__module__ == "sqlite3"
                        and error.__class__.__name__ == "IntegrityError")
    return (sqlite_integrity and "unique" in str(error).lower()) or getattr(error, "sqlstate", None) == "23505"


@contextmanager
def _connect():
    """Yield a shared connection and translate backend errors safely."""
    backend, setting = _backend()
    try:
        connection = _ensure_connection(backend, setting)
        try:
            yield connection
            connection.commit()
        except Exception as error:
            connection.rollback()
            if _is_unique_violation(error):
                raise DuplicateRecordError("A record with those unique values already exists.") from None
            raise
    except DuplicateRecordError:
        raise
    except Exception as error:
        # Driver messages may contain the full connection URL, so log only the type.
        print(f"Database connection failed ({type(error).__name__}).")
        raise DatabaseUnavailable() from None


def _execute(connection, backend, sql, parameters=()):
    """Execute parameterized SQL using the selected placeholder style."""
    return connection.execute(_translate_sql(sql, backend), parameters)


def _row_dict(row, columns=None):
    """Convert either driver's row representation to a dictionary."""
    if row is None:
        return None
    if hasattr(row, "keys"):
        return dict(row)
    return dict(zip(columns, row))


def _table_statements(backend):
    """Return portable table definitions with backend-specific identity syntax."""
    identity = "INTEGER PRIMARY KEY AUTOINCREMENT" if backend == "sqlite" else "INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
    image_bytes_type = "BLOB" if backend == "sqlite" else "BYTEA"
    return [
        f"""CREATE TABLE IF NOT EXISTS images (
            id {identity}, bytes {image_bytes_type} NOT NULL, mime_type TEXT NOT NULL,
            byte_size INTEGER NOT NULL, created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS users (
            id {identity}, google_sub TEXT NOT NULL UNIQUE, email TEXT NOT NULL,
            username TEXT NOT NULL, username_key TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL CHECK (role IN ('customer', 'business')),
            image_id INTEGER REFERENCES images(id), created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS venues (
            id {identity}, name TEXT NOT NULL, neighbourhood TEXT NOT NULL, address TEXT NOT NULL,
            venue_type TEXT NOT NULL, shows_football TEXT NOT NULL, latitude REAL NOT NULL,
            longitude REAL NOT NULL, description TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS reviews (
            id {identity}, venue_id INTEGER NOT NULL REFERENCES venues(id),
            user_id INTEGER NOT NULL REFERENCES users(id), atmosphere INTEGER NOT NULL,
            value INTEGER NOT NULL, quality INTEGER NOT NULL, super_bock_price REAL, comment TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE (venue_id, user_id)
        )""",
        f"""CREATE TABLE IF NOT EXISTS posts (
            id {identity}, user_id INTEGER NOT NULL REFERENCES users(id),
            venue_id INTEGER NOT NULL REFERENCES venues(id), text TEXT, image_id INTEGER REFERENCES images(id),
            created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS comments (
            id {identity}, post_id INTEGER NOT NULL REFERENCES posts(id),
            user_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL, created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS likes (
            post_id INTEGER NOT NULL REFERENCES posts(id), user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL, UNIQUE (post_id, user_id)
        )""",
        """CREATE TABLE IF NOT EXISTS follows (
            follower_id INTEGER NOT NULL REFERENCES users(id), followed_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL, UNIQUE (follower_id, followed_id)
        )""",
        """CREATE TABLE IF NOT EXISTS venue_follows (
            user_id INTEGER NOT NULL REFERENCES users(id), venue_id INTEGER NOT NULL REFERENCES venues(id),
            created_at TEXT NOT NULL, UNIQUE (user_id, venue_id)
        )""",
        f"""CREATE TABLE IF NOT EXISTS conversations (
            id {identity}, name TEXT, is_group INTEGER NOT NULL DEFAULT 0 CHECK (is_group IN (0, 1)),
            created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS conversation_members (
            conversation_id INTEGER NOT NULL REFERENCES conversations(id), user_id INTEGER NOT NULL REFERENCES users(id),
            joined_at TEXT NOT NULL, UNIQUE (conversation_id, user_id)
        )""",
        f"""CREATE TABLE IF NOT EXISTS messages (
            id {identity}, conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            user_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL, created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS events (
            id {identity}, conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            venue_id INTEGER NOT NULL REFERENCES venues(id), title TEXT NOT NULL, starts_at TEXT NOT NULL,
            max_attendees INTEGER, created_by INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS event_responses (
            event_id INTEGER NOT NULL REFERENCES events(id), user_id INTEGER NOT NULL REFERENCES users(id),
            response TEXT NOT NULL CHECK (response IN ('going', 'not_going')), responded_at TEXT NOT NULL,
            UNIQUE (event_id, user_id)
        )""",
    ]


def init_db():
    """Create application tables and enable Postgres row-level security."""
    backend, _ = _backend()
    with _connect() as connection:
        tables = ("images", "users", "venues", "reviews", "posts", "comments", "likes", "follows", "venue_follows",
                  "conversations", "conversation_members", "messages", "events", "event_responses")
        for statement, table in zip(_table_statements(backend), tables):
            _execute(connection, backend, statement)
            if backend == "postgres":
                _execute(connection, backend, f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        _ensure_user_image_column(connection, backend)


def _ensure_user_image_column(connection, backend):
    """Add the nullable image reference to users created by an earlier version."""
    if backend == "sqlite":
        columns = {row[1] for row in _execute(connection, backend, "PRAGMA table_info(users)").fetchall()}
    else:
        columns = {row[0] for row in _execute(connection, backend,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?", ("users",)).fetchall()}
    if "image_id" not in columns:
        _execute(connection, backend, "ALTER TABLE users ADD COLUMN image_id INTEGER REFERENCES images(id)")


def _insert(connection, backend, sql, parameters):
    """Insert a row and return its generated identifier."""
    if backend == "postgres":
        return _execute(connection, backend, sql + " RETURNING id", parameters).fetchone()[0]
    return _execute(connection, backend, sql, parameters).lastrowid


def insert_venue(venue):
    """Save a venue and return its identifier."""
    init_db()
    backend, _ = _backend()
    with _connect() as connection:
        return _insert(connection, backend,
            "INSERT INTO venues (name, neighbourhood, address, venue_type, shows_football, latitude, longitude, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (venue["name"], venue["neighbourhood"], venue["address"], venue["venue_type"], venue["shows_football"], venue["latitude"], venue["longitude"], venue["description"]))


def count_venues():
    """Return the number of stored venues."""
    init_db()
    backend, _ = _backend()
    with _connect() as connection:
        return _execute(connection, backend, "SELECT COUNT(*) FROM venues").fetchone()[0]


def get_all_venues():
    """Return every stored venue as a dictionary."""
    init_db()
    backend, _ = _backend()
    columns = ("id", "name", "neighbourhood", "address", "venue_type", "shows_football", "latitude", "longitude", "description")
    with _connect() as connection:
        rows = _execute(connection, backend, "SELECT * FROM venues ORDER BY name").fetchall()
        return [_row_dict(row, columns) for row in rows]


def get_venue_by_id(venue_id):
    """Find one venue by its identifier."""
    init_db()
    backend, _ = _backend()
    columns = ("id", "name", "neighbourhood", "address", "venue_type", "shows_football", "latitude", "longitude", "description")
    with _connect() as connection:
        return _row_dict(_execute(connection, backend, "SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone(), columns)


def save_review(venue_id, user_id, values, now=None):
    """Insert a review or update the user's existing review for the venue."""
    init_db()
    backend, _ = _backend()
    timestamp = _iso_timestamp(now)
    with _connect() as connection:
        existing = _execute(connection, backend, "SELECT id, created_at FROM reviews WHERE venue_id = ? AND user_id = ?", (venue_id, user_id)).fetchone()
        if existing:
            _execute(connection, backend, "UPDATE reviews SET atmosphere = ?, value = ?, quality = ?, super_bock_price = ?, comment = ?, updated_at = ? WHERE id = ?",
                (values["atmosphere"], values["value"], values["quality"], values["super_bock_price"], values["comment"], timestamp, existing[0]))
            return existing[0]
        return _insert(connection, backend,
            "INSERT INTO reviews (venue_id, user_id, atmosphere, value, quality, super_bock_price, comment, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (venue_id, user_id, values["atmosphere"], values["value"], values["quality"], values["super_bock_price"], values["comment"], timestamp, timestamp))


def get_user_review(user_id, venue_id):
    """Fetch one user's review for a venue, if present."""
    init_db()
    backend, _ = _backend()
    columns = ("id", "venue_id", "user_id", "atmosphere", "value", "quality", "super_bock_price", "comment", "created_at", "updated_at")
    with _connect() as connection:
        return _row_dict(_execute(connection, backend, "SELECT * FROM reviews WHERE user_id = ? AND venue_id = ?", (user_id, venue_id)).fetchone(), columns)


def get_reviews_for_venue(venue_id):
    """Fetch a venue's reviews newest first with reviewer usernames."""
    init_db()
    backend, _ = _backend()
    with _connect() as connection:
        cursor = _execute(connection, backend,
            "SELECT reviews.*, users.username FROM reviews JOIN users ON users.id = reviews.user_id WHERE reviews.venue_id = ? ORDER BY reviews.created_at DESC, reviews.id DESC", (venue_id,))
        columns = [item.name if hasattr(item, "name") else item[0] for item in cursor.description]
        return [_row_dict(row, columns) for row in cursor.fetchall()]


def count_reviews(venue_id=None):
    """Return the review count for one venue or the whole database."""
    init_db()
    backend, _ = _backend()
    with _connect() as connection:
        if venue_id is None:
            return _execute(connection, backend, "SELECT COUNT(*) FROM reviews").fetchone()[0]
        return _execute(connection, backend, "SELECT COUNT(*) FROM reviews WHERE venue_id = ?", (venue_id,)).fetchone()[0]


def get_review_summary(venue_id):
    """Calculate category, overall, price, and count summary values."""
    rows = get_reviews_for_venue(venue_id)
    if not rows:
        return {"atmosphere": None, "value": None, "quality": None, "overall": None, "review_count": 0, "average_super_bock_price": None}
    means = {key: sum(row[key] for row in rows) / len(rows) for key in ("atmosphere", "value", "quality")}
    prices = [row["super_bock_price"] for row in rows if row["super_bock_price"] is not None]
    return {"atmosphere": round(means["atmosphere"], 1), "value": round(means["value"], 1), "quality": round(means["quality"], 1), "overall": round(sum(means.values()) / 3, 1), "review_count": len(rows), "average_super_bock_price": round(sum(prices) / len(prices), 2) if prices else None}


def _iso_timestamp(now):
    """Return an ISO timestamp for a supplied or current UTC time."""
    if now is None:
        now = datetime.now(timezone.utc)
    if isinstance(now, datetime):
        return now.isoformat()
    return str(now)


def create_user(google_sub, email, username, role):
    """Save a Google profile and return its identifier."""
    init_db()
    backend, _ = _backend()
    with _connect() as connection:
        return _insert(connection, backend,
            "INSERT INTO users (google_sub, email, username, username_key, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (google_sub, email, username, username.casefold(), role, _iso_timestamp(None)))


def get_user_by_google_sub(google_sub):
    """Find a profile by its stable Google subject identifier."""
    init_db()
    backend, _ = _backend()
    columns = ("id", "google_sub", "email", "username", "username_key", "role", "created_at")
    with _connect() as connection:
        row = _execute(connection, backend,
            "SELECT id, google_sub, email, username, username_key, role, created_at FROM users WHERE google_sub = ?",
            (google_sub,)).fetchone()
        return _row_dict(row, columns)


def get_user_by_username(username):
    """Find a user without regard to username capitalization."""
    init_db()
    backend, _ = _backend()
    columns = ("id", "google_sub", "email", "username", "username_key", "role", "created_at")
    with _connect() as connection:
        row = _execute(connection, backend,
            "SELECT id, google_sub, email, username, username_key, role, created_at FROM users WHERE username_key = ?",
            (username.casefold(),)).fetchone()
        return _row_dict(row, columns)


def get_user_by_id(user_id):
    """Find a user's public details without email."""
    backend, _ = _backend()
    with _connect() as connection:
        row = _execute(connection, backend, "SELECT id, username, role, image_id FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_dict(row, ("id", "username", "role", "image_id"))


def list_users():
    """Return users for test assertions without exposing email addresses."""
    init_db()
    backend, _ = _backend()
    columns = ("id", "username", "role")
    with _connect() as connection:
        return [_row_dict(row, columns) for row in _execute(connection, backend, "SELECT id, username, role FROM users").fetchall()]


def _rows(cursor):
    """Convert fetched rows from either database driver to dictionaries."""
    columns = [column.name if hasattr(column, "name") else column[0] for column in cursor.description]
    return [_row_dict(row, columns) for row in cursor.fetchall()]


def _query(sql, values=()):
    """Run a portable query against the selected database."""
    backend, _ = _backend()
    with _connect() as connection:
        return _execute(connection, backend, sql, values)


def create_conversation(created_by, member_ids, name=None, is_group=False, now=None):
    """Create a conversation and its members atomically."""
    backend, _ = _backend()
    timestamp = _iso_timestamp(now)
    with _connect() as connection:
        conversation_id = _insert(connection, backend,
            "INSERT INTO conversations (name, is_group, created_by, created_at) VALUES (?, ?, ?, ?)",
            (name, int(is_group), created_by, timestamp))
        for member_id in member_ids:
            _execute(connection, backend,
                "INSERT INTO conversation_members (conversation_id, user_id, joined_at) VALUES (?, ?, ?)",
                (conversation_id, member_id, timestamp))
        return conversation_id


def find_direct_conversation(user_id, other_user_id):
    """Find an existing direct conversation between two users."""
    row = _query("SELECT c.id FROM conversations c JOIN conversation_members a ON a.conversation_id = c.id AND a.user_id = ? "
        "JOIN conversation_members b ON b.conversation_id = c.id AND b.user_id = ? "
        "WHERE c.is_group = 0 ORDER BY c.id LIMIT 1", (user_id, other_user_id)).fetchone()
    return row[0] if row else None


def is_conversation_member(conversation_id, user_id):
    """Check whether a user is a conversation member."""
    return _query("SELECT 1 FROM conversation_members WHERE conversation_id = ? AND user_id = ?",
                  (conversation_id, user_id)).fetchone() is not None


def add_message(conversation_id, user_id, text, now=None):
    """Save a message and return its id."""
    backend, _ = _backend()
    with _connect() as connection:
        return _insert(connection, backend,
            "INSERT INTO messages (conversation_id, user_id, text, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, user_id, text, _iso_timestamp(now)))


def get_messages(conversation_id, limit=100):
    """Return the newest messages oldest first, with author details."""
    cursor = _query("SELECT m.id, m.user_id, u.username, u.role, m.text, m.created_at FROM messages m "
        "JOIN users u ON u.id = m.user_id WHERE m.conversation_id = ? "
        "ORDER BY m.created_at DESC, m.id DESC LIMIT ?", (conversation_id, limit))
    return list(reversed(_rows(cursor)))


def get_conversations_for_user(user_id):
    """Return a user's conversations and their latest message."""
    cursor = _query("SELECT c.id, c.name, c.is_group, c.created_by, c.created_at, other.id AS other_user_id, "
        "other.username AS other_username, other.role AS other_role, other.image_id AS other_image_id, last.text AS last_message, "
        "last.user_id AS last_sender_id, last.created_at AS last_message_at FROM conversations c "
        "JOIN conversation_members me ON me.conversation_id = c.id AND me.user_id = ? "
        "LEFT JOIN conversation_members om ON om.conversation_id = c.id AND om.user_id <> ? AND c.is_group = 0 "
        "LEFT JOIN users other ON other.id = om.user_id LEFT JOIN messages last ON last.id = ("
        "SELECT id FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC, id DESC LIMIT 1)",
        (user_id, user_id))
    return _rows(cursor)


def get_conversation(conversation_id):
    """Fetch a conversation's public settings and creator."""
    cursor = _query("SELECT id, name, is_group, created_by, created_at FROM conversations WHERE id = ?",
                    (conversation_id,))
    return _row_dict(cursor.fetchone(), ("id", "name", "is_group", "created_by", "created_at"))


def get_conversation_members(conversation_id):
    """Return conversation members in stable creation order."""
    cursor = _query("SELECT u.id, u.username, u.role, cm.joined_at FROM conversation_members cm "
        "JOIN users u ON u.id = cm.user_id WHERE cm.conversation_id = ? ORDER BY cm.joined_at, u.id",
        (conversation_id,))
    return _rows(cursor)


def add_conversation_member(conversation_id, user_id, now=None):
    """Add a member and return whether a new row was inserted."""
    backend, _ = _backend()
    with _connect() as connection:
        exists = _execute(connection, backend,
            "SELECT 1 FROM conversation_members WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id)).fetchone()
        if exists is not None:
            return False
        _execute(connection, backend,
            "INSERT INTO conversation_members (conversation_id, user_id, joined_at) VALUES (?, ?, ?)",
            (conversation_id, user_id, _iso_timestamp(now)))
        return True


def remove_conversation_member(conversation_id, user_id):
    """Remove a user from a conversation."""
    _query("DELETE FROM conversation_members WHERE conversation_id = ? AND user_id = ?",
           (conversation_id, user_id))


def rename_conversation(conversation_id, name):
    """Save a group's display name."""
    _query("UPDATE conversations SET name = ? WHERE id = ?", (name, conversation_id))


def add_event(conversation_id, venue_id, title, starts_at, max_attendees, created_by, now=None):
    """Save an event and return its id."""
    backend, _ = _backend()
    with _connect() as connection:
        return _insert(connection, backend,
            "INSERT INTO events (conversation_id, venue_id, title, starts_at, max_attendees, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (conversation_id, venue_id, title, starts_at, max_attendees, created_by, _iso_timestamp(now)))


def get_event(event_id):
    """Fetch event details including its venue and creator names."""
    cursor = _query("SELECT e.id, e.conversation_id, e.venue_id, v.name AS venue_name, e.title, e.starts_at, "
        "e.max_attendees, e.created_by, u.username AS creator_username, e.created_at "
        "FROM events e JOIN venues v ON v.id = e.venue_id JOIN users u ON u.id = e.created_by WHERE e.id = ?",
        (event_id,))
    return _row_dict(cursor.fetchone(), ("id", "conversation_id", "venue_id", "venue_name", "title", "starts_at",
                                         "max_attendees", "created_by", "creator_username", "created_at"))


def get_events_for_conversation(conversation_id):
    """Fetch events in a conversation, ordered by start time."""
    cursor = _query("SELECT e.id, e.conversation_id, e.venue_id, v.name AS venue_name, e.title, e.starts_at, "
        "e.max_attendees, e.created_by, u.username AS creator_username, e.created_at "
        "FROM events e JOIN venues v ON v.id = e.venue_id JOIN users u ON u.id = e.created_by "
        "WHERE e.conversation_id = ? ORDER BY e.starts_at, e.id", (conversation_id,))
    return _rows(cursor)


def get_event_responses(event_id):
    """Return event responses with the attendee usernames."""
    cursor = _query("SELECT r.event_id, r.user_id, r.response, r.responded_at, u.username "
        "FROM event_responses r JOIN users u ON u.id = r.user_id WHERE r.event_id = ? "
        "ORDER BY r.responded_at, r.user_id", (event_id,))
    return _rows(cursor)


def get_event_response(event_id, user_id):
    """Find a user's response to an event, if any."""
    cursor = _query("SELECT response FROM event_responses WHERE event_id = ? AND user_id = ?",
                    (event_id, user_id))
    row = cursor.fetchone()
    return row[0] if row else None


def save_event_response(event_id, user_id, response, now=None):
    """Insert or change a user's response."""
    backend, _ = _backend()
    timestamp = _iso_timestamp(now)
    with _connect() as connection:
        exists = _execute(connection, backend,
            "SELECT 1 FROM event_responses WHERE event_id = ? AND user_id = ?", (event_id, user_id)).fetchone()
        if exists:
            _execute(connection, backend,
                "UPDATE event_responses SET response = ?, responded_at = ? WHERE event_id = ? AND user_id = ?",
                (response, timestamp, event_id, user_id))
        else:
            _execute(connection, backend,
                "INSERT INTO event_responses (event_id, user_id, response, responded_at) VALUES (?, ?, ?, ?)",
                (event_id, user_id, response, timestamp))


def delete_event(event_id):
    """Delete event responses and the event in one transaction."""
    backend, _ = _backend()
    with _connect() as connection:
        _execute(connection, backend, "DELETE FROM event_responses WHERE event_id = ?", (event_id,))
        _execute(connection, backend, "DELETE FROM events WHERE id = ?", (event_id,))


def _escape_like(text):
    """Escape wildcard characters in a LIKE search."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_users(text, exclude_user_id=None, limit=20):
    """Search public user details by username."""
    cursor = _query("SELECT id, username, role, image_id FROM users WHERE username_key LIKE ? ESCAPE '\\' "
        "AND id <> ? ORDER BY username_key LIMIT ?",
        (f"%{_escape_like(text.casefold())}%", exclude_user_id or 0, limit))
    return _rows(cursor)


def add_follow(follower_id, followed_id, now=None):
    """Save a follow unless that pair already exists."""
    backend, _ = _backend()
    with _connect() as connection:
        exists = _execute(connection, backend, "SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?",
                          (follower_id, followed_id)).fetchone()
        if exists is None:
            _execute(connection, backend, "INSERT INTO follows (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
                      (follower_id, followed_id, _iso_timestamp(now)))


def remove_follow(follower_id, followed_id):
    """Remove a follow if present."""
    _query("DELETE FROM follows WHERE follower_id = ? AND followed_id = ?", (follower_id, followed_id))


def is_following(follower_id, followed_id):
    """Check whether one user follows another."""
    return _query("SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?",
                  (follower_id, followed_id)).fetchone() is not None


def get_followers(user_id):
    """Return followers in username order."""
    return _rows(_query("SELECT u.id, u.username, u.role, u.image_id FROM follows f JOIN users u ON u.id = f.follower_id "
                        "WHERE f.followed_id = ? ORDER BY u.username_key", (user_id,)))


def get_following(user_id):
    """Return followed users in username order."""
    return _rows(_query("SELECT u.id, u.username, u.role, u.image_id FROM follows f JOIN users u ON u.id = f.followed_id "
                        "WHERE f.follower_id = ? ORDER BY u.username_key", (user_id,)))


def add_venue_follow(user_id, venue_id, now=None):
    """Save a venue follow unless already present."""
    backend, _ = _backend()
    with _connect() as connection:
        exists = _execute(connection, backend, "SELECT 1 FROM venue_follows WHERE user_id = ? AND venue_id = ?",
                          (user_id, venue_id)).fetchone()
        if exists is None:
            _execute(connection, backend, "INSERT INTO venue_follows (user_id, venue_id, created_at) VALUES (?, ?, ?)",
                      (user_id, venue_id, _iso_timestamp(now)))


def remove_venue_follow(user_id, venue_id):
    """Remove a venue follow if present."""
    _query("DELETE FROM venue_follows WHERE user_id = ? AND venue_id = ?", (user_id, venue_id))


def is_following_venue(user_id, venue_id):
    """Check whether a user follows a venue."""
    return _query("SELECT 1 FROM venue_follows WHERE user_id = ? AND venue_id = ?",
                  (user_id, venue_id)).fetchone() is not None


def get_followed_venues(user_id):
    """Return venues followed by a user."""
    return _rows(_query("SELECT v.id, v.name, v.neighbourhood, v.venue_type FROM venue_follows f "
                        "JOIN venues v ON v.id = f.venue_id WHERE f.user_id = ? ORDER BY v.name", (user_id,)))


def count_venue_followers(venue_id):
    """Count users following a venue."""
    return _query("SELECT COUNT(*) FROM venue_follows WHERE venue_id = ?", (venue_id,)).fetchone()[0]


def _post_query(where, values, limit):
    """Fetch post metadata without loading image contents."""
    cursor = _query("SELECT p.id, p.user_id, u.username, u.role, u.image_id AS author_image_id, p.venue_id, v.name AS venue_name, "
        "p.text, p.image_id, p.created_at FROM posts p JOIN users u ON u.id = p.user_id "
        "JOIN venues v ON v.id = p.venue_id " + where + " ORDER BY p.created_at DESC, p.id DESC LIMIT ?",
        (*values, limit))
    return _rows(cursor)


def _prepare_image(data, mime_type, max_width=1200):
    """Validate, resize and compress JPEG or PNG input."""
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("Photos can be at most 5 MB.")
    if mime_type not in {"image/jpeg", "image/png"}:
        raise ValueError("Photos must be JPG or PNG.")
    try:
        image = Image.open(BytesIO(data))
        expected = "JPEG" if mime_type == "image/jpeg" else "PNG"
        if image.format != expected:
            raise ValueError("That file is not a valid image.")
        image.load()
    except (OSError, Image.DecompressionBombError):
        raise ValueError("That file is not a valid image.") from None
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)), Image.Resampling.LANCZOS)
    output = BytesIO()
    if mime_type == "image/jpeg":
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(output, format="JPEG", optimize=True, quality=85)
    else:
        if image.mode not in ("RGB", "RGBA", "L"):
            image = image.convert("RGBA")
        image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def create_post(user_id, venue_id, text, image_bytes=None, image_name=None, now=None):
    """Save a post and its optional image in one transaction."""
    image_extension = Path(image_name or "").suffix.casefold() if image_bytes is not None else None
    mime_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(image_extension)
    cooked = _prepare_image(image_bytes, mime_type) if image_bytes is not None else None
    backend, _ = _backend()
    timestamp = _iso_timestamp(now)
    with _connect() as connection:
        image_id = None
        if image_bytes is not None:
            image_id = _insert(connection, backend,
                "INSERT INTO images (bytes, mime_type, byte_size, created_at) VALUES (?, ?, ?, ?)",
                (cooked, mime_type, len(cooked), timestamp))
        return _insert(connection, backend,
            "INSERT INTO posts (user_id, venue_id, text, image_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, venue_id, text, image_id, timestamp))


def get_post_image(image_id):
    """Fetch one image's binary content and metadata."""
    if image_id is None:
        return None
    row = _query("SELECT bytes, mime_type, byte_size, created_at FROM images WHERE id = ?", (image_id,)).fetchone()
    return _row_dict(row, ("bytes", "mime_type", "byte_size", "created_at"))


def get_image(image_id):
    """Fetch a stored image for a post or profile."""
    return get_post_image(image_id)


def get_profile_image_id(user_id):
    """Return a user's profile image id, if they have one."""
    row = _query("SELECT image_id FROM users WHERE id = ?", (user_id,)).fetchone()
    return row[0] if row else None


def set_profile_image(user_id, data, image_name, now=None):
    """Store a resized profile picture and replace the user's current image."""
    extension = Path(image_name or "").suffix.casefold()
    mime_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(extension)
    cooked = _prepare_image(data, mime_type, max_width=400)
    backend, _ = _backend()
    timestamp = _iso_timestamp(now)
    with _connect() as connection:
        current = _execute(connection, backend, "SELECT image_id FROM users WHERE id = ?", (user_id,)).fetchone()
        if current is None:
            return None
        image_id = _insert(connection, backend,
            "INSERT INTO images (bytes, mime_type, byte_size, created_at) VALUES (?, ?, ?, ?)",
            (cooked, mime_type, len(cooked), timestamp))
        _execute(connection, backend, "UPDATE users SET image_id = ? WHERE id = ?", (image_id, user_id))
        _delete_unused_image(connection, backend, current[0])
        return image_id


def remove_profile_image(user_id):
    """Clear a user's picture and delete its image row if no longer referenced."""
    backend, _ = _backend()
    with _connect() as connection:
        current = _execute(connection, backend, "SELECT image_id FROM users WHERE id = ?", (user_id,)).fetchone()
        if current is None:
            return False
        _execute(connection, backend, "UPDATE users SET image_id = NULL WHERE id = ?", (user_id,))
        _delete_unused_image(connection, backend, current[0])
        return True


def _delete_unused_image(connection, backend, image_id):
    """Delete an image only after no post or user references it."""
    if image_id is not None:
        _execute(connection, backend, "DELETE FROM images WHERE id = ? "
            "AND NOT EXISTS (SELECT 1 FROM posts WHERE posts.image_id = images.id) "
            "AND NOT EXISTS (SELECT 1 FROM users WHERE users.image_id = images.id)", (image_id,))


def get_image_file(image_id):
    """Return one image from the database for display."""
    return get_post_image(image_id)


def count_images():
    """Count stored images."""
    return _query("SELECT COUNT(*) FROM images").fetchone()[0]


def _post_columns():
    """Return posts visible in a user's feed, including metadata only."""
    return "WHERE p.user_id = ? OR p.user_id IN (SELECT followed_id FROM follows WHERE follower_id = ?) " \
        "OR p.venue_id IN (SELECT venue_id FROM venue_follows WHERE user_id = ?)"


def get_feed_posts(user_id, limit=50):
    """Fetch a user's feed without reading image bytes."""
    return _post_query(_post_columns(), (user_id, user_id, user_id), limit)


def get_venue_posts(venue_id, limit=50):
    """Fetch venue post metadata without reading image bytes."""
    return _post_query("WHERE p.venue_id = ?", (venue_id,), limit)


def get_user_posts(user_id, limit=50):
    """Fetch user post metadata without reading image bytes."""
    return _post_query("WHERE p.user_id = ?", (user_id,), limit)


def count_posts():
    """Count saved posts."""
    return _query("SELECT COUNT(*) FROM posts").fetchone()[0]


def get_post_by_id(post_id):
    """Return a post id when the post exists."""
    row = _query("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    return {"id": row[0]} if row else None


def add_comment(post_id, user_id, text, now=None):
    """Save a comment and return its identifier."""
    backend, _ = _backend()
    with _connect() as connection:
        return _insert(connection, backend,
            "INSERT INTO comments (post_id, user_id, text, created_at) VALUES (?, ?, ?, ?)",
            (post_id, user_id, text, _iso_timestamp(now)))


def get_comments_for_post(post_id):
    """Return comments oldest first with public author details."""
    cursor = _query("SELECT c.id, c.post_id, c.user_id, u.username, u.role, c.text, c.created_at "
        "FROM comments c JOIN users u ON u.id = c.user_id WHERE c.post_id = ? "
        "ORDER BY c.created_at, c.id", (post_id,))
    return _rows(cursor)


def get_comment(comment_id):
    """Find a comment by id for an ownership check."""
    cursor = _query("SELECT id, post_id, user_id, text, created_at FROM comments WHERE id = ?", (comment_id,))
    return _row_dict(cursor.fetchone(), ("id", "post_id", "user_id", "text", "created_at"))


def delete_comment(comment_id):
    """Delete a comment after logic has checked its author."""
    _query("DELETE FROM comments WHERE id = ?", (comment_id,))


def count_comments(post_id):
    """Count comments on a post."""
    return len(get_comments_for_post(post_id))


def add_like(post_id, user_id, now=None):
    """Insert one like; the unique constraint rejects duplicate pairs."""
    backend, _ = _backend()
    with _connect() as connection:
        _execute(connection, backend,
            "INSERT INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
            (post_id, user_id, _iso_timestamp(now)))


def is_liking(post_id, user_id):
    """Check whether a user has liked a post."""
    return _query("SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?", (post_id, user_id)).fetchone() is not None


def remove_like(post_id, user_id):
    """Remove a user's like from a post."""
    _query("DELETE FROM likes WHERE post_id = ? AND user_id = ?", (post_id, user_id))


def get_likes_for_posts(post_ids):
    """Return like pairs for a set of posts without SQL aggregation."""
    likes = []
    for post_id in post_ids:
        cursor = _query("SELECT post_id, user_id FROM likes WHERE post_id = ?", (post_id,))
        likes.extend(_rows(cursor))
    return likes


def count_likes(post_id):
    """Count a post's likes in Python using its like rows."""
    return len(get_likes_for_posts([post_id]))
