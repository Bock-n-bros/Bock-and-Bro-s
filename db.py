"""Store and retrieve application data."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "bocknbros.db"


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
