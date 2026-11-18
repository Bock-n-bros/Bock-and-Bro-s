# Spec 05 — Following users and profile pages

## Why

The feed (spec 06) shows posts from people you follow, so users first need a way to find
each other and follow them. A profile page gives every user, including bar owners, one
place where their posts can be found.

Builds on spec 04 (Google login). Uses the user dictionary `{"id", "username", "role"}`
from `logic.find_google_user` unchanged.

## What

### 1. Database (`db.py`)
- A `venue_follows` table with: user_id, venue_id, created_at, unique on
  (user_id, venue_id), so users can follow bars (venues) directly.
- A `follows` table with: follower_id, followed_id (both REFERENCES users(id)),
  created_at. Primary key / unique constraint on (follower_id, followed_id), so the
  same follow can never exist twice.
- Functions to: add a follow, remove a follow, check whether A follows B, list the ids
  a user follows, count followers and following for a user, search users by username
  (case-insensitive "contains", at most 20 results, without email), fetch a user by id
  (without email).

### 2. Rules (`logic.py`)
- **Follow:** a logged-in user can follow any other existing user. Following yourself
  is refused. Following someone you already follow is not an error: nothing changes.
- **Unfollow:** removes the follow. Unfollowing someone you do not follow is not an
  error: nothing changes.
- **Search:** the search text is trimmed; empty search returns no results (not every
  user). The current user is not included in their own results.
- **Friends** are users who follow each other (mutual follow). Unfollowing ends it.
- **Follow a bar:** any logged-in user can follow an existing venue; same "twice changes
  nothing" rule. The venue page shows its follower count.
- **Profile:** returns username, role, `is_me`, `is_followed_by_me`, `follows_me` and the
  lists `friends`, `followers`, `following` (users) and `bars` (venues), or `None` if
  the user does not exist.
  Never includes the Google email or google_sub.
- Results use the existing `AuthResult`-style pattern (success + message) for follow
  and unfollow, so the screen can show a message.

### 3. Screens (`app.py`)
- The sidebar gets a page choice: **Venues**, **Feed**, **People**, **Messages**
  (Feed and Messages are filled in by specs 06 and 08; until then they show
  "Coming soon").
- **People:** a search box for usernames and a list of matches with a **View profile**
  button. Bar owners are marked "Bar owner".
- **Profile page (Instagram-style):** username, "Bar owner" and "Follows you" labels,
  four counts (Friends, Followers, Following, Bars), **Follow** / **Unfollow** and
  **Message** buttons (not on your own profile), and four tabs listing the people/bars;
  each person opens their profile, each bar opens the venue page.
- **Venue page:** follower count and a **Follow bar** / **Unfollow bar** button. A **My profile** link in the sidebar opens your own profile.
- Usernames are shown as plain text.

## Out of scope

- Private accounts and follow requests (all profiles are public)
- Blocking users
- Profile pictures and bios
- Linking a bar owner to a specific venue (later admin spec)

## Done when

- [ ] Approved tests pass with `uv run pytest` (all earlier tests still pass).
- [ ] A user can search for another user, open the profile and follow them; the
      follower count goes up by one.
- [ ] Following the same user twice still counts as one follow.
- [ ] Following yourself is refused in `logic.py`, not only by hiding the button.
- [ ] Unfollow works and the count goes down.
- [ ] The Google email never appears on any page or in any search result.
- [ ] Still no file other than `db.py` imports `sqlite3`.
