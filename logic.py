"""Validate account actions and apply authentication rules."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
from pathlib import Path

import db


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


MAX_POST_LENGTH = 500
MAX_IMAGE_BYTES = 5 * 1024 * 1024
# File signatures ("magic bytes"), so a renamed non-image file is refused.
IMAGE_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}
IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]
MAX_MESSAGE_LENGTH = 1000
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


def format_review_date(review):
    """Format review creation or update time for display."""
    created = datetime.fromisoformat(review["created_at"])
    updated = datetime.fromisoformat(review["updated_at"])
    if updated > created:
        return f"Updated {updated.day} {updated.strftime('%b %Y')}"
    return f"{created.day} {created.strftime('%b %Y')}"


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
        conversation["title"] = conversation["name"] or conversation["other_username"] or "Conversation"
    return sorted(
        conversations,
        key=lambda item: (item["last_message_at"] or item["created_at"], item["id"]),
        reverse=True,
    )


def format_message_time(timestamp):
    """Format a stored UTC timestamp as Lisbon time, e.g. '18 Nov, 21:30'."""
    moment = datetime.fromisoformat(timestamp)
    if moment.tzinfo is not None:
        moment = moment.astimezone(LISBON)
    return f"{moment.day} {moment.strftime('%b, %H:%M')}"


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


def list_app_conversations(user):
    """List the user's conversations through the configured database."""
    return list_conversations(db, user)


def get_app_conversation_title(user, conversation_id):
    """Return the display title of one of the user's conversations."""
    for conversation in list_conversations(db, user):
        if conversation["id"] == conversation_id:
            return conversation["title"]
    return None


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
        "is_me": person["id"] == viewer["id"],
        "is_followed_by_me": database.is_following(viewer["id"], user_id),
        "follows_me": database.is_following(user_id, viewer["id"]),
        # Friends are people who follow each other.
        "friends": [item for item in following if item["id"] in follower_ids],
        "followers": followers,
        "following": following,
        "bars": database.get_followed_venues(user_id),
    }


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


def get_app_venue_follow_status(user, venue_id):
    """Read a venue's follow status through the configured database."""
    return get_venue_follow_status(db, user, venue_id)


def _image_problem(image_bytes, image_name):
    """Return why a photo is not allowed, or None if it is fine."""
    extension = Path(image_name or "").suffix.casefold()
    if extension not in IMAGE_SIGNATURES:
        return None, "Photos must be JPG, PNG or WEBP."
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return None, "Photos can be at most 5 MB."
    looks_right = image_bytes.startswith(IMAGE_SIGNATURES[extension])
    if extension == ".webp":
        looks_right = looks_right and image_bytes[8:12] == b"WEBP"
    if not looks_right:
        return None, "That file is not a valid image."
    return extension, None


def create_post(database, user, venue_id, text, image_bytes=None, image_name=None, now=None):
    """Check permission and input, then save a post tied to a venue."""
    if not _is_logged_in(user):
        return PostResult(False, "Log in to post.")
    if venue_id is None or database.get_venue_by_id(venue_id) is None:
        return PostResult(False, "Choose the bar or café this post is about.")
    if text is not None and not isinstance(text, str):
        return PostResult(False, "Post text must be text.")
    text = (text or "").strip()
    if len(text) > MAX_POST_LENGTH:
        return PostResult(False, f"Posts can be at most {MAX_POST_LENGTH} characters.")
    extension = None
    if image_bytes:
        extension, problem = _image_problem(image_bytes, image_name)
        if problem:
            return PostResult(False, problem)
    if not text and not image_bytes:
        return PostResult(False, "Add some text or a photo.")
    post_id = database.create_post(user["id"], venue_id, text or None,
                                   image_bytes or None, extension, now=now)
    return PostResult(True, "Posted!", post_id)


def get_feed(database, user):
    """Return the user's feed: own posts, people they follow and bars they follow."""
    if not _is_logged_in(user):
        return []
    return database.get_feed_posts(user["id"])


def get_venue_posts(database, venue_id):
    """Return all posts about a venue."""
    return database.get_venue_posts(venue_id)


def get_user_posts(database, user_id):
    """Return all posts written by a user."""
    return database.get_user_posts(user_id)


def format_post_time(timestamp):
    """Format a stored UTC timestamp as Lisbon time, e.g. '18 Nov 2026, 21:30'."""
    moment = datetime.fromisoformat(timestamp)
    if moment.tzinfo is not None:
        moment = moment.astimezone(LISBON)
    return f"{moment.day} {moment.strftime('%b %Y, %H:%M')}"


def create_app_post(user, venue_id, text, image_bytes=None, image_name=None):
    """Create a post through the configured database."""
    return create_post(db, user, venue_id, text, image_bytes, image_name)


def get_app_feed(user):
    """Read the feed through the configured database."""
    return get_feed(db, user)


def get_app_venue_posts(venue_id):
    """Read a venue's posts through the configured database."""
    return get_venue_posts(db, venue_id)


def get_app_user_posts(user_id):
    """Read a user's posts through the configured database."""
    return get_user_posts(db, user_id)


def get_app_post_image(post):
    """Return the file path of a post's photo, or None."""
    return db.get_image_file(post["image_path"])
