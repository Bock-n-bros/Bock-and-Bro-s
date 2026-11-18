"""Store and retrieve application data."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import uuid

DB_PATH = Path(__file__).resolve().parent / "bocknbros.db"
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"


@contextmanager
def _connect():
    """Open a connection to the configured database file."""
    connection = sqlite3.connect(DB_PATH)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    """Create application tables when they do not exist."""
    with _connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                google_sub TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                username TEXT NOT NULL,
                username_key TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL CHECK (role IN ('customer', 'business')),
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                venue_id INTEGER NOT NULL REFERENCES venues(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                atmosphere INTEGER NOT NULL,
                value INTEGER NOT NULL,
                quality INTEGER NOT NULL,
                super_bock_price REAL,
                comment TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (venue_id, user_id)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS venues (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                neighbourhood TEXT NOT NULL,
                address TEXT NOT NULL,
                venue_type TEXT NOT NULL,
                shows_football TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                description TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                venue_id INTEGER NOT NULL REFERENCES venues(id),
                text TEXT,
                image_path TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS follows (
                follower_id INTEGER NOT NULL REFERENCES users(id),
                followed_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL,
                UNIQUE (follower_id, followed_id)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS venue_follows (
                user_id INTEGER NOT NULL REFERENCES users(id),
                venue_id INTEGER NOT NULL REFERENCES venues(id),
                created_at TEXT NOT NULL,
                UNIQUE (user_id, venue_id)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                name TEXT,
                is_group INTEGER NOT NULL DEFAULT 0 CHECK (is_group IN (0, 1)),
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS conversation_members (
                conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                joined_at TEXT NOT NULL,
                UNIQUE (conversation_id, user_id)
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )


def insert_venue(venue):
    """Save a venue and return its identifier."""
    init_db()
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO venues (name, neighbourhood, address, venue_type, shows_football, latitude, longitude, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                venue["name"], venue["neighbourhood"], venue["address"], venue["venue_type"],
                venue["shows_football"], venue["latitude"], venue["longitude"], venue["description"],
            ),
        )
        return cursor.lastrowid


def count_venues():
    """Return the number of stored venues."""
    init_db()
    with _connect() as connection:
        return connection.execute("SELECT COUNT(*) FROM venues").fetchone()[0]


def get_all_venues():
    """Return every stored venue as a dictionary."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM venues ORDER BY name").fetchall()
        return [dict(row) for row in rows]


def get_venue_by_id(venue_id):
    """Find one venue by its identifier."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM venues WHERE id = ?", (venue_id,)).fetchone()
        return dict(row) if row else None


def save_review(venue_id, user_id, values, now=None):
    """Insert a review or update the user's existing review for the venue."""
    init_db()
    timestamp = _iso_timestamp(now)
    with _connect() as connection:
        existing = connection.execute(
            "SELECT id, created_at FROM reviews WHERE venue_id = ? AND user_id = ?",
            (venue_id, user_id),
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE reviews SET atmosphere = ?, value = ?, quality = ?, super_bock_price = ?, "
                "comment = ?, updated_at = ? WHERE id = ?",
                (values["atmosphere"], values["value"], values["quality"],
                 values["super_bock_price"], values["comment"], timestamp, existing[0]),
            )
            return existing[0]
        cursor = connection.execute(
            "INSERT INTO reviews (venue_id, user_id, atmosphere, value, quality, super_bock_price, comment, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (venue_id, user_id, values["atmosphere"], values["value"], values["quality"],
             values["super_bock_price"], values["comment"], timestamp, timestamp),
        )
        return cursor.lastrowid


def get_user_review(user_id, venue_id):
    """Fetch one user's review for a venue, if present."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM reviews WHERE user_id = ? AND venue_id = ?", (user_id, venue_id)
        ).fetchone()
        return dict(row) if row else None


def get_reviews_for_venue(venue_id):
    """Fetch a venue's reviews newest first with reviewer usernames."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT reviews.*, users.username FROM reviews JOIN users ON users.id = reviews.user_id "
            "WHERE reviews.venue_id = ? ORDER BY reviews.created_at DESC, reviews.id DESC",
            (venue_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def count_reviews(venue_id=None):
    """Return the review count for one venue or the whole database."""
    init_db()
    with _connect() as connection:
        if venue_id is None:
            return connection.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        return connection.execute("SELECT COUNT(*) FROM reviews WHERE venue_id = ?", (venue_id,)).fetchone()[0]


def get_review_summary(venue_id):
    """Calculate category, overall, price, and count summary values."""
    rows = get_reviews_for_venue(venue_id)
    if not rows:
        return {"atmosphere": None, "value": None, "quality": None, "overall": None,
                "review_count": 0, "average_super_bock_price": None}
    means = {key: sum(row[key] for row in rows) / len(rows)
             for key in ("atmosphere", "value", "quality")}
    prices = [row["super_bock_price"] for row in rows if row["super_bock_price"] is not None]
    return {"atmosphere": round(means["atmosphere"], 1), "value": round(means["value"], 1),
            "quality": round(means["quality"], 1), "overall": round(sum(means.values()) / 3, 1),
            "review_count": len(rows),
            "average_super_bock_price": round(sum(prices) / len(prices), 2) if prices else None}


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
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO users (google_sub, email, username, username_key, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (google_sub, email, username, username.casefold(), role),
        )
        return cursor.lastrowid


def get_user_by_google_sub(google_sub):
    """Find a profile by its stable Google subject identifier."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, google_sub, email, username, username_key, role, created_at "
            "FROM users WHERE google_sub = ?",
            (google_sub,),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_username(username):
    """Find a user without regard to username capitalization."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, google_sub, email, username, username_key, role, created_at "
            "FROM users WHERE username_key = ?",
            (username.casefold(),),
        ).fetchone()
        return dict(row) if row else None


def list_users():
    """Return users for test assertions without exposing email addresses."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT id, username, role FROM users").fetchall()
        return [dict(row) for row in rows]


def get_user_by_id(user_id):
    """Find a user's public details by identifier, without email."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def _escape_like(text):
    """Make % and _ in user input match literally in a LIKE pattern."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_users(text, exclude_user_id=None, limit=20):
    """Return users whose username contains the text, without email."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, username, role FROM users "
            "WHERE username_key LIKE ? ESCAPE '\\' AND id <> ? ORDER BY username_key LIMIT ?",
            (f"%{_escape_like(text.casefold())}%", exclude_user_id or 0, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def create_conversation(created_by, member_ids, name=None, is_group=False, now=None):
    """Save a conversation and all its members in one transaction."""
    timestamp = _iso_timestamp(now)
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO conversations (name, is_group, created_by, created_at) VALUES (?, ?, ?, ?)",
            (name, 1 if is_group else 0, created_by, timestamp),
        )
        conversation_id = cursor.lastrowid
        for member_id in member_ids:
            connection.execute(
                "INSERT INTO conversation_members (conversation_id, user_id, joined_at) VALUES (?, ?, ?)",
                (conversation_id, member_id, timestamp),
            )
        return conversation_id


def find_direct_conversation(user_id, other_user_id):
    """Return the id of the direct conversation between two users, if any."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT c.id FROM conversations c "
            "JOIN conversation_members a ON a.conversation_id = c.id AND a.user_id = ? "
            "JOIN conversation_members b ON b.conversation_id = c.id AND b.user_id = ? "
            "WHERE c.is_group = 0 ORDER BY c.id LIMIT 1",
            (user_id, other_user_id),
        ).fetchone()
        return row[0] if row else None


def is_conversation_member(conversation_id, user_id):
    """Return whether a user belongs to a conversation."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM conversation_members WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        return row is not None


def add_message(conversation_id, user_id, text, now=None):
    """Save a message and return its identifier."""
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO messages (conversation_id, user_id, text, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, user_id, text, _iso_timestamp(now)),
        )
        return cursor.lastrowid


def get_messages(conversation_id, limit=100):
    """Return the latest messages in a conversation, oldest first, with usernames."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT m.id, m.user_id, u.username, u.role, m.text, m.created_at "
            "FROM messages m JOIN users u ON u.id = m.user_id "
            "WHERE m.conversation_id = ? ORDER BY m.created_at DESC, m.id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]


def get_conversations_for_user(user_id):
    """Return a user's conversations with the other person and the last message."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT c.id, c.name, c.is_group, c.created_at, "
            "other.id AS other_user_id, other.username AS other_username, other.role AS other_role, "
            "last.text AS last_message, last.user_id AS last_sender_id, last.created_at AS last_message_at "
            "FROM conversations c "
            "JOIN conversation_members me ON me.conversation_id = c.id AND me.user_id = ? "
            "LEFT JOIN conversation_members om "
            "  ON om.conversation_id = c.id AND om.user_id <> ? AND c.is_group = 0 "
            "LEFT JOIN users other ON other.id = om.user_id "
            "LEFT JOIN messages last ON last.id = ("
            "  SELECT id FROM messages WHERE conversation_id = c.id "
            "  ORDER BY created_at DESC, id DESC LIMIT 1)",
            (user_id, user_id),
        ).fetchall()
        return [dict(row) for row in rows]


def add_follow(follower_id, followed_id, now=None):
    """Save that one user follows another; an existing follow is left unchanged."""
    with _connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?",
            (follower_id, followed_id),
        ).fetchone()
        if exists is None:
            connection.execute(
                "INSERT INTO follows (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
                (follower_id, followed_id, _iso_timestamp(now)),
            )


def remove_follow(follower_id, followed_id):
    """Delete a follow between two users, if it exists."""
    with _connect() as connection:
        connection.execute(
            "DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
            (follower_id, followed_id),
        )


def is_following(follower_id, followed_id):
    """Return whether one user follows another."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?",
            (follower_id, followed_id),
        ).fetchone()
        return row is not None


def get_followers(user_id):
    """Return the users who follow a user, sorted by username, without email."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT u.id, u.username, u.role FROM follows f JOIN users u ON u.id = f.follower_id "
            "WHERE f.followed_id = ? ORDER BY u.username_key",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_following(user_id):
    """Return the users a user follows, sorted by username, without email."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT u.id, u.username, u.role FROM follows f JOIN users u ON u.id = f.followed_id "
            "WHERE f.follower_id = ? ORDER BY u.username_key",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def add_venue_follow(user_id, venue_id, now=None):
    """Save that a user follows a venue; an existing follow is left unchanged."""
    with _connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM venue_follows WHERE user_id = ? AND venue_id = ?",
            (user_id, venue_id),
        ).fetchone()
        if exists is None:
            connection.execute(
                "INSERT INTO venue_follows (user_id, venue_id, created_at) VALUES (?, ?, ?)",
                (user_id, venue_id, _iso_timestamp(now)),
            )


def remove_venue_follow(user_id, venue_id):
    """Delete a user's follow of a venue, if it exists."""
    with _connect() as connection:
        connection.execute(
            "DELETE FROM venue_follows WHERE user_id = ? AND venue_id = ?",
            (user_id, venue_id),
        )


def is_following_venue(user_id, venue_id):
    """Return whether a user follows a venue."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM venue_follows WHERE user_id = ? AND venue_id = ?",
            (user_id, venue_id),
        ).fetchone()
        return row is not None


def get_followed_venues(user_id):
    """Return the venues a user follows, sorted by name."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT v.id, v.name, v.neighbourhood, v.venue_type FROM venue_follows f "
            "JOIN venues v ON v.id = f.venue_id WHERE f.user_id = ? ORDER BY v.name",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def count_venue_followers(venue_id):
    """Return how many users follow a venue."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM venue_follows WHERE venue_id = ?", (venue_id,)
        ).fetchone()
        return row[0]


_POST_COLUMNS = (
    "SELECT p.id, p.user_id, u.username, u.role, p.venue_id, v.name AS venue_name, "
    "p.text, p.image_path, p.created_at "
    "FROM posts p JOIN users u ON u.id = p.user_id JOIN venues v ON v.id = p.venue_id "
)


def create_post(user_id, venue_id, text, image_bytes=None, image_extension=None, now=None):
    """Save a post and its optional photo file, and return the post id."""
    image_name = None
    if image_bytes is not None:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        # A random name means users can never overwrite or guess each other's files.
        image_name = f"{uuid.uuid4().hex}{image_extension}"
        (UPLOADS_DIR / image_name).write_bytes(image_bytes)
    try:
        with _connect() as connection:
            cursor = connection.execute(
                "INSERT INTO posts (user_id, venue_id, text, image_path, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, venue_id, text, image_name, _iso_timestamp(now)),
            )
            return cursor.lastrowid
    except Exception:
        if image_name:
            (UPLOADS_DIR / image_name).unlink(missing_ok=True)
        raise


def get_image_file(image_name):
    """Return the full path of a stored photo, or None if it is missing."""
    if not image_name:
        return None
    path = UPLOADS_DIR / Path(image_name).name
    return path if path.is_file() else None


def get_feed_posts(user_id, limit=50):
    """Return posts by the user, people they follow and bars they follow, newest first."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            _POST_COLUMNS
            + "WHERE p.user_id = ? "
            "OR p.user_id IN (SELECT followed_id FROM follows WHERE follower_id = ?) "
            "OR p.venue_id IN (SELECT venue_id FROM venue_follows WHERE user_id = ?) "
            "ORDER BY p.created_at DESC, p.id DESC LIMIT ?",
            (user_id, user_id, user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def get_venue_posts(venue_id, limit=50):
    """Return posts tagged with a venue, newest first."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            _POST_COLUMNS + "WHERE p.venue_id = ? ORDER BY p.created_at DESC, p.id DESC LIMIT ?",
            (venue_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def get_user_posts(user_id, limit=50):
    """Return posts written by a user, newest first."""
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            _POST_COLUMNS + "WHERE p.user_id = ? ORDER BY p.created_at DESC, p.id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def count_posts():
    """Return the total number of posts (used by tests)."""
    with _connect() as connection:
        return connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
