# Spec 06 — Posts with photos, the feed and posts on venue pages

## Why

A feed, like Strava or Instagram, makes the app social: users show where they are having
a beer and who they are with, and bars show what is happening tonight. Every post is
tied to a venue, so posts also become live content on each venue page.

Needs spec 05 (follows).

## What

### 1. Database (`db.py`)
- A `posts` table with: id, user_id (REFERENCES users), venue_id (REFERENCES venues,
  not null), text, image_id (nullable REFERENCES images), created_at.
- An `images` table stores id, bytes (SQLite BLOB / Postgres BYTEA), mime_type,
  byte_size and created_at. Images are processed and saved by `db.py`; post queries
  return only `image_id`, and image bytes are fetched one at a time for display.
- Functions to: save a post (with optional image bytes + extension), fetch the feed for
  a user (posts by the users they follow and their own, newest first, at most 50), fetch
  posts for a venue (newest first, at most 50), fetch posts by a user (newest first, at
  most 50), and return the full path of an image file. Each post comes back with the
  author's username and role and the venue's name.

### 2. Rules (`logic.py`)
- **Who can post:** any logged-in user, customer or business (bar owner).
- **Validation:**
  - The venue must exist.
  - `text` is trimmed and at most 500 characters.
  - A post must have text, a photo, or both. An empty post is refused.
  - A photo must be `.jpg`, `.jpeg` or `.png` (case-insensitive), at most 5 MB
    before processing, and its content must be a valid image of the matching type.
    Images wider than 1200 pixels are resized and accepted images are compressed.
    Anything else is refused and nothing is saved.
- **Feed:** posts from users the current user follows, posts tagged with bars they
  follow (spec 05), plus their own posts. Someone
  who follows nobody sees only their own posts and a hint to find people.
- **Venue posts:** all posts tagged with that venue, from anyone. Posts by bar owners
  are marked so they stand out.
- **Dates** are shown as "18 Nov 2026, 21:30" (reuse the review date helper if it fits).

### 3. Screens (`app.py`)
- **Feed page:** a **New post** form at the top: venue (select box, searchable by name),
  text area (max 500), and photo upload (`st.file_uploader` with types jpg, jpeg, png).
  Below it the feed: username (click opens their profile), "Bar owner" label if
  any, venue name (click opens the venue page), photo (`st.image`), text, date.
- **Venue page:** a new **Posts** section below the reviews, with the same post layout,
  and a **Post about this venue** shortcut that opens the form with the venue chosen.
- **Profile page (spec 05):** the user's own posts below the counts.
- Post text is shown as plain text (`st.text`), never as Markdown or HTML, as for
  reviews (D-012).

## Out of scope

- Editing or deleting posts
- Likes
- Several photos per post, video
- Tagging other users in a post
- Storing photos in Supabase Storage (when the app is deployed; only `db.py` changes)
- Comments (spec 07)

## Done when

- [ ] Approved tests pass with `uv run pytest` (all earlier tests still pass).
- [ ] A customer and a bar owner can both post with a photo and a venue.
- [ ] A post appears in the feed of users who follow the author, and not for others.
- [ ] The post appears on the venue page, and a bar owner's post is marked "Bar owner".
- [ ] An empty post, a missing venue, text over 500 characters, a `.gif` or a 6 MB
      photo is refused with a clear message, and no row or file is saved.
- [ ] Photos are still shown after restarting the app.
- [ ] Image bytes are fetched individually rather than with feed metadata.
- [ ] Still no file other than `db.py` imports database drivers.
