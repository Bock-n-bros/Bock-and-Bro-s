# Spec 04 — Google login replaces username and password

## Why

Every feature depends on knowing who the user is. With Google login the app stores no
passwords, so there is nothing to leak, and Google handles brute-force protection,
two-factor and password resets. The app keeps its own `users` table and user ids, so
reviews and the features other team members are building keep working unchanged.

This spec replaces the registration and login parts of spec 01. The rules for usernames,
roles and the 18+ confirmation stay.

## What

### 1. Setup
- Add the dependency `streamlit[auth]` with `uv add "streamlit[auth]"` (this brings in
  Authlib, which `st.login` needs). Remove `bcrypt` with `uv remove bcrypt`.
- Add `.streamlit/secrets.toml.example` with the `[auth]` keys and placeholder values:
  `redirect_uri`, `cookie_secret`, `client_id`, `client_secret`,
  `server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"`.
- Update `README.md`: how to create `.streamlit/secrets.toml` from the example, that it must
  never be committed, and that the local database must be deleted once after this change.
- Update `AGENTS.md`: replace "bcrypt for password hashing" with
  "Google login through Streamlit's `st.login` (OpenID Connect)".

### 2. Database (`db.py`)
- The `users` table becomes: id, google_sub (unique, not null), email, username,
  username_key (unique), role (`customer` or `business`), created_at.
- Remove the columns password_hash, failed_attempts and locked_until, and the function
  `update_login_state`.
- Functions: create a user (google_sub, email, username, role), fetch a user by google_sub,
  fetch a user by username (case-insensitive, for the uniqueness check), list users
  (without email, for tests).
- The `reviews` and `venues` tables do not change.

### 3. Rules (`logic.py`)
- `find_google_user(database, google_sub)` returns the user as
  `{"id", "username", "role"}` or `None` if this Google account has no profile yet.
  **This dictionary shape must not change**: reviews, chat, leaderboard and map use it.
- `complete_profile(database, google_sub, email, username, role, age_confirmed)` creates
  the profile and returns an `AuthResult`. It succeeds only if:
  - google_sub is a non-empty string and has no profile yet
  - username is 3–20 characters, only letters, digits and underscore
  - username is not taken (case-insensitive)
  - role is `customer` or `business`
  - the user has confirmed they are 18 or older
- Remove `register_user`, `login_user`, `authenticate_user`, `create_account`,
  `has_valid_session_user` and every use of bcrypt.
- No Streamlit in `logic.py`: the Google identity arrives as plain arguments.

### 4. Screens (`app.py`)
- **Logged out** (`st.user.is_logged_in` is false): app title, one sentence about the app,
  and a **Log in with Google** button that calls `st.login()`.
- **Logged in, no profile yet:** a **Finish your profile** form with username, a choice
  between "Customer" and "Bar owner", and the checkbox "I confirm I am 18 or older".
  "Bar owner" is only the label on screen: it is stored as the role `business`, so
  existing code and teammates' features keep working. Errors
  from `complete_profile` are shown. A **Log out** button is also visible.
- **Logged in with a profile:** the existing venue pages, unchanged. The sidebar shows
  username, role and a **Log out** button that calls `st.logout()`.
- On every rerun the user is looked up in the database by `st.user.sub`. The login is no
  longer stored in `st.session_state` (the selected venue may still be).
- The Google email is never shown to other users. Reviews keep showing the username.
- If the `[auth]` section is missing from secrets, show a clear message
  ("Google login is not set up — see README") instead of a crash.

### 5. Tests
- Tests call the `logic.py` and `db.py` functions with fake values such as
  `google_sub="test-sub-1"`. No test calls Google or `st.login`.
- Update the test helpers that create users (for example `make_user` in
  `tests/test_reviews.py`) to the new `create_user` signature.
- Remove password and lockout tests.

## Out of scope

- Changing a role after the profile is created
- Admin role, and an admin approving bar owners and linking each one to their venue
  (planned for a later spec; until then the bar-owner role is self-declared)
- Other login providers, email/password as a fallback
- Deleting accounts
- Deployment and Supabase (the deployed redirect URI is added when the app is deployed)

## Done when

- [ ] Approved tests pass with `uv run pytest` (venue and review tests still pass).
- [ ] Locally, I log in with Google, finish my profile as a customer and review a venue.
- [ ] Logging out and in again goes straight to the venues, without the profile form.
- [ ] A second Google account that picks "Bar owner" sees no review form.
- [ ] A taken username, a bad username, a missing role or an unticked 18+ box shows a
      clear error and saves nothing.
- [ ] No code mentions bcrypt or password hashes; `pyproject.toml` has no bcrypt.
- [ ] `.streamlit/secrets.toml` is not in Git; the example file is.
- [ ] Removing `[auth]` from secrets shows the setup message, not a crash.
- [ ] Still no file other than `db.py` imports `sqlite3`.
- [ ] `docs/DECISIONS.md` has an entry for every decision made in this task.
