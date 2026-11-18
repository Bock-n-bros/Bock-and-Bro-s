# Spec 07 — Comments on posts

## Why

Comments let users coordinate around a post and let bar owners answer questions.

Needs spec 06 (posts).

## What

### 1. Database (`db.py`)
- A `comments` table with id, post_id (REFERENCES posts), user_id (REFERENCES users),
  text and created_at. Creation time is supplied by the app.
- Functions add a comment, fetch a post's comments oldest first with username and role,
  count comments for a post, find a comment and delete a comment.

### 2. Rules (`logic.py`)
- Any logged-in user, including a business user, may comment on an existing post.
- Text is trimmed, must not be empty and may contain at most 500 characters.
- A comment's author may delete it. Other users cannot.

### 3. Screens (`app.py`)
- Posts on the feed, venue pages and profiles show the comment count and an expander
  with comments oldest first, a one-line comment field and a Send button.
- Each comment shows its author's username, role, text and date. The author can delete
  their own comment.
- Comments are shown as plain text, not Markdown or HTML.

## Out of scope

- Editing comments
- Replies to comments or threads
- Likes on comments
- Notifications

## Done when

- [ ] Approved tests pass with `uv run pytest`; existing tests still pass.
- [ ] A customer or business user can comment on an existing post.
- [ ] Comments appear oldest first with username and role.
- [ ] Empty text, 501 characters and comments on unknown posts are refused.
- [ ] A user can delete their own comment, but another user cannot.
- [ ] Text such as `**bold** <b>hi</b>` appears exactly as typed, as plain text.
- [ ] No file other than `db.py` uses a database driver or contains SQL.
