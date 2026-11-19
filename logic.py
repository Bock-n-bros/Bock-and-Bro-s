"""Validate account actions and apply authentication rules."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import math
from zoneinfo import ZoneInfo
import csv
from pathlib import Path

import db
import mail


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


WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather(code):
    """Return a readable label for a WMO weather code."""
    try:
        return WEATHER_DESCRIPTIONS.get(int(code), "Unknown conditions")
    except (TypeError, ValueError):
        return "Unknown conditions"


def is_terrace_weather(temperature, precipitation, measured_precipitation,
                       rain_chance, weather_code):
    """Return whether current and observed weather suits a terrace."""
    try:
        values = [float(value) for value in (
            temperature, precipitation, measured_precipitation, rain_chance,
        )]
        code = int(weather_code)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for value in values):
        return False
    temperature, precipitation, measured_precipitation, rain_chance = values
    return (
        temperature >= 18
        and precipitation == 0
        and measured_precipitation == 0
        and rain_chance < 30
        and code in {0, 1, 2}
    )


def closest_station(lat, lon, stations):
    """Return the nearest station from a list of IPMA GeoJSON features."""
    nearest = None
    nearest_distance = float("inf")
    for station in stations or []:
        try:
            properties = station.get("properties", station)
            coordinates = station.get("geometry", {}).get("coordinates")
            if coordinates:
                station_lon, station_lat = map(float, coordinates[:2])
            else:
                station_lat = float(station["latitude"])
                station_lon = float(station["longitude"])
            lat1, lat2 = math.radians(float(lat)), math.radians(station_lat)
            delta_lat = lat2 - lat1
            delta_lon = math.radians(station_lon - float(lon))
            haversine = (
                math.sin(delta_lat / 2) ** 2
                + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
            )
            distance = 2 * math.asin(min(1, math.sqrt(haversine)))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if distance < nearest_distance:
            nearest = station
            nearest_distance = distance
    return nearest


def marker_color(avg_rating):
    """Return fill and outline RGB colors for a venue's average rating."""
    if avg_rating is None:
        return {"fill": [255, 255, 255], "line": [217, 150, 15]}
    if avg_rating >= 4:
        color = [46, 139, 87]
        return {"fill": color, "line": color}
    if avg_rating >= 3:
        color = [217, 150, 15]
        return {"fill": color, "line": color}
    color = [196, 52, 44]
    return {"fill": color, "line": color}


def build_map_rows(venues, summaries, minimum_rating="All"):
    """Build map marker rows from venues and their shared review summaries."""
    rows = []
    threshold = float(minimum_rating[:-1]) if minimum_rating != "All" else None
    for venue in venues:
        summary = summaries[venue["id"]]
        rating = summary["overall"]
        if threshold is not None and (rating is None or rating < threshold):
            continue
        colors = marker_color(rating)
        price = summary["lowest_super_bock_price"]
        rows.append({
            "id": venue["id"], "name": venue["name"],
            "neighbourhood": venue["neighbourhood"],
            "latitude": venue["latitude"], "longitude": venue["longitude"],
            "rating": rating,
            "taste": f"{summary['quality']:.1f}" if summary["quality"] is not None else "no reviews",
            "vibe": f"{summary['atmosphere']:.1f}" if summary["atmosphere"] is not None else "no reviews",
            "price": price, "pin_label": price_label(price, rating),
            "fill": colors["fill"], "line": colors["line"],
        })
    return rows


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


@dataclass
class MessageResult:
    """Describe the outcome of a messaging action."""

    success: bool
    message: str
    conversation_id: int | None = None


@dataclass
class EventResult:
    """Describe the outcome of an event action."""

    success: bool
    message: str
    event_id: int | None = None


@dataclass
class FollowResult:
    """Describe the outcome of a follow or unfollow action."""

    success: bool
    message: str


@dataclass
class PostResult:
    """Describe the outcome of creating a post."""

    success: bool
    message: str
    post_id: int | None = None


@dataclass
class CommentResult:
    """Describe the outcome of adding or deleting a comment."""

    success: bool
    message: str
    comment_id: int | None = None


@dataclass
class LikeResult:
    """Describe the outcome of toggling a like."""

    success: bool
    message: str
    liked: bool = False


@dataclass
class ProfilePictureResult:
    """Describe the outcome of changing a profile picture."""

    success: bool
    message: str


@dataclass
class NotificationResult:
    """Describe the outcome of a notification request."""

    success: bool
    message: str
    sent_count: int = 0


MAX_POST_LENGTH = 500
MAX_LOCATION_LENGTH = 60
MAX_TAGS = 10
IMAGE_TYPES = ["jpg", "jpeg", "png", "heic", "heif", "webp"]
MAX_MESSAGE_LENGTH = 1000
MAX_GROUP_NAME_LENGTH = 50
MAX_GROUP_MEMBERS = 20
LISBON = ZoneInfo("Europe/Lisbon")


def find_google_user(database, google_sub):
    """Return the public user dictionary for a Google subject."""
    user = database.get_user_by_google_sub(google_sub)
    if user is None:
        return None
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


def complete_profile(database, google_sub, email, username, role, age_confirmed):
    """Validate and save a profile for a Google account."""
    if not isinstance(google_sub, str) or not google_sub.strip():
        return AuthResult(False, "Google account could not be identified.")
    if not isinstance(username, str) or not 3 <= len(username) <= 20:
        return AuthResult(False, "Username must be 3 to 20 characters.")
    if not username.isascii() or not all(char.isalnum() or char == "_" for char in username):
        return AuthResult(False, "Username may contain only letters, digits, and underscores.")
    if database.get_user_by_google_sub(google_sub):
        return AuthResult(False, "This Google account already has a profile.")
    if database.get_user_by_username(username):
        return AuthResult(False, "That username is already taken.")
    if role not in {"customer", "business"}:
        return AuthResult(False, "Choose customer or business.")
    if not age_confirmed:
        return AuthResult(False, "Confirm that you are 18 or older.")
    database.create_user(google_sub, email, username, role)
    return AuthResult(True, "Profile saved.", find_google_user(database, google_sub))


def initialize_app_data():
    """Initialize storage and load demo venues when needed."""
    db.init_db()
    return load_venues(db, Path(__file__).resolve().parent / "data" / "venues.csv")


def find_app_google_user(google_sub):
    """Find the logged-in user's public profile."""
    return find_google_user(db, google_sub)


def complete_app_profile(google_sub, email, username, role, age_confirmed):
    """Complete a profile through the configured database."""
    return complete_profile(db, google_sub, email, username, role, age_confirmed)


def get_venue(venue_id):
    """Fetch one venue for a screen."""
    return db.get_venue_by_id(venue_id)


def get_venues():
    """Fetch all venues for a screen."""
    return db.get_all_venues()


def remove_demo_venues():
    """Remove eligible demo venues through the configured database."""
    return db.remove_demo_venues()


def get_venue_review_summary(venue_id):
    """Fetch a venue's review summary for a screen."""
    return db.get_review_summary(venue_id)


def get_review_summaries(database):
    """Return {venue_id: summary} for all venues; venues without reviews get an empty summary."""
    summaries = database.get_all_review_summaries()
    empty = {**database.summarize_reviews([]), "lowest_super_bock_price": None}
    return {venue["id"]: summaries.get(venue["id"], dict(empty)) for venue in database.get_all_venues()}


def get_all_venue_review_summaries():
    """Fetch every venue's review summary in one database round trip (for lists and the map)."""
    return get_review_summaries(db)


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


def format_review_date(review):
    """Format review creation or update time for display."""
    created = datetime.fromisoformat(review["created_at"])
    updated = datetime.fromisoformat(review["updated_at"])
    if updated > created:
        return f"Updated {updated.day} {updated.strftime('%b %Y')}"
    return f"{created.day} {created.strftime('%b %Y')}"


def cheapest_review_price(reviews):
    """Return the lowest logged Super Bock price, if any review has one."""
    prices = [review["super_bock_price"] for review in reviews
              if review.get("super_bock_price") is not None]
    return min(prices) if prices else None


def format_venue_card_summary(summary, cheapest_price):
    """Format a venue's score, review count and cheapest logged price."""
    if not summary["review_count"]:
        return "No reviews yet"
    price_text = (
        f"from €{cheapest_price:.2f}" if cheapest_price is not None
        else "no price logged"
    )
    return f"★ {summary['overall']:.1f} · {summary['review_count']} reviews · {price_text}"


def review_rating(review):
    """Return one review's mean rating rounded to one decimal place."""
    scores = [review[field] for field in ("atmosphere", "value", "quality")]
    return round(sum(scores) / len(scores), 1)


def format_time_ago(timestamp, now=None):
    """Format a review timestamp as a short relative age."""
    created = datetime.fromisoformat(timestamp)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    seconds = max(0, int((now - created).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        amount, unit = seconds // 60, "minute"
    elif seconds < 86400:
        amount, unit = seconds // 3600, "hour"
    else:
        amount, unit = seconds // 86400, "day"
    suffix = "" if amount == 1 else "s"
    return f"{amount} {unit}{suffix} ago"


def review_preview(reviews, now=None):
    """Return display data for the three newest venue reviews."""
    preview = []
    for review in reviews[:3]:
        preview.append({
            "username": review["username"],
            "rating": review_rating(review),
            "comment": (review.get("comment") or "").strip()[:140],
            "time_ago": format_time_ago(review["created_at"], now),
        })
    return preview


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
    """Seed valid CSV venues only when the database has no venues."""
    if database.get_all_venues():
        return 0
    venues, errors = validate_venues_csv(csv_path)
    for error in errors:
        print(f"Venue loading: {error}")
    existing_names = set()
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
    # One query for all venues instead of one per venue (matters on Supabase).
    all_summaries = database.get_all_review_summaries()
    empty = database.summarize_reviews([])
    summaries = {venue["id"]: all_summaries.get(venue["id"], empty) for venue in venues}
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


def _is_logged_in(user):
    """Return whether a user dictionary belongs to a logged-in profile."""
    return isinstance(user, dict) and bool(user.get("id")) and user.get("role") in {"customer", "business"}


def search_people(database, user, text):
    """Find other users by username; an empty search finds nobody."""
    if not _is_logged_in(user) or not isinstance(text, str) or not text.strip():
        return []
    return database.search_users(text.strip(), exclude_user_id=user["id"])


def start_direct_conversation(database, user, other_user_id, now=None):
    """Open the direct conversation with another user, creating it only once."""
    if not _is_logged_in(user):
        return MessageResult(False, "Log in to send messages.")
    if other_user_id == user["id"]:
        return MessageResult(False, "You cannot message yourself.")
    if database.get_user_by_id(other_user_id) is None:
        return MessageResult(False, "That user could not be found.")
    existing = database.find_direct_conversation(user["id"], other_user_id)
    if existing is not None:
        return MessageResult(True, "Conversation opened.", existing)
    conversation_id = database.create_conversation(
        user["id"], [user["id"], other_user_id], now=now
    )
    return MessageResult(True, "Conversation started.", conversation_id)


def create_group_conversation(database, user, name, member_ids, now=None):
    """Create a named or unnamed group with the current user as its owner."""
    if not _is_logged_in(user):
        return MessageResult(False, "Log in to create a group.")
    if name is not None and not isinstance(name, str):
        return MessageResult(False, "Group name must be text.")
    name = name.strip() if name else None
    name = name or None
    if name and len(name) > MAX_GROUP_NAME_LENGTH:
        return MessageResult(False, "Group names can be at most 50 characters.")
    if not isinstance(member_ids, (list, tuple)):
        return MessageResult(False, "Choose group members.")
    if len(member_ids) < 2:
        return MessageResult(False, "A group needs at least three members, including you.")
    if len(member_ids) + 1 > MAX_GROUP_MEMBERS:
        return MessageResult(False, "Groups can have at most 20 members.")
    if user["id"] in member_ids or len(set(member_ids)) != len(member_ids):
        return MessageResult(False, "Choose each other member once.")
    if any(database.get_user_by_id(member_id) is None for member_id in member_ids):
        return MessageResult(False, "A selected member could not be found.")
    conversation_id = database.create_conversation(
        user["id"], [user["id"], *member_ids], name=name, is_group=True, now=now
    )
    for member_id in member_ids:
        notify(database, member_id, user, "group_added", conversation_id=conversation_id, now=now)
    return MessageResult(True, "Group created.", conversation_id)


def _owned_group(database, user, conversation_id):
    """Return a group owned by the user, or None."""
    conversation = database.get_conversation(conversation_id)
    if conversation is None or not conversation["is_group"] or conversation["created_by"] != user["id"]:
        return None
    return conversation


def add_group_member(database, user, conversation_id, member_id, now=None):
    """Let a group's creator add a member, respecting the member limit."""
    if not _is_logged_in(user):
        return MessageResult(False, "Log in to manage this group.")
    conversation = _owned_group(database, user, conversation_id)
    if conversation is None:
        return MessageResult(False, "Only the group creator can add members.")
    if database.get_user_by_id(member_id) is None:
        return MessageResult(False, "That user could not be found.")
    if database.is_conversation_member(conversation_id, member_id):
        return MessageResult(True, "That user is already a member.", conversation_id)
    if len(database.get_conversation_members(conversation_id)) >= MAX_GROUP_MEMBERS:
        return MessageResult(False, "Groups can have at most 20 members.")
    database.add_conversation_member(conversation_id, member_id, now=now)
    notify(database, member_id, user, "group_added", conversation_id=conversation_id, now=now)
    return MessageResult(True, "Member added.", conversation_id)


def remove_group_member(database, user, conversation_id, member_id):
    """Let a group's creator remove another member."""
    if not _is_logged_in(user):
        return MessageResult(False, "Log in to manage this group.")
    if _owned_group(database, user, conversation_id) is None:
        return MessageResult(False, "Only the group creator can remove members.")
    if member_id == user["id"]:
        return MessageResult(False, "The group creator cannot remove themselves.")
    if not database.is_conversation_member(conversation_id, member_id):
        return MessageResult(False, "That user is not a group member.")
    database.remove_conversation_member(conversation_id, member_id)
    return MessageResult(True, "Member removed.", conversation_id)


def leave_group(database, user, conversation_id):
    """Let a non-creator member leave a group."""
    if not _is_logged_in(user):
        return MessageResult(False, "Log in to leave this group.")
    conversation = database.get_conversation(conversation_id)
    if conversation is None or not conversation["is_group"]:
        return MessageResult(False, "That group could not be found.")
    if conversation["created_by"] == user["id"]:
        return MessageResult(False, "The group creator cannot leave the group.")
    if not database.is_conversation_member(conversation_id, user["id"]):
        return MessageResult(False, "You are not a member of this group.")
    database.remove_conversation_member(conversation_id, user["id"])
    return MessageResult(True, "You left the group.", conversation_id)


def rename_group(database, user, conversation_id, name):
    """Let the group creator change or clear its name."""
    if not _is_logged_in(user):
        return MessageResult(False, "Log in to manage this group.")
    if _owned_group(database, user, conversation_id) is None:
        return MessageResult(False, "Only the group creator can change the name.")
    if name is not None and not isinstance(name, str):
        return MessageResult(False, "Group name must be text.")
    name = name.strip() if name else None
    name = name or None
    if name and len(name) > MAX_GROUP_NAME_LENGTH:
        return MessageResult(False, "Group names can be at most 50 characters.")
    database.rename_conversation(conversation_id, name)
    return MessageResult(True, "Group name updated.", conversation_id)


def send_message(database, user, conversation_id, text, now=None):
    """Check membership and text, then save the message."""
    if not _is_logged_in(user):
        return MessageResult(False, "Log in to send messages.")
    if not database.is_conversation_member(conversation_id, user["id"]):
        return MessageResult(False, "You are not part of this conversation.")
    if not isinstance(text, str) or not text.strip():
        return MessageResult(False, "Write a message first.")
    text = text.strip()
    if len(text) > MAX_MESSAGE_LENGTH:
        return MessageResult(False, f"Messages can be at most {MAX_MESSAGE_LENGTH} characters.")
    database.add_message(conversation_id, user["id"], text, now=now)
    for member in database.get_conversation_members(conversation_id):
        notify(database, member["id"], user, "message", conversation_id=conversation_id, now=now)
    return MessageResult(True, "Message sent.", conversation_id)


def get_conversation_messages(database, user, conversation_id):
    """Return a conversation's messages, or None if the user is not a member."""
    if not _is_logged_in(user) or not database.is_conversation_member(conversation_id, user["id"]):
        return None
    return database.get_messages(conversation_id)


def list_conversations(database, user):
    """Return the user's conversations, most recent activity first."""
    if not _is_logged_in(user):
        return []
    conversations = database.get_conversations_for_user(user["id"])
    for conversation in conversations:
        conversation["members"] = (database.get_conversation_members(conversation["id"])
                                   if conversation["is_group"] else [])
        if conversation["name"]:
            conversation["title"] = conversation["name"]
        elif conversation["is_group"]:
            members = conversation["members"]
            conversation["title"] = ", ".join(member["username"] for member in members[:3])
        else:
            conversation["title"] = conversation["other_username"] or "Conversation"
    return sorted(
        conversations,
        key=lambda item: (item["last_message_at"] or item["created_at"], item["id"]),
        reverse=True,
    )


def list_group_candidates(database, user):
    """Return other public users who can be invited to a group."""
    if not _is_logged_in(user):
        return []
    return [person for person in database.list_users() if person["id"] != user["id"]]


def format_message_time(timestamp):
    """Format a stored UTC timestamp as Lisbon time, e.g. '18 Nov, 21:30'."""
    moment = datetime.fromisoformat(timestamp)
    if moment.tzinfo is not None:
        moment = moment.astimezone(LISBON)
    return f"{moment.day} {moment.strftime('%b, %H:%M')}"


def _event_datetime(value):
    """Parse an ISO date and interpret a naive value as Lisbon local time."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        moment = datetime.fromisoformat(value)
    else:
        raise ValueError("Choose a valid date and time.")
    return moment.replace(tzinfo=LISBON) if moment.tzinfo is None else moment


def format_event_time(timestamp):
    """Format an ISO event time for Lisbon readers."""
    moment = _event_datetime(timestamp).astimezone(LISBON)
    return f"{moment.day} {moment.strftime('%b %Y, %H:%M')}"


def create_event(database, user, conversation_id, venue_id, title, starts_at,
                 max_attendees=None, now=None):
    """Validate group membership and save a venue meetup."""
    if not _is_logged_in(user):
        return EventResult(False, "Log in to create a meetup.")
    conversation = database.get_conversation(conversation_id)
    if (conversation is None or not conversation["is_group"]
            or not database.is_conversation_member(conversation_id, user["id"])):
        return EventResult(False, "Only group members can create meetups.")
    if database.get_venue_by_id(venue_id) is None:
        return EventResult(False, "Choose an existing bar or café.")
    if not isinstance(title, str) or not title.strip():
        return EventResult(False, "Enter a meetup title.")
    if max_attendees is not None and (isinstance(max_attendees, bool)
            or not isinstance(max_attendees, int) or max_attendees < 1):
        return EventResult(False, "Maximum attendees must be a positive whole number.")
    try:
        start = _event_datetime(starts_at).isoformat()
    except (TypeError, ValueError):
        return EventResult(False, "Choose a valid date and time.")
    event_id = database.add_event(conversation_id, venue_id, title.strip(), start,
                                  max_attendees, user["id"], now=now)
    return EventResult(True, "Meetup created.", event_id)


def get_conversation_events(database, user, conversation_id, now=None):
    """Return a group's upcoming and previous events for one member."""
    if (not _is_logged_in(user)
            or not database.is_conversation_member(conversation_id, user["id"])):
        return None
    conversation = database.get_conversation(conversation_id)
    if conversation is None:
        return None
    current = _event_datetime(now) if now is not None else datetime.now(LISBON)
    result = {"is_group": bool(conversation["is_group"]), "upcoming": [], "past": []}
    if not conversation["is_group"]:
        return result
    for event in database.get_events_for_conversation(conversation_id):
        responses = database.get_event_responses(event["id"])
        attendees = [row for row in responses if row["response"] == "going"]
        event["attendees"] = attendees
        event["going_count"] = len(attendees)
        event["my_response"] = database.get_event_response(event["id"], user["id"])
        event["is_past"] = _event_datetime(event["starts_at"]) < current
        result["past" if event["is_past"] else "upcoming"].append(event)
    result["past"].sort(key=lambda event: _event_datetime(event["starts_at"]), reverse=True)
    result["upcoming"].sort(key=lambda event: _event_datetime(event["starts_at"]))
    return result


def respond_to_event(database, user, event_id, response, now=None):
    """Save a member's yes/no response while enforcing the attendee cap."""
    if not _is_logged_in(user):
        return EventResult(False, "Log in to respond to this meetup.")
    event = database.get_event(event_id)
    if event is None or not database.is_conversation_member(event["conversation_id"], user["id"]):
        return EventResult(False, "You are not a member of this meetup's group.")
    if response not in {"going", "not_going"}:
        return EventResult(False, "Choose going or not going.")
    previous = database.get_event_response(event_id, user["id"])
    if response == "going" and previous != "going" and event["max_attendees"] is not None:
        going_count = sum(row["response"] == "going" for row in database.get_event_responses(event_id))
        if going_count >= event["max_attendees"]:
            return EventResult(False, "This meetup is full. There are no places left.")
    database.save_event_response(event_id, user["id"], response, now=now)
    return EventResult(True, "Your response was saved.", event_id)


def get_event_attendees(database, user, event_id):
    """Return the going members of an event, or no rows for an outsider."""
    event = database.get_event(event_id)
    if (not _is_logged_in(user) or event is None
            or not database.is_conversation_member(event["conversation_id"], user["id"])):
        return None
    return [row for row in database.get_event_responses(event_id) if row["response"] == "going"]


def cancel_event(database, user, event_id):
    """Delete a meetup only when requested by its creator."""
    if not _is_logged_in(user):
        return EventResult(False, "Log in to cancel this meetup.")
    event = database.get_event(event_id)
    if event is None:
        return EventResult(False, "That meetup could not be found.")
    if event["created_by"] != user["id"]:
        return EventResult(False, "Only the meetup creator can cancel it.")
    database.delete_event(event_id)
    return EventResult(True, "Meetup cancelled.", event_id)


def _notification_cooldown(database, conversation_id, recipient_id, now):
    """Return remaining cooldown time, if a recent notice was sent."""
    last_sent = database.get_notification_sent_at(conversation_id, recipient_id)
    if last_sent is None:
        return None
    previous = datetime.fromisoformat(last_sent)
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    remaining = timedelta(hours=1) - (now - previous.astimezone(timezone.utc))
    return remaining if remaining.total_seconds() > 0 else None


def _send_notification(database, sender, conversation, recipient_id, subject, details, now):
    """Check consent and cooldown, send one notice, and record successful delivery."""
    recipient = database.get_email_notification_settings(recipient_id)
    if recipient is None:
        return "missing"
    if not recipient["email_notifications"]:
        return "disabled"
    remaining = _notification_cooldown(database, conversation["id"], recipient_id, now)
    if remaining is not None:
        return f"cooldown:{max(1, math.ceil(remaining.total_seconds() / 60))}"
    body = (f"{sender['username']} notified you in {conversation['title']}.\n\n"
            f"{details}\n\nOpen Bock'n Bros: {mail.app_url()}")
    try:
        mail.send_notification(recipient["email"], subject, body)
        sent_at = now.isoformat()
        database.add_notification(conversation["id"], sender["id"], recipient_id, sent_at)
    except Exception:
        logging.exception("Email notification delivery failed for recipient %s", recipient_id)
        return "failed"
    return "sent"


def _notify_recipients(database, user, conversation, recipient_ids, subject, details, now=None):
    """Send a notice to eligible members and summarize any delivery blocks."""
    if not mail.smtp_configured():
        return NotificationResult(False, "Email notifications are not set up.")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    statuses = [_send_notification(database, user, conversation, recipient_id,
                                    subject, details, current) for recipient_id in recipient_ids]
    sent_count = statuses.count("sent")
    if sent_count:
        message = f"Notification sent to {sent_count} {('person' if sent_count == 1 else 'people')}."
        if "disabled" in statuses:
            message += " Some recipients have turned off email notifications."
        if any(status.startswith("cooldown:") for status in statuses):
            remaining = min(int(status.split(":")[1]) for status in statuses if status.startswith("cooldown:"))
            unit = "minute" if remaining == 1 else "minutes"
            message += f" Try again in {remaining} {unit} for other recipients."
        if "failed" in statuses:
            message += " Some emails could not be sent; please try again."
        return NotificationResult(True, message, sent_count)
    if "disabled" in statuses:
        return NotificationResult(False, "The recipient has turned off email notifications.")
    cooldowns = [int(status.split(":")[1]) for status in statuses if status.startswith("cooldown:")]
    if cooldowns:
        remaining = min(cooldowns)
        unit = "minute" if remaining == 1 else "minutes"
        return NotificationResult(False, f"{remaining} {unit} remaining before you can notify again.")
    if "failed" in statuses:
        return NotificationResult(False, "Email could not be sent. Please try again.")
    if statuses and all(status == "missing" for status in statuses):
        return NotificationResult(False, "The recipient could not be found.")
    return NotificationResult(False, "No one is waiting for a response.")


def notify_conversation(database, user, conversation_id, now=None):
    """Notify the other member of a direct conversation without quoting messages."""
    if not _is_logged_in(user):
        return NotificationResult(False, "Log in to notify someone.")
    conversation = database.get_conversation(conversation_id)
    if conversation is None or not database.is_conversation_member(conversation_id, user["id"]):
        return NotificationResult(False, "You are not part of this conversation.")
    if conversation["is_group"]:
        return NotificationResult(False, "Use Notify bro on a meetup to notify the group.")
    members = database.get_conversation_members(conversation_id)
    recipients = [member["id"] for member in members if member["id"] != user["id"]]
    details = "There is something new in your conversation."
    conversation["title"] = "your direct conversation"
    return _notify_recipients(database, user, conversation, recipients,
                              "New activity in Bock'n Bros", details, now)


def notify_event(database, user, event_id, now=None):
    """Notify group members who have not responded to a meetup."""
    if not _is_logged_in(user):
        return NotificationResult(False, "Log in to notify the group.")
    event = database.get_event(event_id)
    if event is None or not database.is_conversation_member(event["conversation_id"], user["id"]):
        return NotificationResult(False, "You are not a member of this meetup's group.")
    conversation = database.get_conversation(event["conversation_id"])
    if conversation is None or not conversation["is_group"]:
        return NotificationResult(False, "Meetup notifications are only available in groups.")
    conversation["title"] = get_conversation_title_for_user(database, user, conversation["id"]) or "your group"
    responded = {row["user_id"] for row in database.get_event_responses(event_id)}
    recipients = [member["id"] for member in database.get_conversation_members(conversation["id"])
                 if member["id"] != user["id"] and member["id"] not in responded]
    details = (f"Meetup: {event['title']}\nPlace: {event['venue_name']}\n"
               f"When: {format_event_time(event['starts_at'])}")
    return _notify_recipients(database, user, conversation, recipients,
                              f"Meetup reminder: {event['title']}", details, now)


def get_conversation_title_for_user(database, user, conversation_id):
    """Return a member's display title for a conversation."""
    return next((item["title"] for item in list_conversations(database, user)
                 if item["id"] == conversation_id), None)


def set_email_notifications(database, user, enabled):
    """Let a signed-in user change only their own notification preference."""
    if not _is_logged_in(user):
        return NotificationResult(False, "Log in to change notification settings.")
    if not isinstance(enabled, bool):
        return NotificationResult(False, "Choose whether email notifications are on or off.")
    if database.set_email_notifications(user["id"], enabled) is None:
        return NotificationResult(False, "Your profile could not be found.")
    label = "on" if enabled else "off"
    return NotificationResult(True, f"Email notifications turned {label}.")


def get_email_notifications(database, user):
    """Return the signed-in user's email notification preference."""
    if not _is_logged_in(user):
        return None
    return database.get_email_notifications(user["id"])


def search_app_people(user, text):
    """Find other users through the configured database."""
    return search_people(db, user, text)


def start_app_direct_conversation(user, other_user_id):
    """Open a direct conversation through the configured database."""
    return start_direct_conversation(db, user, other_user_id)


def send_app_message(user, conversation_id, text):
    """Send a message through the configured database."""
    return send_message(db, user, conversation_id, text)


def get_app_conversation_messages(user, conversation_id):
    """Read a conversation through the configured database."""
    return get_conversation_messages(db, user, conversation_id)


def notify_app_conversation(user, conversation_id):
    """Send a new-activity email for a direct conversation."""
    return notify_conversation(db, user, conversation_id)


def notify_app_event(user, event_id):
    """Send a meetup notification to group members still awaiting a response."""
    return notify_event(db, user, event_id)


def app_email_notifications_enabled(user):
    """Read the signed-in user's email preference."""
    return get_email_notifications(db, user)


def set_app_email_notifications(user, enabled):
    """Save the signed-in user's email preference."""
    return set_email_notifications(db, user, enabled)


def app_email_notifications_configured():
    """Report whether SMTP settings are available for the notification buttons."""
    return mail.smtp_configured()


def list_app_conversations(user):
    """List the user's conversations through the configured database."""
    return list_conversations(db, user)


def get_app_conversation_title(user, conversation_id):
    """Return the display title of one of the user's conversations."""
    for conversation in list_conversations(db, user):
        if conversation["id"] == conversation_id:
            return conversation["title"]
    return None


def get_app_conversation_details(user, conversation_id):
    """Return one of the signed-in user's conversations."""
    return next((item for item in list_conversations(db, user)
                 if item["id"] == conversation_id), None)


def get_app_group_candidates(user):
    """List possible group members through the configured database."""
    return list_group_candidates(db, user)


def create_app_group(user, name, member_ids):
    """Create a group through the configured database."""
    return create_group_conversation(db, user, name, member_ids)


def add_app_group_member(user, conversation_id, member_id):
    """Add a group member through the configured database."""
    return add_group_member(db, user, conversation_id, member_id)


def remove_app_group_member(user, conversation_id, member_id):
    """Remove a group member through the configured database."""
    return remove_group_member(db, user, conversation_id, member_id)


def leave_app_group(user, conversation_id):
    """Leave a group through the configured database."""
    return leave_group(db, user, conversation_id)


def rename_app_group(user, conversation_id, name):
    """Rename a group through the configured database."""
    return rename_group(db, user, conversation_id, name)


def get_app_conversation_events(user, conversation_id, now=None):
    """Read a group's meetups through the configured database."""
    return get_conversation_events(db, user, conversation_id, now=now)


def create_app_event(user, conversation_id, venue_id, title, starts_at, max_attendees=None):
    """Create a meetup through the configured database."""
    return create_event(db, user, conversation_id, venue_id, title, starts_at, max_attendees)


def respond_app_event(user, event_id, response):
    """Save a meetup response through the configured database."""
    return respond_to_event(db, user, event_id, response)


def cancel_app_event(user, event_id):
    """Cancel a meetup through the configured database."""
    return cancel_event(db, user, event_id)


def follow_user(database, user, other_user_id, now=None):
    """Follow another user; following twice changes nothing."""
    if not _is_logged_in(user):
        return FollowResult(False, "Log in to follow people.")
    if other_user_id == user["id"]:
        return FollowResult(False, "You cannot follow yourself.")
    other = database.get_user_by_id(other_user_id)
    if other is None:
        return FollowResult(False, "That user could not be found.")
    database.add_follow(user["id"], other_user_id, now=now)
    return FollowResult(True, f"You follow {other['username']}.")


def unfollow_user(database, user, other_user_id):
    """Stop following a user; unfollowing someone you do not follow changes nothing."""
    if not _is_logged_in(user):
        return FollowResult(False, "Log in to follow people.")
    database.remove_follow(user["id"], other_user_id)
    return FollowResult(True, "Unfollowed.")


def follow_venue(database, user, venue_id, now=None):
    """Follow a bar or café; following twice changes nothing."""
    if not _is_logged_in(user):
        return FollowResult(False, "Log in to follow bars.")
    venue = database.get_venue_by_id(venue_id)
    if venue is None:
        return FollowResult(False, "That venue could not be found.")
    database.add_venue_follow(user["id"], venue_id, now=now)
    return FollowResult(True, f"You follow {venue['name']}.")


def unfollow_venue(database, user, venue_id):
    """Stop following a venue."""
    if not _is_logged_in(user):
        return FollowResult(False, "Log in to follow bars.")
    database.remove_venue_follow(user["id"], venue_id)
    return FollowResult(True, "Unfollowed.")


def get_profile(database, viewer, user_id):
    """Return a public profile with friends, followers, following and bars, or None."""
    person = database.get_user_by_id(user_id)
    if person is None or not _is_logged_in(viewer):
        return None
    followers = database.get_followers(user_id)
    following = database.get_following(user_id)
    follower_ids = {item["id"] for item in followers}
    return {
        "id": person["id"],
        "username": person["username"],
        "role": person["role"],
        "image_id": person["image_id"],
        "is_me": person["id"] == viewer["id"],
        "is_followed_by_me": database.is_following(viewer["id"], user_id),
        "follows_me": database.is_following(user_id, viewer["id"]),
        # Friends are people who follow each other.
        "friends": [item for item in following if item["id"] in follower_ids],
        "followers": followers,
        "following": following,
        "bars": database.get_followed_venues(user_id),
    }


def set_profile_picture(database, user, image_bytes, image_name, now=None):
    """Validate and save a profile picture for the signed-in user."""
    if not _is_logged_in(user):
        return ProfilePictureResult(False, "Log in to change your profile picture.")
    try:
        image_id = database.set_profile_image(user["id"], image_bytes, image_name, now=now)
    except (TypeError, ValueError) as error:
        return ProfilePictureResult(False, str(error))
    if image_id is None:
        return ProfilePictureResult(False, "That user could not be found.")
    return ProfilePictureResult(True, "Profile picture saved.")


def remove_profile_picture(database, user):
    """Remove the signed-in user's profile picture."""
    if not _is_logged_in(user):
        return ProfilePictureResult(False, "Log in to change your profile picture.")
    if not database.remove_profile_image(user["id"]):
        return ProfilePictureResult(False, "That user could not be found.")
    return ProfilePictureResult(True, "Profile picture removed.")


def get_profile_avatar(database, person):
    """Return a user's image data or their initial for a fallback avatar."""
    image = database.get_image(person.get("image_id")) if person.get("image_id") else None
    if image:
        return {"bytes": image["bytes"], "mime_type": image["mime_type"], "initial": None}
    username = person.get("username", "?").strip()
    return {"bytes": None, "mime_type": None, "initial": username[:1].upper() or "?"}


def get_venue_follow_status(database, user, venue_id):
    """Return whether the user follows a venue and how many followers it has."""
    following = _is_logged_in(user) and database.is_following_venue(user["id"], venue_id)
    return {"is_following": following, "followers": database.count_venue_followers(venue_id)}


def follow_app_user(user, other_user_id):
    """Follow a user through the configured database."""
    return follow_user(db, user, other_user_id)


def unfollow_app_user(user, other_user_id):
    """Unfollow a user through the configured database."""
    return unfollow_user(db, user, other_user_id)


def follow_app_venue(user, venue_id):
    """Follow a venue through the configured database."""
    return follow_venue(db, user, venue_id)


def unfollow_app_venue(user, venue_id):
    """Unfollow a venue through the configured database."""
    return unfollow_venue(db, user, venue_id)


def get_app_profile(viewer, user_id):
    """Read a profile through the configured database."""
    return get_profile(db, viewer, user_id)


def get_app_profile_avatar(person):
    """Read a profile image through the configured database."""
    return get_profile_avatar(db, person)


def set_app_profile_picture(user, image_bytes, image_name):
    """Save a profile image through the configured database."""
    return set_profile_picture(db, user, image_bytes, image_name)


def remove_app_profile_picture(user):
    """Remove a profile image through the configured database."""
    return remove_profile_picture(db, user)


def get_app_venue_follow_status(user, venue_id):
    """Read a venue's follow status through the configured database."""
    return get_venue_follow_status(db, user, venue_id)


def create_post(database, user, venue_id, text, image_bytes=None, image_name=None, now=None,
                location_name=None, tagged_user_ids=None):
    """Check permission and input, then save a post tied to a venue or to a typed-in location."""
    if not _is_logged_in(user):
        return PostResult(False, "Log in to post.")
    if venue_id is None:
        # "Other" location: a place that is not in the venue list, typed in by the user.
        if not isinstance(location_name, str) or not location_name.strip():
            return PostResult(False, "Choose the bar or café this post is about, or type in your own location.")
        location_name = " ".join(location_name.split())
        if len(location_name) > MAX_LOCATION_LENGTH:
            return PostResult(False, f"Locations can be at most {MAX_LOCATION_LENGTH} characters.")
    else:
        location_name = None
        if database.get_venue_by_id(venue_id) is None:
            return PostResult(False, "Choose the bar or café this post is about.")
    if text is not None and not isinstance(text, str):
        return PostResult(False, "Post text must be text.")
    text = (text or "").strip()
    if len(text) > MAX_POST_LENGTH:
        return PostResult(False, f"Posts can be at most {MAX_POST_LENGTH} characters.")
    if not text and not image_bytes:
        return PostResult(False, "Add some text or a photo.")
    tagged_user_ids = list(dict.fromkeys(tagged_user_ids or []))
    if len(tagged_user_ids) > MAX_TAGS:
        return PostResult(False, f"You can tag at most {MAX_TAGS} people.")
    if user["id"] in tagged_user_ids:
        return PostResult(False, "You cannot tag yourself.")
    if any(database.get_user_by_id(tagged_id) is None for tagged_id in tagged_user_ids):
        return PostResult(False, "A tagged user could not be found.")
    try:
        post_id = database.create_post(user["id"], venue_id, text or None,
                                       image_bytes or None, image_name, now=now, location_name=location_name)
    except ValueError as error:
        return PostResult(False, str(error))
    if tagged_user_ids:
        database.add_post_tags(post_id, tagged_user_ids)
        for tagged_id in tagged_user_ids:
            notify(database, tagged_id, user, "tag", post_id=post_id, now=now)
    return PostResult(True, "Posted!", post_id)


def get_feed(database, user):
    """Return the user's feed: own posts, people they follow and bars they follow."""
    if not _is_logged_in(user):
        return []
    return _add_like_details(database, database.get_feed_posts(user["id"]), user)


def _add_like_details(database, posts, user):
    """Attach each post's like count and the viewer's state."""
    likes = database.get_likes_for_posts(post["id"] for post in posts)
    counts = {}
    liked_ids = set()
    for like in likes:
        counts[like["post_id"]] = counts.get(like["post_id"], 0) + 1
        if like["user_id"] == user["id"]:
            liked_ids.add(like["post_id"])
    tags = {}
    for tag in database.get_tags_for_posts(post["id"] for post in posts):
        tags.setdefault(tag["post_id"], []).append({"id": tag["id"], "username": tag["username"], "role": tag["role"]})
    for post in posts:
        post["like_count"] = counts.get(post["id"], 0)
        post["liked_by_me"] = post["id"] in liked_ids
        post["tags"] = tags.get(post["id"], [])
    return posts


def get_venue_posts(database, venue_id, user=None):
    """Return all posts about a venue."""
    posts = database.get_venue_posts(venue_id)
    return _add_like_details(database, posts, user) if _is_logged_in(user) else posts


def get_venue_community_photos(database, venue_id):
    """Return up to twelve photo posts for a venue, newest first."""
    return database.get_venue_photo_posts(venue_id, limit=12)


def get_post_for_viewer(database, post_id, viewer):
    """Return one post with the viewer's like state for the feed screen."""
    posts = database.get_post_details(post_id)
    if not posts:
        return None
    return _add_like_details(database, posts, viewer)[0] if _is_logged_in(viewer) else posts[0]


def get_user_posts(database, user_id, viewer=None):
    """Return all posts written by a user."""
    posts = database.get_user_posts(user_id)
    return _add_like_details(database, posts, viewer) if _is_logged_in(viewer) else posts


def add_comment(database, user, post_id, text, now=None):
    """Validate a comment and save it for a post."""
    if not _is_logged_in(user):
        return CommentResult(False, "Log in to comment.")
    if database.get_post_by_id(post_id) is None:
        return CommentResult(False, "That post could not be found.")
    if not isinstance(text, str):
        return CommentResult(False, "Comment must be text.")
    text = text.strip()
    if not text:
        return CommentResult(False, "Write a comment first.")
    if len(text) > 500:
        return CommentResult(False, "Comments can be at most 500 characters.")
    comment_id = database.add_comment(post_id, user["id"], text, now=now)
    notify(database, _post_owner(database, post_id), user, "comment", post_id=post_id, now=now)
    return CommentResult(True, "Comment added.", comment_id)


def get_comments(database, post_id):
    """Return a post's comments with their public author details."""
    return database.get_comments_for_post(post_id)


def delete_comment(database, user, comment_id):
    """Delete a comment only when the signed-in user wrote it."""
    if not _is_logged_in(user):
        return CommentResult(False, "Log in to delete a comment.")
    comment = database.get_comment(comment_id)
    if comment is None:
        return CommentResult(False, "That comment could not be found.")
    if comment["user_id"] != user["id"]:
        return CommentResult(False, "You can only delete your own comments.")
    database.delete_comment(comment_id)
    return CommentResult(True, "Comment deleted.", comment_id)


def toggle_like(database, user, post_id, now=None):
    """Add or remove the signed-in user's like on a post."""
    if not _is_logged_in(user):
        return LikeResult(False, "Log in to like posts.")
    if database.get_post_by_id(post_id) is None:
        return LikeResult(False, "That post could not be found.")
    if database.is_liking(post_id, user["id"]):
        database.remove_like(post_id, user["id"])
        return LikeResult(True, "Like removed.", False)
    database.add_like(post_id, user["id"], now=now)
    notify(database, _post_owner(database, post_id), user, "like", post_id=post_id, now=now)
    return LikeResult(True, "Post liked.", True)


def format_post_time(timestamp):
    """Format a stored UTC timestamp as Lisbon time, e.g. '18 Nov 2026, 21:30'."""
    moment = datetime.fromisoformat(timestamp)
    if moment.tzinfo is not None:
        moment = moment.astimezone(LISBON)
    return f"{moment.day} {moment.strftime('%b %Y, %H:%M')}"


def create_app_post(user, venue_id, text, image_bytes=None, image_name=None, location_name=None,
                    tagged_user_ids=None):
    """Create a post through the configured database."""
    return create_post(db, user, venue_id, text, image_bytes, image_name, location_name=location_name,
                       tagged_user_ids=tagged_user_ids)


def get_app_feed(user):
    """Read the feed through the configured database."""
    return get_feed(db, user)


def get_app_venue_posts(venue_id, user=None):
    """Read a venue's posts through the configured database."""
    return get_venue_posts(db, venue_id, user)


def get_app_venue_community_photos(venue_id):
    """Read venue photo metadata through the configured database."""
    return get_venue_community_photos(db, venue_id)


def get_app_post_for_viewer(post_id, viewer):
    """Read one post for the feed screen."""
    return get_post_for_viewer(db, post_id, viewer)


def get_app_user_posts(user_id, viewer=None):
    """Read a user's posts through the configured database."""
    return get_user_posts(db, user_id, viewer)


def get_app_post_image(post):
    """Return one post's image bytes from the database, or None."""
    if not post.get("image_id"):
        return None
    image = db.get_image_file(post["image_id"])
    return image["bytes"] if image else None


def add_app_comment(user, post_id, text):
    """Add a comment through the configured database."""
    return add_comment(db, user, post_id, text)


def get_app_comments(post_id):
    """Read comments through the configured database."""
    return get_comments(db, post_id)


def delete_app_comment(user, comment_id):
    """Delete a comment through the configured database."""
    return delete_comment(db, user, comment_id)


def toggle_app_like(user, post_id):
    """Toggle a post like through the configured database."""
    return toggle_like(db, user, post_id)


# ---------------------------------------------------------------------------
# In-app notifications ("alerts") with optional email (spec 11)
# ---------------------------------------------------------------------------

ALERT_KINDS = ("like", "comment", "tag", "group_added", "message")
# Kinds that get at most one email per hour for the same post or conversation, so a busy
# post or chat does not flood the inbox. Tags and group invites are emailed every time.
_THROTTLED_EMAIL_KINDS = {"like", "comment", "message"}
EMAIL_COOLDOWN = timedelta(hours=1)


def _post_owner(database, post_id):
    """Return the id of the user who wrote a post, or None."""
    posts = database.get_post_details(post_id)
    return posts[0]["user_id"] if posts else None


def _utc(now):
    """Return a timezone-aware UTC time (the current time when none is given)."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def alert_text(alert):
    """Describe a notification in one short sentence."""
    actor = alert["actor_username"]
    group = alert.get("conversation_name") or "a group"
    if alert["kind"] == "like":
        return f"{actor} liked your post"
    if alert["kind"] == "comment":
        return f"{actor} commented on your post"
    if alert["kind"] == "tag":
        return f"{actor} tagged you in a post"
    if alert["kind"] == "group_added":
        return f"{actor} added you to {group}"
    if alert.get("is_group"):
        return f"{actor} sent a message in {group}"
    return f"{actor} sent you a message"


def notify(database, recipient_id, actor, kind, post_id=None, conversation_id=None, now=None):
    """Create an in-app notification (and maybe an email); never fails the action that caused it."""
    if recipient_id is None or recipient_id == actor["id"] or kind not in ALERT_KINDS:
        return None
    try:
        if kind == "like" and database.find_alert(recipient_id, "like", actor_id=actor["id"], post_id=post_id):
            return None  # liking, unliking and liking again only notifies once
        if kind == "message":
            # One unread notification per conversation: newer messages move it to the top again.
            existing = database.find_alert(recipient_id, "message", conversation_id=conversation_id, unread_only=True)
            if existing is not None:
                database.refresh_alert(existing["id"], actor["id"], now=now)
                alert_id = existing["id"]
            else:
                alert_id = database.add_alert(recipient_id, actor["id"], kind, conversation_id=conversation_id, now=now)
        else:
            alert_id = database.add_alert(recipient_id, actor["id"], kind, post_id=post_id,
                                          conversation_id=conversation_id, now=now)
        _email_alert(database, alert_id, recipient_id, actor, kind, post_id, conversation_id, now)
        return alert_id
    except Exception:
        logging.exception("Could not create %s notification for user %s", kind, recipient_id)
        return None


def _email_alert(database, alert_id, recipient_id, actor, kind, post_id, conversation_id, now):
    """Email a notification if the user wants email and it is not too soon after the last one."""
    if not mail.smtp_configured():
        return False
    settings = database.get_email_notification_settings(recipient_id)
    if settings is None or not settings["email_notifications"]:
        return False
    current = _utc(now)
    if kind in _THROTTLED_EMAIL_KINDS:
        last = database.get_last_alert_email(recipient_id, kind, post_id=post_id, conversation_id=conversation_id)
        if last is not None and current - _utc(datetime.fromisoformat(last)) < EMAIL_COOLDOWN:
            return False
    conversation = database.get_conversation(conversation_id) if conversation_id else None
    text = alert_text({"kind": kind, "actor_username": actor["username"],
                       "conversation_name": conversation["name"] if conversation else None,
                       "is_group": bool(conversation and conversation["is_group"])})
    # Like the Notify bro emails, never include message, comment or post text.
    body = f"{text} on Bock'n Bros.\n\nOpen Bock'n Bros: {mail.app_url()}"
    try:
        mail.send_notification(settings["email"], f"Bock'n Bros: {text}", body)
    except Exception:
        logging.exception("Notification email failed for user %s", recipient_id)
        return False
    database.mark_alert_emailed(alert_id, now=now)
    return True


def get_alerts(database, user):
    """Return the user's notifications, newest first, each with a 'text'."""
    if not _is_logged_in(user):
        return []
    alerts = database.get_alerts(user["id"])
    for alert in alerts:
        alert["text"] = alert_text(alert)
    return alerts


def take_new_alerts(database, user):
    """Return notifications not yet shown as a pop-up and mark them as shown."""
    if not _is_logged_in(user):
        return []
    alerts = database.get_untoasted_alerts(user["id"])
    for alert in alerts:
        alert["text"] = alert_text(alert)
    database.mark_alerts_toasted(alert["id"] for alert in alerts)
    return alerts


def count_unread_alerts(database, user):
    """Return how many notifications the user has not read."""
    return database.count_unread_alerts(user["id"]) if _is_logged_in(user) else 0


def mark_alerts_read(database, user, now=None):
    """Mark all of the user's notifications as read."""
    if _is_logged_in(user):
        database.mark_alerts_read(user["id"], now=now)


def get_app_alerts(user):
    """Read notifications through the configured database."""
    return get_alerts(db, user)


def take_app_new_alerts(user):
    """Read and mark pop-up notifications through the configured database."""
    return take_new_alerts(db, user)


def count_app_unread_alerts(user):
    """Count unread notifications through the configured database."""
    return count_unread_alerts(db, user)


def mark_app_alerts_read(user):
    """Mark notifications read through the configured database."""
    mark_alerts_read(db, user)
