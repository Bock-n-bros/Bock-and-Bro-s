"""Validate account actions and apply authentication rules."""

from dataclasses import dataclass
from datetime import datetime, timezone
import csv
from pathlib import Path

import bcrypt
import db


VENUE_TYPES = {"bar", "cervejaria", "pub", "rooftop", "café", "sports bar"}
VENUE_FIELDS = (
    "name", "neighbourhood", "address", "venue_type", "shows_football",
    "latitude", "longitude", "description",
)

MAP_STYLES = {
    "Light": "mapbox://styles/mapbox/light-v11",
    "Streets": "mapbox://styles/mapbox/streets-v12",
    "Dark": "mapbox://styles/mapbox/dark-v11",
    "Satellite": "mapbox://styles/mapbox/satellite-streets-v12",
}


def marker_color(avg_rating):
    """Return an RGB marker color for a venue's average rating."""
    if avg_rating is None:
        return [128, 128, 128]
    if avg_rating >= 4:
        return [46, 160, 67]
    if avg_rating >= 3:
        return [245, 166, 35]
    return [220, 53, 69]


def map_style_url(name):
    """Return the Mapbox style URL for a named map style."""
    return MAP_STYLES.get(name, MAP_STYLES["Light"])


def price_label(price, avg_rating=None):
    """Show a price when available, otherwise the rating or a no-review label."""
    if price is not None:
        return f"€{price:.2f}"
    if avg_rating is not None:
        return f"{avg_rating:.1f} ★"
    return "no reviews"


@dataclass
class AuthResult:
    """Describe the outcome of an authentication action."""

    success: bool
    message: str
    user: dict | None = None


@dataclass
class ReviewResult:
    """Describe the outcome of submitting a review."""

    success: bool
    message: str


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
    return AuthResult(True, "Logged in.", {
        "id": user["id"], "username": user["username"], "role": user["role"]
    })


def initialize_app_data():
    """Initialize storage and load demo venues when needed."""
    db.init_db()
    return load_venues(db, Path(__file__).resolve().parent / "data" / "venues.csv")


def authenticate_user(username, password, now=None):
    """Authenticate through the application's configured database."""
    return login_user(db, username, password, now=now)


def create_account(username, password, password_repeat, role, age_confirmed):
    """Register an account through the application's configured database."""
    return register_user(db, username, password, password_repeat, role, age_confirmed)


def get_venue(venue_id):
    """Fetch one venue for a screen."""
    return db.get_venue_by_id(venue_id)


def get_venues():
    """Fetch all venues for a screen."""
    return db.get_all_venues()


def get_venue_review_summary(venue_id):
    """Fetch a venue's review summary for a screen."""
    return db.get_review_summary(venue_id)


def get_customer_review(user_id, venue_id):
    """Fetch the current customer's review for a venue."""
    return db.get_user_review(user_id, venue_id)


def get_venue_reviews(venue_id):
    """Fetch a venue's reviews for display."""
    return db.get_reviews_for_venue(venue_id)


def find_app_venues(**filters):
    """Find and sort venues through the configured database."""
    return find_venues(db, **filters)


def submit_app_review(user, venue_id, atmosphere, value, quality,
                      super_bock_price=None, comment=None, now=None):
    """Submit the current user's review through the configured database."""
    return submit_review(db, user, venue_id, atmosphere, value, quality,
                         super_bock_price, comment, now=now)


def has_valid_session_user(user):
    """Check that a saved session has the identity fields used by screens."""
    return (isinstance(user, dict) and user.get("role") in {"customer", "business"}
            and user.get("id") is not None and user.get("username"))


def format_review_date(review):
    """Format review creation or update time for display."""
    created = datetime.fromisoformat(review["created_at"])
    updated = datetime.fromisoformat(review["updated_at"])
    if updated > created:
        return f"Updated {updated.day} {updated.strftime('%b %Y')}"
    return f"{created.day} {created.strftime('%b %Y')}"


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
    """Add valid CSV venues missing from the database and report invalid rows."""
    venues, errors = validate_venues_csv(csv_path)
    for error in errors:
        print(f"Venue loading: {error}")
    existing_names = {
        venue["name"].strip().casefold() for venue in database.get_all_venues()
    }
    loaded = 0
    for item in venues:
        name_key = item["name"].casefold()
        if name_key in existing_names:
            continue
        database.insert_venue(item)
        existing_names.add(name_key)
        loaded += 1
    return loaded


def find_venues(database, neighbourhood="All", venue_type="All", shows_football=False, search="", sort_by="name"):
    """Return filtered venues in the selected order."""
    venues = database.get_all_venues()
    query = search.strip().casefold() if isinstance(search, str) else ""
    matches = [
        venue for venue in venues
        if (neighbourhood == "All" or venue["neighbourhood"] == neighbourhood)
        and (venue_type == "All" or venue["venue_type"] == venue_type)
        and (not shows_football or venue["shows_football"] == "yes")
        and (not query or query in venue["name"].casefold())
    ]
    return sort_venues(matches, database, sort_by)


def submit_review(database, user, venue_id, atmosphere, value, quality,
                  super_bock_price=None, comment=None, now=None):
    """Check review permission and input, then save or update the review."""
    if not isinstance(user, dict) or user.get("role") != "customer" or not user.get("id"):
        return ReviewResult(False, "Only logged-in customers can submit reviews.")
    if database.get_venue_by_id(venue_id) is None:
        return ReviewResult(False, "That venue could not be found.")
    for label, score in (("Atmosphere", atmosphere), ("Value", value), ("Quality", quality)):
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
            return ReviewResult(False, f"{label} must be a whole number from 1 to 5.")
    if super_bock_price is not None:
        if isinstance(super_bock_price, bool) or not isinstance(super_bock_price, (int, float)) or not 0.5 <= super_bock_price <= 10:
            return ReviewResult(False, "Super Bock price must be between €0.50 and €10.00.")
        super_bock_price = round(float(super_bock_price), 2)
    if comment is not None:
        if not isinstance(comment, str) or len(comment) > 500:
            return ReviewResult(False, "Comment must be 500 characters or fewer.")
        comment = comment.strip() or None
    database.save_review(venue_id, user["id"], {
        "atmosphere": atmosphere, "value": value, "quality": quality,
        "super_bock_price": super_bock_price, "comment": comment,
    }, now=now)
    return ReviewResult(True, "Review saved.")


def sort_venues(venues, database, sort_by="name"):
    """Sort venues by name or a review summary, keeping missing data last."""
    if sort_by not in {"name", "overall", "atmosphere", "price", "reviews"}:
        sort_by = "name"
    if sort_by == "name":
        return sorted(venues, key=lambda venue: venue["name"].casefold())
    summaries = {venue["id"]: database.get_review_summary(venue["id"]) for venue in venues}
    key_name = {"overall": "overall", "atmosphere": "atmosphere", "price": "average_super_bock_price",
                "reviews": "review_count"}[sort_by]
    def ordering(venue):
        summary = summaries[venue["id"]]
        metric = summary[key_name]
        missing = metric is None or (sort_by == "reviews" and metric == 0)
        descending = sort_by != "price"
        return (missing, -metric if metric is not None and descending else metric or 0,
                venue["name"].casefold())
    return sorted(venues, key=ordering)


def can_view_venues(user):
    """Return whether a logged-in customer or business may view venues."""
    return isinstance(user, dict) and user.get("role") in {"customer", "business"}
