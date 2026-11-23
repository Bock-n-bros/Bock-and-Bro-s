# Spec 16 — Rating a bar from the feed post

## Why

Rating a bar today means leaving the feed, opening the venue page and filling in three
sliders. Most people posting a photo from a bar would happily say "the vibe here is a
4" in the same breath, and never do the full review. One optional slider in the post
form turns a photo into a rating, and the rating counts for real: it is the atmosphere
score of that user's review of that bar.

Builds on spec 03 (reviews, D14, D15) and spec 06 (posts).

## What

### 1. Reviews may be partly filled (`db.py`)
- `reviews.atmosphere`, `value` and `quality` become nullable, each with
  `CHECK (x IS NULL OR x BETWEEN 1 AND 5)`, plus a table check that at least one of the
  three is filled. *Why:* a vibe rating is a real review with one category answered.
- `save_review` only writes the fields it is given. Keys left out keep the value they
  have. *Why:* posting a vibe must not wipe the value and quality scores of someone who
  already wrote a full review. A key given as `None` still clears that field, so the
  venue page can remove a Super Bock price.
- `summarize_reviews` averages each category over the reviews that answered it, and
  `overall` is the mean of the category means that exist. Rounding still happens once,
  at the end (D14). A venue with only vibe ratings has an overall score equal to its
  atmosphere score, and `value`/`quality` stay None.
- `review_count` counts reviews, whether partial or full.

**One-time migration.** `CREATE TABLE IF NOT EXISTS` will not change an existing table:
- Local: delete `bocknbros.db` and let `seed.py` rebuild it (the file is ignored by Git).
- Supabase: run once in the SQL editor —
  `ALTER TABLE reviews ALTER COLUMN atmosphere DROP NOT NULL;` and the same for `value`
  and `quality`.
Put both in the README under "Database setup" so the whole group can repeat them.

### 2. Rules (`logic.py`)
- `submit_review` accepts `None` for any of the three scores. A score that is given must
  still be a whole number from 1 to 5, and at least one of the three is required.
- `create_post(..., vibe=None)`: when a vibe is given, the post is saved first, then the
  rating is saved as a review through the normal path, so D15 still holds — one review
  per customer per venue, created or updated, original date kept.
- A vibe is only possible when the post is about a venue from the list. Posts about a
  typed-in "Other" location have nowhere to attach a rating; the slider is not shown.
- Only customers can rate (D15), so a business posting about its own bar never sees the
  slider.
- A rating that fails validation does not throw the post away: the post is kept and the
  message explains that the rating was not saved.
- Deleting the post does not delete the rating. *Why:* it is a real review that other
  people have already seen on the venue page. Say this in the delete confirmation.

### 3. Screens (`app.py`)
- The post form shows **Vibe (optional)** as a `st.select_slider` with the options
  "No rating" (default), 1, 2, 3, 4, 5. *Why not `st.slider`:* a plain slider has no
  empty state, so it would force a rating on everyone who posts.
- Under it, a caption when the user has already rated that bar: "You rated The Garden
  3 for atmosphere. Posting a vibe updates it."
- After posting: "Posted! Updated your vibe for The Garden." or "Posted! Rated The
  Garden 4 for vibe."
- `posts.vibe` stores the number that was given with the post, and the post shows it as
  "★ 4 vibe". *Why store it twice:* the post is what the user said that evening; the
  review is what they think now. Without it the badge would change under an old post
  when the user later updates their review. Only `reviews` feeds the venue average.
- The venue page shows "No rating yet" instead of a number for a category nobody has
  answered, and the review list shows only the categories a review filled in.

## Out of scope

- Rating value, quality or the Super Bock price from the feed; the venue page keeps the
  full form.
- Rating a typed-in "Other" location, or rating from a comment.
- Changing a vibe from the post afterwards (the venue page does that).

## Done when

- [ ] Approved tests pass with `uv run pytest`, including the existing review tests that
      this spec changes.
- [ ] A vibe-only review is saved, counts in `review_count`, and sets overall = vibe.
- [ ] Posting a vibe for a bar the user already reviewed in full keeps value, quality,
      price and the original date, and changes only atmosphere.
- [ ] A venue with one vibe-only and one full review averages atmosphere over both, and
      value and quality over the full one alone.
- [ ] A review with all three scores empty is refused by both `logic.py` and the database.
- [ ] Businesses and "Other" location posts never get the slider, and a refused rating
      still leaves the post standing.
- [ ] Deleting the post leaves the rating on the venue page.
- [ ] Both databases accept partial reviews after the migration.
