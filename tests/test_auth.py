from pathlib import Path

import pytest

import db
import logic


@pytest.fixture
def user_db(tmp_path, monkeypatch):
    """Use an isolated database for every auth test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db


def complete_profile(database, **overrides):
    """Complete a valid default profile with optional field overrides."""
    values = {
        "google_sub": "test-sub-1",
        "email": "test@example.com",
        "username": "BroUser",
        "role": "customer",
        "age_confirmed": True,
    }
    values.update(overrides)
    return logic.complete_profile(database, **values)


@pytest.mark.parametrize("role", ["customer", "business"])
def test_complete_profile_succeeds_for_allowed_roles(user_db, role):
    result = complete_profile(user_db, role=role)
    assert result.success
    assert result.user == {
        "id": 1,
        "username": "BroUser",
        "role": role,
    }


@pytest.mark.parametrize("username", ["abc", "a" * 20])
def test_complete_profile_accepts_username_length_boundaries(user_db, username):
    assert complete_profile(user_db, username=username).success


@pytest.mark.parametrize("username", ["ab", "a" * 21, "bad-name", "bad name"])
def test_complete_profile_rejects_invalid_username(user_db, username):
    result = complete_profile(user_db, username=username)
    assert not result.success
    assert user_db.get_user_by_username(username) is None


def test_complete_profile_rejects_case_insensitive_duplicate_username(user_db):
    assert complete_profile(user_db, username="Bro").success
    assert not complete_profile(user_db, google_sub="test-sub-2", username="bro").success


def test_complete_profile_rejects_invalid_role(user_db):
    assert not complete_profile(user_db, role="admin").success


def test_complete_profile_rejects_unconfirmed_age(user_db):
    assert not complete_profile(user_db, age_confirmed=False).success


@pytest.mark.parametrize("google_sub", ["", None, 123])
def test_complete_profile_rejects_invalid_google_subject(user_db, google_sub):
    assert not complete_profile(user_db, google_sub=google_sub).success
    assert user_db.list_users() == []


def test_complete_profile_rejects_google_account_with_existing_profile(user_db):
    assert complete_profile(user_db).success
    result = complete_profile(user_db, username="AnotherUser")
    assert not result.success
    assert len(user_db.list_users()) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"username": "ab"},
        {"username": "bad-name"},
        {"role": "admin"},
        {"age_confirmed": False},
        {"google_sub": ""},
    ],
)
def test_rejected_profile_saves_nothing(user_db, overrides):
    assert not complete_profile(user_db, **overrides).success
    assert user_db.list_users() == []


def test_create_user_stores_google_identity_and_profile_fields(user_db):
    user_id = user_db.create_user(
        "test-sub-1", "test@example.com", "BroUser", "customer"
    )
    user = user_db.get_user_by_google_sub("test-sub-1")
    assert user["id"] == user_id
    assert user["google_sub"] == "test-sub-1"
    assert user["email"] == "test@example.com"
    assert user["username"] == "BroUser"
    assert user["username_key"] == "brouser"
    assert user["role"] == "customer"
    assert user["created_at"]


def test_get_user_by_google_sub_returns_none_for_unknown_subject(user_db):
    assert user_db.get_user_by_google_sub("missing-sub") is None


def test_get_user_by_username_is_case_insensitive(user_db):
    user_db.create_user("test-sub-1", "test@example.com", "BroUser", "customer")
    user = user_db.get_user_by_username("bRoUsEr")
    assert user["google_sub"] == "test-sub-1"


def test_list_users_does_not_include_email(user_db):
    user_db.create_user("test-sub-1", "private@example.com", "BroUser", "customer")
    listed = user_db.list_users()
    assert listed == [{"id": 1, "username": "BroUser", "role": "customer"}]
    assert "email" not in listed[0]


def test_database_rejects_duplicate_google_subject(user_db):
    user_db.create_user("test-sub-1", "one@example.com", "BroUser", "customer")
    with pytest.raises(Exception):
        user_db.create_user("test-sub-1", "two@example.com", "OtherUser", "customer")


def test_database_rejects_duplicate_username_key(user_db):
    user_db.create_user("test-sub-1", "one@example.com", "BroUser", "customer")
    with pytest.raises(Exception):
        user_db.create_user("test-sub-2", "two@example.com", "brouser", "customer")


def test_find_google_user_returns_required_dictionary_shape(user_db):
    user_db.create_user("test-sub-1", "private@example.com", "BroUser", "customer")
    assert logic.find_google_user(user_db, "test-sub-1") == {
        "id": 1,
        "username": "BroUser",
        "role": "customer",
    }


def test_find_google_user_returns_none_without_profile(user_db):
    assert logic.find_google_user(user_db, "missing-sub") is None


def test_profile_persists_after_database_reopen(user_db, tmp_path, monkeypatch):
    assert complete_profile(user_db).success
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    assert logic.find_google_user(db, "test-sub-1") == {
        "id": 1,
        "username": "BroUser",
        "role": "customer",
    }


def test_no_password_authentication_remains():
    project = Path(__file__).resolve().parents[1]
    source_files = ["app.py", "logic.py", "db.py", "seed.py", "pyproject.toml"]
    source = "\n".join(
        (project / filename).read_text(encoding="utf-8").lower()
        for filename in source_files
    )
    forbidden = [
        "bcrypt",
        "password_hash",
        "failed_attempts",
        "locked_until",
        "register_user",
        "login_user",
        "authenticate_user",
        "create_account",
        "has_valid_session_user",
    ]
    assert all(token not in source for token in forbidden)


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
