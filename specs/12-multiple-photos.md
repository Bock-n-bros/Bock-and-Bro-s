# Spec 12 — Several photos in one post

## Why

Spec 06 allowed one photo per post. A night out is rarely one picture: the bar, the
beer and the people are three. Letting a post carry a few photos makes the feed worth
scrolling without adding video or albums.

Needs spec 06 (posts) and spec 11 (deleting posts).

## What

### 1. Database (`db.py`)
- A `post_images` table: id, post_id (REFERENCES posts), image_id (REFERENCES images)
  and position, unique per post and position. It holds every photo of a post in
  upload order.
- `posts.image_id` stays, and now means the post's **cover photo** (its first one).
  Keeping it means venue photo queries and older rows keep working unchanged.
- `create_post` takes a list of (bytes, filename) pairs. Every photo is checked and
  compressed **before** anything is written, so one bad file saves nothing at all.
- `get_post_image_ids(post_id)` returns the photo ids in order.
- Posts written before this feature are copied into `post_images` once, on startup, by
  `_ensure_post_images_backfill`. It skips posts that already have rows, so running it
  again changes nothing.
- `delete_post` (spec 11) removes every `post_images` row and then cleans up each
  image. An image is only deleted when no post, no cover and no profile picture still
  points at it.
- `post_images` is created with RLS enabled, like every other table.

### 2. Rules (`logic.py`)
- `MAX_POST_PHOTOS = 4`. More than four photos is refused with a clear message.
- Each photo follows the spec 06 rules unchanged: `.jpg`, `.jpeg` or `.png`, at most
  5 MB before processing, valid content, resized above 1200 pixels wide.
- A post still needs text, at least one photo, or both.
- The single-photo arguments from spec 06 still work, so earlier callers and tests are
  unaffected.
- Posts come back with an `image_ids` list wherever they are fetched: the feed, a
  venue page, a profile and one post on its own.

### 3. Screens (`app.py`)
- The new-post form uses `st.file_uploader(accept_multiple_files=True)` and says how
  many photos are allowed.
- A post with one photo looks exactly as before, full width. A post with several shows
  them in a two-column grid with a "3 photos" caption underneath.
- A photo that cannot be read is skipped, and the post still shows the rest.
- The venue page's "Photos from the community" keeps showing one cover photo per post,
  so one post cannot take over the whole section.

## Out of scope

- Reordering or removing a single photo after posting
- A lightbox, carousel or full-screen viewer
- Video, GIFs and albums
- More than four photos per post
- Captions per photo

## Done when

- [ ] Approved tests pass with `uv run pytest`; all earlier tests still pass.
- [ ] A post can be created with two, three or four photos, kept in upload order.
- [ ] A fifth photo is refused and nothing is saved.
- [ ] One invalid photo among valid ones refuses the whole post and saves no images.
- [ ] A post with one photo behaves exactly as it did before.
- [ ] Posts written before this feature still show their photo.
- [ ] Deleting a post removes all of its photos.
- [ ] `post_images` is created with RLS enabled.
- [ ] No file other than `db.py` imports a database driver or contains SQL.
