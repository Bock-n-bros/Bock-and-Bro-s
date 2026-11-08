# Spec 01 — Project setup, registration and login

## Why

Every other feature (reviews, meetups, business pages) depends on knowing who the
user is and whether they are a customer or a business. Secure accounts are also an
explicit requirement for the project: each user needs a username and password, and
passwords must be protected both on screen and in storage.

## What

### 1. Project setup
- Create the project with `uv` and add dependencies: `streamlit`, `bcrypt`, `pytest`.
- Create the structure from `AGENTS.md`: `app.py`, `logic.py`, `db.py`, `seed.py`,
  `tests/`, `docs/`, plus `.gitignore` (ignore the database file, `.venv`,
  `__pycache__`, `.streamlit/secrets.toml`).
- A short `README.md` explaining how to install and run the app (`uv run streamlit run app.py`).

### 2. Database (`db.py`)
- A `users` table with: id, username (unique), password_hash, role
  (`customer` or `business`), created_at, failed_attempts, locked_until.
- Functions to create a user, fetch a user by username, and update failed attempts / lock.
- Tables are created automatically on startup.

### 3. Rules (`logic.py`)
- **Registration** succeeds only if:
  - username is 3–20 characters, only letters, digits and underscore
  - username is not already taken (case-insensitive: `Bro` and `bro` are the same)
  - password is at least 8 characters and contains at least one letter and one digit
  - the two password fields match
  - role is `customer` or `business`
  - the user has confirmed they are 18 or older
- Passwords are hashed with bcrypt before being passed to `db.py`.
- **Login** succeeds only if the username exists and the password matches the hash.
  - On failure, show one generic message: "Wrong username or password."
  - After 5 failed attempts in a row, the account is locked for 15 minutes.
  - A successful login resets the failed-attempt counter.
- Return clear error messages so the UI can show them.

### 4. Screens (`app.py`)
- When logged out: a page with two tabs, **Log in** and **Sign up**.
  - Sign up: username, password, repeat password (both shown as dots), a choice
    between "Customer" and "Business", and a checkbox "I confirm I am 18 or older".
  - Log in: username and password (shown as dots).
- When logged in: a simple welcome page showing username and role, and a
  **Log out** button. (Customer and business can see the same placeholder page for now.)
- The logged-in user is kept in `st.session_state`.

## Out of scope

- Venues, reviews, meetups, maps (later specs)
- Password reset, email verification, "remember me"
- Login with Google or other providers
- Verifying that a business user really owns a business
- Deployment and Supabase

## Done when

- [ ] Approved tests in `tests/` pass with `uv run pytest`.
- [ ] I can sign up as a customer and as a business, and log in with each.
- [ ] Every rejected registration (short username, taken username, weak password,
      mismatched passwords, 18+ not ticked) shows a clear error and saves nothing.
- [ ] Wrong password shows the generic message; the 6th attempt after 5 failures is
      refused because the account is locked.
- [ ] Passwords appear as dots while typing.
- [ ] Opening the database shows only bcrypt hashes, never the real passwords.
- [ ] After stopping and restarting the app, existing users can still log in.
- [ ] No file other than `db.py` contains SQL or imports `sqlite3`.
