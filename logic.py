"""Validate account actions and apply authentication rules."""

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
from pathlib import Path

import bcrypt


VENUE_TYPES = {"bar", "cervejaria", "pub", "rooftop", "café", "sports bar"}
VENUE_FIELDS = (
    "name", "neighbourhood", "address", "venue_type", "shows_football",
    "latitude", "longitude", "description",
)


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


def validate_venue(row):
    """Return a normalized venue or a validation reason."""
    for field in ("name", "neighbourhood", "address"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            return None, f"{field} must not be empty"
    venue_type = row.get("venue_type", "").strip().casefold()
    if venue_type not in VENUE_TYPES:
        return None, "venue_type is not allowed"
    shows_football = row.get("shows_football", "").strip().casefold()
    if shows_football not in {"yes", "no"}:
        return None, "shows_football must be yes or no"
    try:
        latitude = float(row.get("latitude", ""))
    except (TypeError, ValueError):
        return None, "latitude must be a number between 38.68 and 38.80"
    try:
        longitude = float(row.get("longitude", ""))
    except (TypeError, ValueError):
        return None, "longitude must be a number between -9.25 and -9.08"
    if not 38.68 <= latitude <= 38.80:
        return None, "latitude must be between 38.68 and 38.80"
    if not -9.25 <= longitude <= -9.08:
        return None, "longitude must be between -9.25 and -9.08"
    return {
        "name": row["name"].strip(),
        "neighbourhood": row["neighbourhood"].strip(),
        "address": row["address"].strip(),
        "venue_type": venue_type,
        "shows_football": shows_football,
        "latitude": latitude,
        "longitude": longitude,
        "description": row.get("description", "").strip(),
    }, None


def validate_venues_csv(csv_path):
    """Read and validate CSV rows without accessing the database."""
    path = Path(csv_path)
    if not path.exists():
        return [], ["CSV file not found"]
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                return [], ["CSV is empty and has no rows"]
            if any(field not in reader.fieldnames for field in VENUE_FIELDS):
                return [], ["CSV is missing required columns"]
            valid = []
            errors = []
            has_rows = False
            for row_number, row in enumerate(reader, start=2):
                has_rows = True
                normalized, reason = validate_venue(row)
                if reason:
                    errors.append(f"row {row_number}: {reason}")
                else:
                    valid.append(normalized)
            if not has_rows:
                errors.append("CSV has no rows")
            return valid, errors
    except (OSError, UnicodeError, csv.Error) as error:
        return [], [f"CSV could not be read: {error}"]


def load_venues(database, csv_path):
    """Load valid venues into an empty database and report skipped rows."""
    if database.count_venues() > 0:
        return 0
    venues, errors = validate_venues_csv(csv_path)
    for error in errors:
        print(f"Venue loading: {error}")
    for item in venues:
        database.insert_venue(item)
    return len(venues)


def find_venues(database, neighbourhood="All", venue_type="All", shows_football=False, search=""):
    """Return venues matching the selected filters, sorted by name."""
    venues = database.get_all_venues()
    query = search.strip().casefold() if isinstance(search, str) else ""
    return [
        venue for venue in venues
        if (neighbourhood == "All" or venue["neighbourhood"] == neighbourhood)
        and (venue_type == "All" or venue["venue_type"] == venue_type)
        and (not shows_football or venue["shows_football"] == "yes")
        and (not query or query in venue["name"].casefold())
    ]


def can_view_venues(user):
    """Return whether a logged-in customer or business may view venues."""
    return isinstance(user, dict) and user.get("role") in {"customer", "business"}
