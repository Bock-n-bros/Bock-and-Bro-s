# Spec 07 — Comments on posts

## Why

Comments turn posts into conversations ("Save me a seat!", "Is the match on tonight?")
and give bar owners a way to answer questions about their posts.

Needs spec 06 (posts).

## What

### 1. Database (`db.py`)
- A `comments` table with: id, post_id (REFERENCES posts), user_id (REFERENCES users),
  text, created_at.
- Functions to: add a comment, fetch the comments for a post (oldest first, with the
  author's username and role), and count comments per post.

### 2. Rules (`logic.py`)
- **Who can comment:** any logged-in user, on any existing post they can open
  (all posts are public, see spec 05).
- **Validation:** text is trimmed, not empty, at most 300 characters. The post must exist.

### 3. Screens (`app.py`)
- Each post (feed, venue page, profile) shows "💬 N comments". Clicking it shows the
  comments under the post (`st.expander`) and a one-line comment box with a **Send**
  button.
- Comments show username, "Bar owner" label if any, the text as plain text, and the date.

## Out of scope

- Editing or deleting comments
- Replies to comments (threads)
- Likes on comments
- Notifications

## Done when

- [ ] Approved tests pass with `uv run pytest` (all earlier tests still pass).
- [ ] A user can comment on another user's post and the comment count goes up.
- [ ] Comments are shown oldest first.
- [ ] An empty comment, a comment over 300 characters, or a comment on a post that does
      not exist is refused and nothing is saved.
- [ ] A comment such as `**bold** <b>hi</b>` is displayed exactly as typed.
