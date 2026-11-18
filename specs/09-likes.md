# Spec 09 — Likes on posts

## Why

Likes let users quickly show that they enjoyed a post.

Needs spec 06 (posts).

## What

### 1. Database (`db.py`)
- A `likes` table with post_id (REFERENCES posts), user_id (REFERENCES users) and
  created_at. A unique constraint on (post_id, user_id) ensures one like per user per
  post even if application rules are bypassed. Creation time is supplied by the app.
- Functions add a like, remove a like and fetch the like rows needed for display.

### 2. Rules (`logic.py`)
- Any logged-in user, including a business user, can like an existing post.
- Pressing Like adds the user's like. Pressing it again removes that like.
- Like counts and whether the current user liked each post are calculated in Python.

### 3. Screens (`app.py`)
- Each post in the feed shows its like count and whether the current user has liked it,
  with a button to like or unlike the post.

## Out of scope

- Notifications
- A list of users who liked a post
- Likes on comments

## Done when

- [ ] Approved tests pass with `uv run pytest`; existing tests still pass.
- [ ] A user cannot create two likes for the same post, including by calling the
  database function directly.
- [ ] Pressing Like again removes the like and updates the count.
- [ ] Business users can like posts.
- [ ] The feed shows each post's like count and the current user's liked state.
- [ ] Counts are aggregated in Python, without SQL `GROUP BY`.
- [ ] No file other than `db.py` uses a database driver or contains SQL.
