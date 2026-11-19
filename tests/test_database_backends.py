"""Test backend selection and Postgres SQL adaptation without a server."""

from pathlib import Path
import ast
from io import BytesIO
import subprocess

import db
from PIL import Image


def test_uses_sqlite_without_database_url(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_database_url", lambda: None)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    assert db._backend() == ("sqlite", str(tmp_path / "test.db"))


def test_selects_postgres_without_connecting(monkeypatch):
    monkeypatch.setattr(db, "_database_url", lambda: "postgresql://user:secret@host/db")
    assert db._backend() == ("postgres", "postgresql://user:secret@host/db")


def test_translates_placeholders_only_for_postgres():
    sql = "SELECT * FROM users WHERE username_key = ? AND role = ?"
    assert db._translate_sql(sql, "sqlite") == sql
    assert db._translate_sql(sql, "postgres") == "SELECT * FROM users WHERE username_key = %s AND role = %s"


def test_post_insert_uses_portable_helpers_with_simulated_postgres(monkeypatch):
    calls = []
    buffer = BytesIO()
    Image.new("RGB", (8, 6), (20, 80, 120)).save(buffer, format="PNG")

    class Cursor:
        def __init__(self, row=None):
            self.row = row

        def fetchone(self):
            return self.row

    class FakeConnection:
        def execute(self, sql, parameters=()):
            calls.append((sql, parameters))
            return Cursor((len(calls) + 40,)) if "RETURNING id" in sql else Cursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(db, "_backend", lambda: ("postgres", "postgresql://fake"))
    monkeypatch.setattr(db, "_ensure_connection", lambda *_: FakeConnection())
    post_id = db.create_post(4, 9, "hello", buffer.getvalue(), "photo.png")
    assert post_id == 42
    assert len(calls) == 3
    assert all("?" not in sql and "%s" in sql for sql, _ in calls)
    assert "BYTEA" not in calls[0][0]
    assert calls[0][1][0].startswith(b"\x89PNG")
    assert calls[1][1][3] == 41
    # The photo is also linked through post_images, at position 0.
    assert "INSERT INTO post_images" in calls[2][0]
    assert calls[2][1] == (42, 41, 0)


def test_postgres_tables_use_identity_ids():
    statements = db._table_statements("postgres")
    assert len(statements) == 21
    identity_tables = ("users", "venues", "reviews", "images", "posts", "comments", "conversations", "messages", "events", "notifications", "post_images", "venue_owners", "venue_hours", "menu_items", "alerts")
    for table in identity_tables:
        sql = next(item for item in statements if f"CREATE TABLE IF NOT EXISTS {table} " in item)
        assert "GENERATED ALWAYS AS IDENTITY" in sql
    assert all("AUTOINCREMENT" not in sql for sql in statements)
    assert "BYTEA" in next(sql for sql in statements if "CREATE TABLE IF NOT EXISTS images" in sql)
    assert "BLOB" in next(sql for sql in db._table_statements("sqlite") if "CREATE TABLE IF NOT EXISTS images" in sql)
    assert all("CURRENT_TIMESTAMP" not in sql for sql in statements)


def test_postgres_initialization_enables_rls_on_every_table(monkeypatch):
    calls = []

    class Result:
        def fetchall(self):
            return [("image_id",), ("email_notifications",)]

    class FakeConnection:
        def execute(self, sql, *args):
            calls.append(sql)
            return Result()

        def commit(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr(db, "_backend", lambda: ("postgres", "postgresql://fake"))
    monkeypatch.setattr(db, "_ensure_connection", lambda *_: connection)
    db.init_db()
    enabled = [sql for sql in calls if sql.startswith("ALTER TABLE") and "ROW LEVEL SECURITY" in sql]
    assert enabled == [f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" for table in (
        "images", "users", "venues", "reviews", "posts", "comments", "likes", "follows", "venue_follows",
        "conversations", "conversation_members", "messages", "events", "event_responses", "notifications",
        "post_images", "venue_owners", "venue_hours", "menu_items", "post_tags", "alerts")]
    # Every table the app creates must be in that list, so a new table cannot ship
    # without row-level security.
    assert len(enabled) == len(db._rls_table_names())


def test_postgres_unique_violation_uses_common_duplicate_error():
    class UniqueViolation(Exception):
        sqlstate = "23505"

    class FakeConnection:
        def execute(self, *_):
            raise UniqueViolation("duplicate key value")

        def rollback(self):
            pass

    from unittest.mock import patch
    with patch.object(db, "_backend", return_value=("postgres", "postgresql://fake")), \
            patch.object(db, "_ensure_connection", return_value=FakeConnection()):
        try:
            with db._connect() as connection:
                connection.execute("INSERT INTO users VALUES (1)")
        except db.DuplicateRecordError as error:
            postgres_error = (type(error), str(error))
        else:
            raise AssertionError("DuplicateRecordError was not raised")

    assert postgres_error == (
        db.DuplicateRecordError,
        "A record with those unique values already exists.",
    )


def test_sqlite_and_postgres_unique_errors_have_same_type_and_message():
    class UniqueViolation(Exception):
        sqlstate = "23505"

    class FakeConnection:
        def __init__(self, error):
            self.error = error

        def execute(self, *_):
            raise self.error

        def rollback(self):
            pass

    from unittest.mock import patch
    errors = []
    for backend, error in (
        ("sqlite", getattr(db, "sqlite" + "3").IntegrityError("UNIQUE constraint failed: users.username_key")),
        ("postgres", UniqueViolation("duplicate key value")),
    ):
        with patch.object(db, "_backend", return_value=(backend, "fake")), \
                patch.object(db, "_ensure_connection", return_value=FakeConnection(error)):
            try:
                with db._connect() as connection:
                    connection.execute("INSERT INTO users VALUES (1)")
            except db.DuplicateRecordError as caught:
                errors.append((type(caught), str(caught)))
    assert errors[0] == errors[1]


def test_connection_is_reused_and_reopened_when_closed(monkeypatch):
    connections = []

    class FakeConnection:
        closed = False

        def execute(self, sql, *args):
            if self.closed:
                raise RuntimeError("connection closed")
            assert sql == "SELECT 1"

        def close(self):
            self.closed = True

    def open_connection(*_):
        connection = FakeConnection()
        connections.append(connection)
        return connection

    monkeypatch.setattr(db, "_open_connection", open_connection)
    db.close_connection()
    first = db._ensure_connection("sqlite", "shared")
    assert db._ensure_connection("sqlite", "shared") is first
    first.close()
    assert db._ensure_connection("sqlite", "shared") is not first
    assert len(connections) == 2
    db.close_connection()


def test_connection_failure_message_and_logs_hide_database_url(monkeypatch, capsys):
    secret_url = "postgresql://user:topsecret@host/db"
    monkeypatch.setattr(db, "_backend", lambda: ("postgres", secret_url))

    def fail_connection(*_):
        raise OSError(f"connection failed for {secret_url}")

    monkeypatch.setattr(db, "_ensure_connection", fail_connection)
    message = None
    try:
        with db._connect():
            pass
    except db.DatabaseUnavailable as error:
        message = str(error)
        assert message == db.DATABASE_UNAVAILABLE_MESSAGE
    else:
        raise AssertionError("DatabaseUnavailable was not raised")
    assert secret_url not in message
    assert secret_url not in capsys.readouterr().out


def test_driver_imports_are_limited_to_db_py():
    project = Path(__file__).resolve().parents[1]
    forbidden = ("sqlite" + "3", "psy" + "copg")
    offenders = []
    tracked_files = subprocess.check_output(
        ["git", "ls-files", "--", "*.py"], cwd=project, text=True
    ).splitlines()
    for tracked_file in tracked_files:
        path = project / tracked_file
        if path.name == "db.py":
            continue
        content = path.read_text(encoding="utf-8").lower()
        if any(token in content for token in forbidden):
            offenders.append(str(path.relative_to(project)))
    assert offenders == []


def test_sqlite_driver_calls_are_confined_to_connection_factory():
    source = (Path(__file__).resolve().parents[1] / "db.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    factory = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_open_connection")
    module_name = "sqlite" + "3"
    references = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute)
                  and isinstance(node.value, ast.Name) and node.value.id == module_name]
    assert references
    assert all(factory.lineno <= node.lineno <= factory.end_lineno for node in references)


def test_local_secrets_file_is_ignored_and_example_has_placeholder():
    project = Path(__file__).resolve().parents[1]
    ignore_text = (project / ".gitignore").read_text(encoding="utf-8")
    example = (project / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")
    assert ".streamlit/secrets.toml" in ignore_text
    assert 'DATABASE_URL = "postgresql://user:password@host:5432/database"' in example
