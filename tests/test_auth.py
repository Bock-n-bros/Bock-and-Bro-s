from pathlib import Path

import bcrypt
import pytest

import db
import logic


@pytest.fixture
def user_db(tmp_path, monkeypatch):
    """Use an isolated database for every auth test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db


def register(database, **overrides):
    """Register a valid default user with optional field overrides."""
    values = {
        "username": "BroUser",
        "password": "password1",
        "password_repeat": "password1",
        "role": "customer",
        "age_confirmed": True,
    }
    values.update(overrides)
    return logic.register_user(database, **values)


@pytest.mark.parametrize("role", ["customer", "business"])
def test_register_valid_roles_succeeds(user_db, role):
    result = register(user_db, role=role)
    assert result.success
    assert user_db.get_user_by_username("BroUser")["role"] == role


@pytest.mark.parametrize("username", ["abc", "a" * 20])
def test_register_accepts_username_length_boundaries(user_db, username):
    assert register(user_db, username=username).success


def test_register_accepts_eight_character_password(user_db):
    assert register(user_db, password="abcde123", password_repeat="abcde123").success


@pytest.mark.parametrize("username", ["ab", "a" * 21, "bad-name", "bad name"])
def test_register_rejects_invalid_username(user_db, username):
    result = register(user_db, username=username)
    assert not result.success
    assert user_db.get_user_by_username(username) is None


def test_register_rejects_case_insensitive_duplicate(user_db):
    assert register(user_db, username="Bro").success
    assert not register(user_db, username="bro").success


@pytest.mark.parametrize("password", ["short1", "abcdefgh", "12345678"])
def test_register_rejects_weak_passwords(user_db, password):
    assert not register(user_db, password=password, password_repeat=password).success


def test_register_rejects_mismatched_passwords(user_db):
    assert not register(user_db, password_repeat="different1").success


def test_register_rejects_invalid_role(user_db):
    assert not register(user_db, role="admin").success


def test_register_rejects_unconfirmed_age(user_db):
    assert not register(user_db, age_confirmed=False).success


@pytest.mark.parametrize(
    "overrides",
    [
        {"username": "ab"},
        {"username": "bad-name"},
        {"password": "weak", "password_repeat": "weak"},
        {"password_repeat": "different1"},
        {"role": "admin"},
        {"age_confirmed": False},
    ],
)
def test_rejected_registration_saves_nothing(user_db, overrides):
    assert not register(user_db, **overrides).success
    assert user_db.list_users() == []


@pytest.mark.parametrize("role", ["customer", "business"])
def test_login_succeeds_for_each_role(user_db, role):
    assert register(user_db, role=role).success
    result = logic.login_user(user_db, "BroUser", "password1")
    assert result.success
    assert result.user["role"] == role


def test_login_uses_same_generic_error_for_unknown_user_and_wrong_password(user_db):
    assert register(user_db).success
    wrong_password = logic.login_user(user_db, "BroUser", "incorrect1")
    unknown_user = logic.login_user(user_db, "missing", "incorrect1")
    assert wrong_password.message == "Wrong username or password."
    assert unknown_user.message == wrong_password.message


def test_failed_login_increments_attempt_count(user_db):
    register(user_db)
    logic.login_user(user_db, "BroUser", "wrongpass1")
    assert user_db.get_user_by_username("BroUser")["failed_attempts"] == 1


def test_fifth_failed_attempt_locks_account_for_fifteen_minutes(user_db):
    register(user_db)
    now = 1_800_000_000
    for _ in range(5):
        result = logic.login_user(user_db, "BroUser", "wrongpass1", now=now)
    user = user_db.get_user_by_username("BroUser")
    assert not result.success
    assert user["failed_attempts"] == 5
    assert user["locked_until"] == now + 15 * 60


def test_login_is_refused_during_lock_and_allowed_after_expiry(user_db):
    register(user_db)
    now = 1_800_000_000
    for _ in range(5):
        logic.login_user(user_db, "BroUser", "wrongpass1", now=now)
    locked = logic.login_user(user_db, "BroUser", "password1", now=now + 14 * 60)
    expired = logic.login_user(user_db, "BroUser", "password1", now=now + 15 * 60)
    assert not locked.success
    assert expired.success


def test_successful_login_resets_failed_attempts(user_db):
    register(user_db)
    for _ in range(3):
        logic.login_user(user_db, "BroUser", "wrongpass1")
    assert logic.login_user(user_db, "BroUser", "password1").success
    assert user_db.get_user_by_username("BroUser")["failed_attempts"] == 0


def test_password_is_stored_as_bcrypt_hash(user_db):
    register(user_db)
    stored = user_db.get_user_by_username("BroUser")["password_hash"]
    assert stored != "password1"
    assert bcrypt.checkpw(b"password1", stored.encode("utf-8"))


def test_user_can_login_after_database_reopen(user_db, tmp_path, monkeypatch):
    register(user_db)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    assert logic.login_user(db, "BroUser", "password1").success


def test_only_db_py_uses_sqlite_token():
    project = Path(__file__).resolve().parents[1]
    token = "sqlite" + "3"
    offenders = [
        str(path.relative_to(project))
        for path in project.rglob("*.py")
        if path.name != "db.py"
        and not any(part in {".venv", ".git", ".uv-cache", ".pytest-tmp"} for part in path.parts)
        and token in path.read_text(encoding="utf-8").lower()
    ]
    assert offenders == []
