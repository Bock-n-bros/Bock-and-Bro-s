# Spec 13 — A bar's own menu and opening hours

## Why

Bar accounts could sign up (D7) but had nothing to manage. A customer deciding where to
go wants two things first: what a beer costs, and whether the place is open. Letting a
bar keep its own menu and opening hours makes the business account worth having, and
gives the venue page the live information reviews cannot.

This is the "bedriftsbruker: eget sted" half of D3 level 2.

## What

### 1. Database (`db.py`)
- `venue_owners`: id, venue_id (unique), user_id (unique) and claimed_at. Both columns
  are unique, so one venue has at most one bar account and one bar account manages at
  most one venue.
- `venue_hours`: id, venue_id, weekday (0–6), opens_at, closes_at, closed and
  updated_at, unique per venue and weekday.
- `menu_items`: id, venue_id, name, price, position, created_at and updated_at.
- Functions to claim and release a venue, read the owner, read and save one weekday's
  hours, and list, add, change, count and delete menu items.
- All three tables are created with RLS enabled.

### 2. Rules (`logic.py`)
- **Claiming:** only a business account can claim a venue, only one venue per account,
  and only if no other account manages it. A bar can release its venue, which frees it
  for another account.
- **Ownership is checked in `logic.py`** for every menu and hours change, not by hiding
  buttons. A customer, a logged-out visitor or a different bar is refused.
- **Menu item:** a trimmed name of 1–60 characters, and a price from 0.10 € to
  500.00 €, rounded to cents. At most 60 items per venue.
- **Opening hours:** set one weekday at a time, as `HH:MM`. A day can be marked closed
  instead, which clears both times.
- **Open past midnight is normal for a bar**, so a closing time *earlier* than the
  opening time is accepted (16:00–02:00). Only an opening time equal to the closing
  time is refused, because that says nothing.
- A weekday with nothing saved reads as "Not set", not as closed.
- Verifying that an account really owns the bar stays out of scope, as in D7.

### 3. Screens (`app.py`)
- **Bar's own profile:** if no venue is chosen yet, a picker to choose one. Once chosen,
  three expanders: Menu, Opening hours and Bar settings.
- **The menu editor is dynamic:** every line has its own name and price field with Save
  and Remove, and a form at the bottom adds a new line.
- **Opening hours editor:** one small form per weekday with opening time, closing time
  and a Closed box.
- **Any profile of a bar account** shows a card under the name with the bar's name,
  address, opening hours and menu. This is the "bio" a customer reads.
- **Venue page:** opening hours and menu side by side under the venue card.
- Today's weekday is marked in the opening hours, in Lisbon time.
- Menu item names are shown as plain text (`st.text`), as for reviews and comments
  (D16).

## Out of scope

- Verifying that an account really owns the bar
- Several venues per bar account
- Menu categories, descriptions, photos or allergens
- Reordering menu items by dragging
- Special hours for holidays, or a live "Open now" badge
- Currency other than euro

## Done when

- [ ] Approved tests pass with `uv run pytest`; all earlier tests still pass.
- [ ] A bar account can claim a free venue; a customer account cannot.
- [ ] A second account cannot claim a venue that is already managed.
- [ ] One account cannot manage two venues, and releasing frees the venue.
- [ ] Only the managing account can add, change or remove menu items and hours.
- [ ] Name and price limits are enforced at their boundaries.
- [ ] 16:00–02:00 is accepted; identical open and close times are refused.
- [ ] A day marked closed shows "Closed"; a day never set shows "Not set".
- [ ] `venue_owners`, `venue_hours` and `menu_items` are created with RLS enabled.
- [ ] No file other than `db.py` imports a database driver or contains SQL.
