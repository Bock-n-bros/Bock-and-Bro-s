# Spec 03 — Reviews, average scores and sorting

## Why

Reviews are what turn a list of bars into Bock'n Bros: users share how the atmosphere,
value and quality really are, and other users use that to pick where to go. Average
scores and sorting let users quickly find "the best atmosphere in Bairro Alto" or
"the cheapest Super Bock".

## What

### 1. Database (`db.py`)
- A `reviews` table with: id, venue_id, user_id, atmosphere, value, quality,
  super_bock_price, comment, created_at, updated_at.
- At most one review per user per venue (enforced in the database too, with a unique
  constraint on venue_id + user_id).
- Functions to: save a review (insert or update the user's existing one), fetch the
  current user's review for a venue, fetch all reviews for a venue (newest first, with
  the reviewer's username), and fetch summary numbers per venue.

### 2. Rules (`logic.py`)
- **Who can review:** only logged-in **customers**. Businesses and logged-out users are
  refused (checked in logic, not only by hiding the form).
- **One review per venue:** if the customer has already reviewed the venue, submitting
  again **updates** their existing review instead of creating a second one.
- **Validation:**
  - `atmosphere`, `value` (value for money) and `quality` are whole numbers 1–5.
  - `super_bock_price` is optional; if given, it is between 0.50 and 10.00 euros.
  - `comment` is optional, at most 500 characters, leading/trailing spaces removed.
  - The venue must exist.
- **Summary per venue:**
  - Average atmosphere, value and quality, each rounded to 1 decimal.
  - Overall score = average of the three averages, rounded to 1 decimal.
  - Number of reviews.
  - Average Super Bock price (only from reviews that gave one), rounded to 2 decimals.
  - A venue with no reviews has no scores ("No reviews yet"), not zero.
- **Sorting the venue list** (applied after the filters from spec 02):
  - Name (A–Z) — default
  - Best overall score
  - Best atmosphere
  - Cheapest Super Bock
  - Most reviews
  - Venues without the relevant data (no reviews / no price) are always placed last.
    Ties are broken by name.

### 3. Screens (`app.py`)
- **Venue list:** each venue also shows its overall score (e.g. "4.3 ★") and number of
  reviews, or "No reviews yet". A **Sort by** dropdown next to the filters.
- **Venue page:**
  - Summary box: overall score, the three category averages, number of reviews,
    average Super Bock price.
  - **For customers:** a review form with three 1–5 sliders, an optional Super Bock
    price, and an optional comment. If they have already reviewed this venue, the form
    is pre-filled and the button says **Update review**.
  - **For businesses:** no form; a short note that only customers can review.
  - List of reviews, newest first: username, the three scores, Super Bock price (if
    any), comment and date.
- **Security:** comments are shown as plain text (e.g. `st.text`), never rendered as
  Markdown or HTML, so a user cannot inject links, formatting or scripts.

## Out of scope

- Business replies to reviews (level 2)
- Deleting reviews, reporting/flagging reviews, likes on reviews
- Photos in reviews
- Demo reviews in the seed data (separate step later)

## Done when

- [ ] Approved tests pass with `uv run pytest` (all earlier tests still pass).
- [ ] A customer can review a venue and sees the summary update immediately.
- [ ] Reviewing the same venue again updates the review; the review count does not increase.
- [ ] A business user sees no review form, and the logic refuses a business review.
- [ ] Invalid input (score 0 or 6, price 0.20 or 15, comment over 500 characters) is
      rejected with a clear message and nothing is saved.
- [ ] A venue with no reviews shows "No reviews yet" and is sorted last when sorting by score.
- [ ] Each sort option orders the list correctly, together with the filters.
- [ ] A comment such as `**bold** <b>hi</b>` is displayed exactly as typed.
- [ ] Reviews are still there after restarting the app.
- [ ] Still no file other than `db.py` imports `sqlite3`.
