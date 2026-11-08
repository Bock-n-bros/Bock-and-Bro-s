"""Validate account actions and apply authentication rules."""

from dataclasses import dataclass
from datetime import datetime, timezone

import bcrypt


@dataclass
class AuthResult:
    """Describe the outcome of an authentication action."""

    success: bool
    message: str
    user: dict | None = None


def register_user(database, username, password, password_repeat, role, age_confirmed):
    """Validate and save a new account."""
    if not isinstance(username, str) or not 3 <= len(username) <= 20:
        return AuthResult(False, "Username must be 3 to 20 characters.")
    if not username.isascii() or not all(char.isalnum() or char == "_" for char in username):
        return AuthResult(False, "Username may contain only letters, digits, and underscores.")
    if database.get_user_by_username(username):
        return AuthResult(False, "That username is already taken.")
    if not isinstance(password, str) or len(password) < 8 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return AuthResult(False, "Password must be at least 8 characters and include a letter and a digit.")
    if password != password_repeat:
        return AuthResult(False, "The passwords do not match.")
    if role not in {"customer", "business"}:
        return AuthResult(False, "Choose customer or business.")
    if not age_confirmed:
        return AuthResult(False, "Confirm that you are 18 or older.")
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    database.create_user(username, password_hash, role)
    return AuthResult(True, "Account created.")


def login_user(database, username, password, now=None):
    """Authenticate a user and apply the consecutive-failure lockout."""
    current = _timestamp(now)
    user = database.get_user_by_username(username) if isinstance(username, str) else None
    if not user:
        return AuthResult(False, "Wrong username or password.")
    if user["locked_until"] is not None and current < user["locked_until"]:
        return AuthResult(False, "Wrong username or password.")
    valid = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))
    if not valid:
        failures = user["failed_attempts"] + 1
        locked_until = current + 15 * 60 if failures >= 5 else None
        database.update_login_state(user["username"], failures, locked_until)
        return AuthResult(False, "Wrong username or password.")
    database.update_login_state(user["username"], 0, None)
    return AuthResult(True, "Logged in.", {"username": user["username"], "role": user["role"]})


def _timestamp(now):
    """Convert the optional clock value to a UTC Unix timestamp."""
    if now is None:
        return int(datetime.now(timezone.utc).timestamp())
    if isinstance(now, datetime):
        return int(now.timestamp())
    return int(now)
