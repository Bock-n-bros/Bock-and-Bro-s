"""Store and retrieve application data."""

import sqlite3
from contextlib import contextmanager
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
                username TEXT NOT NULL,
                username_key TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('customer', 'business')),
                created_at TEXT NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until INTEGER
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


def create_user(username, password_hash, role):
    """Save a user account and return its identifier."""
    init_db()
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO users (username, username_key, password_hash, role, created_at) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (username, username.casefold(), password_hash, role),
        )
        return cursor.lastrowid


def get_user_by_username(username):
    """Find a user without regard to username capitalization."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, username, password_hash, role, created_at, failed_attempts, locked_until "
            "FROM users WHERE username_key = ?",
            (username.casefold(),),
        ).fetchone()
        return dict(row) if row else None


def update_login_state(username, failed_attempts, locked_until):
    """Save the latest failed-login count and lock expiry."""
    with _connect() as connection:
        connection.execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE username_key = ?",
            (failed_attempts, locked_until, username.casefold()),
        )


def list_users():
    """Return users for test assertions without exposing account secrets."""
    init_db()
    with _connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT id, username, role FROM users").fetchall()
        return [dict(row) for row in rows]
