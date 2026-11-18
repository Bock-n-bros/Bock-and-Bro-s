"""Store and retrieve application data using SQLite or Postgres."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

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
                _connection.execute("SELECT 1")
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
    return (isinstance(error, sqlite3.IntegrityError)
            and "unique" in str(error).lower()) or getattr(error, "sqlstate", None) == "23505"


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
    return [
        f"""CREATE TABLE IF NOT EXISTS users (
            id {identity}, username TEXT NOT NULL, username_key TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('customer', 'business')),
            created_at TEXT NOT NULL, failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until INTEGER
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
    ]


def init_db():
    """Create application tables and enable Postgres row-level security."""
    backend, _ = _backend()
    with _connect() as connection:
        for statement, table in zip(_table_statements(backend), ("users", "venues", "reviews")):
            connection.execute(statement)
            if backend == "postgres":
                connection.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


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


def create_user(username, password_hash, role):
    """Save a user account and return its identifier."""
    init_db()
    backend, _ = _backend()
    with _connect() as connection:
        return _insert(connection, backend,
            "INSERT INTO users (username, username_key, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, username.casefold(), password_hash, role, _iso_timestamp(None)))


def get_user_by_username(username):
    """Find a user without regard to username capitalization."""
    init_db()
    backend, _ = _backend()
    columns = ("id", "username", "password_hash", "role", "created_at", "failed_attempts", "locked_until")
    with _connect() as connection:
        row = _execute(connection, backend,
            "SELECT id, username, password_hash, role, created_at, failed_attempts, locked_until FROM users WHERE username_key = ?", (username.casefold(),)).fetchone()
        return _row_dict(row, columns)


def update_login_state(username, failed_attempts, locked_until):
    """Save the latest failed-login count and lock expiry."""
    backend, _ = _backend()
    with _connect() as connection:
        _execute(connection, backend, "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE username_key = ?", (failed_attempts, locked_until, username.casefold()))


def list_users():
    """Return users for test assertions without exposing account secrets."""
    init_db()
    backend, _ = _backend()
    columns = ("id", "username", "role")
    with _connect() as connection:
        return [_row_dict(row, columns) for row in _execute(connection, backend, "SELECT id, username, role FROM users").fetchall()]
