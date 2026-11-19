# Spec 11 — Deleting your own post

## Why

Spec 06 left deleting out of scope, so a post was permanent once it was published. A
wrong bar, a blurry photo or a change of mind should not have to stay in the feed
forever. Authors need a way to take their own post back.

Needs spec 06 (posts), spec 07 (comments) and spec 09 (likes).

## What

### 1. Database (`db.py`)
- `delete_post(post_id)` removes the post together with everything that hangs off it:
  its comments, its likes and the post row itself, in that order, inside one
  connection.
- The post's photo is then cleaned up with the existing `_delete_unused_image`, which
  only deletes an image when no other post and no profile picture still points at it.
- Returns `False` when the post does not exist, so nothing is deleted by accident.

### 2. Rules (`logic.py`)
- **Who can delete:** only the user who wrote the post. Checked in `logic.py`, not just
  by hiding the button.
- A logged-out user is refused ("Log in to delete a post.").
- An unknown post is refused ("That post could not be found.").
- Someone else's post is refused ("You can only delete your own posts.").
- Deleting is permanent; there is no soft delete and no undo.
- Returns a `PostResult`, like the other post actions.

### 3. Screens (`app.py`)
- A **Delete post** button at the bottom of the author's own posts, wherever a post is
  shown: the feed, the venue page and the profile page.
- Clicking it asks for confirmation first: a warning that the photo, comments and likes
  go with it and cannot be undone, then **Yes, delete** and **Keep it**.
- The confirmation state is kept per post in `st.session_state`, so opening it on one
  post does not arm the button on another.
- Other users never see the button on a post they did not write.

## Out of scope

- Editing a post after publishing
- Deleting someone else's post (moderation, reporting)
- A bin or undo window after deleting
- Deleting a whole account with all its posts

## Done when

- [ ] Approved tests pass with `uv run pytest`; all earlier tests still pass.
- [ ] An author can delete their own post and it leaves the feed, the venue page and
      their profile.
- [ ] Another user and a logged-out user are both refused.
- [ ] Deleting a post also removes its comments and its likes.
- [ ] Deleting a post removes its photo, but keeps an image that a profile picture
      still uses.
- [ ] Deleting one post leaves the author's other posts untouched.
- [ ] The button only appears on the author's own posts and asks before deleting.
- [ ] No file other than `db.py` imports a database driver or contains SQL.
