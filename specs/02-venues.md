# Spec 02 — Venues in Lisbon: list, filter and venue page

## Why

The core of Bock'n Bros is finding a good place for a beer in Lisbon. Before users can
rate places or create meetups, the app needs a set of venues to browse. Each venue also
stores its coordinates now, so the map in a later step can use them without changes.

## What

### 1. Venue data (`data/venues.csv`)
- Venues are stored in a CSV file so anyone on the team can edit the list in Excel or
  Google Sheets without touching code.
- Columns: `name, neighbourhood, address, venue_type, shows_football, latitude, longitude, description`
  - `neighbourhood`: e.g. Bairro Alto, Cais do Sodré, Alfama, Príncipe Real, Chiado,
    Baixa, Santos, Alcântara, Intendente, Campo de Ourique
  - `venue_type`: one of `bar`, `cervejaria`, `pub`, `rooftop`, `café`, `sports bar`
  - `shows_football`: `yes` or `no`
  - `description`: one short sentence
- For now, create the CSV with 5 clearly fictional example venues (names starting with
  "Demo"), so the code can be built and tested. The team will replace them with real
  venues afterwards.

### 2. Database (`db.py`)
- A `venues` table with: id, name, neighbourhood, address, venue_type, shows_football,
  latitude, longitude, description.
- Functions to: insert a venue, count venues, fetch all venues, fetch one venue by id.

### 3. Rules (`logic.py`)
- **Loading venues** (`seed.py` calls logic, logic calls db):
  - On startup, if the venues table is empty, load all rows from `data/venues.csv`.
  - If the table already has venues, do nothing (no duplicates when the app restarts).
  - Each row is validated before saving: name, neighbourhood and address are not empty;
    `venue_type` is one of the allowed values; `shows_football` is yes/no;
    latitude is between 38.68 and 38.80 and longitude between -9.25 and -9.08 (Lisbon).
  - Invalid rows are skipped and reported with the row number and reason; valid rows
    are still loaded.
- **Finding venues:**
  - Filter by neighbourhood (or "All").
  - Filter by venue type (or "All").
  - Filter "Shows football" (on/off).
  - Search by name, case-insensitive, partial match (`super` finds "Demo Super Bar").
  - Filters can be combined. Results sorted alphabetically by name.

### 4. Screens (`app.py`)
- After login, the welcome page is replaced by a **Venues** page:
  - Filters at the top (neighbourhood, type, football toggle, name search).
  - A list of matching venues showing name, neighbourhood and type, each with a
    **View** button.
  - If nothing matches: "No venues match your filters."
- **Venue page:** name, type, neighbourhood, address, football yes/no, description,
  and a **Back to venues** button.
- Username, role and **Log out** stay visible (e.g. in the sidebar).
- Venues are only visible to logged-in users (customers and businesses alike).

## Out of scope

- Reviews and ratings (spec 03)
- Map (later spec — but coordinates are stored now)
- Business users owning or editing venues
- Adding venues from inside the app
- Photos

## Done when

- [ ] Approved tests pass with `uv run pytest` (old auth tests still pass too).
- [ ] Starting the app with an empty database loads the 5 demo venues.
- [ ] Restarting the app does not create duplicate venues.
- [ ] A CSV with a bad row (e.g. coordinates in Porto) loads the good rows and reports the bad one.
- [ ] Each filter works on its own and combined; search ignores upper/lower case.
- [ ] Clicking **View** opens the venue page; **Back to venues** returns to the list.
- [ ] Logged-out users cannot see venues.
- [ ] Still no file other than `db.py` imports `sqlite3`.
