# AGENTS.md — Bock'n Bros

Standing instructions for any AI coding agent working in this repository.
Read this file before every task.

## What the app is

Bock'n Bros is a TripAdvisor-style app for bars and cafés in Lisbon, built around
meeting up for a beer (the name comes from Super Bock). Two kinds of users:

- **Customer**: rates venues (atmosphere, price, quality) and creates/joins meetups
  ("Bock a Bro") such as after-work drinks or watching a football match.
- **Business**: manages its own venue page, posts offers, replies to reviews.

Scope is limited to Lisbon. The app is a university team project (4 people) that will
be shown as a live demo and a code walkthrough. **Every team member must be able to
explain any part of the code.** Prefer simple, readable code over clever code.

## Tech stack (do not change without the team's approval)

- Python, managed with **uv**
- **Streamlit** for the interface
- **SQLite** for storage (planned later move to Postgres/Supabase — see "Database rules")
- **pytest** for tests
- **bcrypt** for password hashing
- GitHub for version control; work on feature branches, merge via pull request

Do not add new libraries or external services without asking first and explaining why.

## Project structure

```
app.py        # screens only: Streamlit UI, reads/writes st.session_state, calls logic.py
logic.py      # rules: validation, permissions, calculations. No Streamlit, no SQL.
db.py         # storage: the ONLY file that talks to the database
seed.py       # fills the database with demo data (venues, demo users)
tests/        # pytest tests, mainly for logic.py and db.py
specs/        # one spec per feature (Why / What / Out of scope / Done when)
docs/         # notes and decisions
```

Keep these boundaries strict. If a screen needs data, `app.py` calls a function in
`logic.py`, which calls `db.py`. This is what lets the team explain the app and
swap the database later.

## Database rules

- All SQL lives in `db.py`. No other file imports `sqlite3` or `psycopg`.
- Always use parameterized queries (`?` placeholders). Never build SQL with f-strings
  or string concatenation.
- Write plain, portable SQL that would also work on Postgres where reasonable
  (avoid SQLite-only tricks), so the move to Supabase only touches `db.py`.
- The database file path comes from one setting in `db.py`, so tests can use a
  temporary database.
- Tables are created automatically on startup if they do not exist.

## Security rules

- Passwords are never stored or logged in plain text — only bcrypt hashes.
- Password fields use `st.text_input(..., type="password")` so input shows as dots.
- Permission checks (e.g. "only customers can review") happen in `logic.py`,
  not only by hiding buttons in the UI.
- Validate all user input in `logic.py` before saving it.
- Secrets and API keys go in `.streamlit/secrets.toml`, which is in `.gitignore`.
  Never commit secrets.
- Error messages for login must not reveal whether the username or the password
  was wrong.

## Working method

1. Read the spec in `specs/` for the task.
2. **Propose tests first** and stop. Wait for the team to approve them.
3. Implement until the approved tests pass. Do not change approved tests without asking.
4. Keep changes limited to what the spec asks for. Anything in "Out of scope" stays out.
5. At the end, summarize in plain language: which files changed, what each change does,
   and any decision you had to make that the spec did not cover.

## Code style

- Short functions with clear names and a one-line docstring.
- Comments explain *why*, not *what*.
- Code, comments and UI text in English.
