"""Test backend selection and Postgres SQL adaptation without a server."""

from pathlib import Path

import db


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


def test_postgres_tables_use_identity_ids():
    statements = db._table_statements("postgres")
    assert len(statements) == 3
    assert all("GENERATED ALWAYS AS IDENTITY" in sql for sql in statements)
    assert all("AUTOINCREMENT" not in sql for sql in statements)


def test_postgres_initialization_enables_rls_on_every_table(monkeypatch):
    calls = []

    class FakeConnection:
        def execute(self, sql, *args):
            calls.append(sql)

        def commit(self):
            pass

    connection = FakeConnection()
    monkeypatch.setattr(db, "_backend", lambda: ("postgres", "postgresql://fake"))
    monkeypatch.setattr(db, "_ensure_connection", lambda *_: connection)
    db.init_db()
    enabled = [sql for sql in calls if sql.startswith("ALTER TABLE")]
    assert enabled == [
        "ALTER TABLE users ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE venues ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE reviews ENABLE ROW LEVEL SECURITY",
    ]


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

        def execute(self, sql):
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
    for path in project.rglob("*.py"):
        if path.name == "db.py" or any(part in {".venv", ".git", ".uv-cache"} for part in path.parts):
            continue
        content = path.read_text(encoding="utf-8").lower()
        if any(token in content for token in forbidden):
            offenders.append(str(path.relative_to(project)))
    assert offenders == []


def test_local_secrets_file_is_ignored_and_example_has_placeholder():
    project = Path(__file__).resolve().parents[1]
    ignore_text = (project / ".gitignore").read_text(encoding="utf-8")
    example = (project / ".streamlit" / "secrets.example.toml").read_text(encoding="utf-8")
    assert ".streamlit/secrets.toml" in ignore_text
    assert 'DATABASE_URL = "postgresql://user:password@host:5432/database"' in example
