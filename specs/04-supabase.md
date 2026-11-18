# Spec 04 — Permanent storage with Supabase (Postgres)

## Why

The app is deployed on Streamlit Community Cloud, and we confirmed that the SQLite file
is wiped when the app restarts: after a reboot, registered users and reviews were gone.
Restarts also happen on every push and when the app goes to sleep. For a live demo and
real use, data must survive restarts.

We planned for this from the start (decision D4): only `db.py` talks to the database,
so this change should stay inside `db.py` (plus configuration and tests).

## What

### 1. Two storage backends, chosen by configuration
- **Postgres (Supabase)** when a `DATABASE_URL` is configured — read from
  `st.secrets["DATABASE_URL"]` if available, otherwise from the environment variable
  `DATABASE_URL`.
- **SQLite** (current behaviour) when no `DATABASE_URL` is configured. Local development
  without secrets and **all automated tests** keep using SQLite temporary databases.
- Every public function in `db.py` keeps the same name, arguments and return values,
  so `logic.py` and `app.py` do not need to change.

### 2. Postgres implementation (`db.py`)
- New dependency: `psycopg[binary]` (approved by the team). Add it with `uv add`.
- Keep the SQL portable. Handle the differences in one place, e.g.:
  - placeholders (`?` for SQLite, `%s` for psycopg)
  - auto-increment ids (`INTEGER PRIMARY KEY AUTOINCREMENT` vs `GENERATED ALWAYS AS IDENTITY`)
  - getting the id of a newly inserted row
- Always use parameterized queries, as before.
- Tables are created on startup if they do not exist, on both backends.
- On Postgres, enable Row Level Security on every table we create
  (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`) with no policies. Our app connects as
  the database owner and is not affected, but Supabase's public REST API can then not
  read or change our tables.
- Seeding behaves as before: venues are loaded from the CSV only when the venues table
  is empty.

### 3. When the database cannot be reached
- If the connection fails (Supabase down, wrong password, no internet), the app must not
  crash or show a traceback. It shows:
  "Bock'n Bros can't reach the database right now. Please try again in a few minutes."
- Technical details go to the console log only.
- The connection string or password must **never** be shown in the app, in error
  messages, or in logs.

### 4. Secrets
- Locally: `.streamlit/secrets.toml` (already in `.gitignore`). Add a
  `.streamlit/secrets.example.toml` to the repo with a placeholder value and a comment
  explaining where the real value goes.
- On Streamlit Cloud: the same line is pasted into the app's **Secrets** settings.
- Update `README.md` with a short "Database setup" section.

### 5. Structure rule
- Update the structure test: no file other than `db.py` may import `sqlite3` **or**
  `psycopg`. Update `AGENTS.md` "Database rules" to say the same.

## Out of scope

- Moving existing local SQLite data to Supabase (we start fresh; demo venues are seeded)
- Supabase's own login system (Supabase Auth) — we keep our own tested bcrypt login
- The Supabase Python client / REST API — we use plain SQL through psycopg
- Automatic backups / export
- Any change to features, screens or rules

## Done when

- [ ] All existing tests pass with `uv run pytest` (on SQLite, no network needed).
- [ ] New tests cover: choosing SQLite when no `DATABASE_URL` is set, choosing Postgres
      when it is set (without actually connecting), the friendly message when the
      connection fails (simulated), and that the error message never contains the
      connection string.
- [ ] Running locally **without** `secrets.toml` works exactly as before (SQLite).
- [ ] Running locally **with** `secrets.toml` creates the tables in Supabase, seeds the
      5 demo venues once, and a new user/review appears in the Supabase Table Editor.
- [ ] On the deployed app: register a user, add a review, **Reboot app** → both still exist.
- [ ] In Supabase, every table shows Row Level Security as enabled.
- [ ] A wrong password in `secrets.toml` shows the friendly message, not a traceback.
- [ ] `git status` shows no `secrets.toml`; no password anywhere in the repository.
- [ ] No file other than `db.py` imports `sqlite3` or `psycopg`.
