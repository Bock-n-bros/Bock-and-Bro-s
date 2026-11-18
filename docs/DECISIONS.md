# Decision log — Bock'n Bros

Every decision about the code that the team may be asked about in the walkthrough.
Each entry answers four questions: **what** we decided, **why**, **instead of** what,
and **where** it lives. New entries go at the bottom. Nothing is deleted: a reversed
decision gets "Replaced by D-0xx".

---

## Before the login work

Decisions already in the code from specs 01–03 (recorded 18 Nov 2026).

| ID | What | Why |
| --- | --- | --- |
| D-001 | Python + uv, Streamlit, SQLite, pytest | Course stack; one language; nothing to install besides uv |
| D-002 | Three layers: `app.py` screens → `logic.py` rules → `db.py` storage | Each part explainable alone; rules testable without a browser; database swap touches one file |
| D-003 | All SQL in `db.py`, always with `?` placeholders | Blocks SQL injection |
| D-004 | SQLite now, Supabase Postgres when deployed | No setup while building; a deployed app needs a database that survives restarts |
| D-005 | Tables created automatically on startup | A new member runs the app and it works. Changing a table needs the local database deleted once |
| D-006 | Spec first, Codex proposes tests, team approves, then code | The team decides what "working" means, not the AI |
| D-007 | Venues loaded from `data/venues.csv`; bad rows skipped and reported | Editable in Excel; restarts never duplicate venues |
| D-008 | One review per user per venue, enforced by the database too | Nobody can inflate a score, even if the logic has a bug |
| D-009 | Permissions checked in `logic.py`, not only by hiding buttons | A hidden button is not security |
| D-010 | Scores 1–5; Super Bock price €0.50–€10.00; comment max 500 characters | Keeps averages and price sorting meaningful |
| D-011 | No reviews = "No reviews yet", not 0, and sorted last | A 0 would look like a bad venue, not an unknown one |
| D-012 | Comments shown as plain text (`st.text`) | Users cannot inject links or scripts |

---

## Login: Google instead of passwords (Montero)

### D-013 · Google login replaces username and password
*18 Nov 2026 · team meeting*

- **What:** users log in with their Google account. The password login from spec 01 goes.
- **Why:** we store no passwords, so none can leak. Google handles brute-force attacks, two-factor and password resets.
- **Instead of:** keeping username and password with bcrypt (spec 01), which means defending our own password storage and lockout.
- **Where:** spec 04 (to be written in step 5).

### D-014 · One Google Cloud project for the team, no billing
*18 Nov 2026 · step 2*

- **What:** the Google login is registered in a Google Cloud project called "Bock n Bros", with no credit card or billing account. All team members have the Admin role, so the login does not depend on one person.
- **Why:** Google needs to know our app before it lets users log in to it. Login is free, so billing would only add risk.
- **Instead of:** each member making their own project, which would mean four sets of keys and logins that differ per laptop.
- **Where:** console.cloud.google.com, outside the code.


### D-015 · Login open to any Google account ("External")
*18 Nov 2026 · step 2*

- **What:** the login screen is set to "External", so any Google account can log in, not only one organisation's.
- **Why:** customers and bars use personal Gmail accounts. "Internal" only works inside one Google Workspace organisation.
- **Instead of:** "Internal".
- **Where:** Google Auth Platform → Audience.

### D-016 · Testing mode while building, published before the demo
*18 Nov 2026 · step 2*

- **What:** the Google login stays in "Testing", where only listed test users (the team) can log in. It is published before the presentation.
- **Why:** nobody outside the team can log in to a half-built app. In Testing mode the examiners could not log in, so it must be published before the demo.
- **Instead of:** publishing now, which opens the login to anyone while the app is unfinished.
- **Where:** Google Auth Platform → Audience → Test users.

### D-017 · "Bar owner" on screen, `business` in the database
*18 Nov 2026 · step 2*

- **What:** the profile form offers "Customer" or "Bar owner". "Bar owner" is stored as the role `business`.
- **Why:** "Bar owner" is clearer for users. Keeping the stored value means the review rules and teammates' code need no change.
- **Instead of:** renaming the role to `bar_owner` everywhere, which touches every feature for no gain.
- **Where:** spec 04, profile form in `app.py`.

### D-018 · Bar owners are self-declared for now; admin approval later
*18 Nov 2026 · step 2*

- **What:** anyone can choose "Bar owner" when signing up. Nothing checks yet that they run a bar.
- **Why:** login only needs to know the role. Checking ownership needs an admin role and a link from each owner to one venue, which is a separate feature.
- **Instead of:** building admin approval now, which would make the login PR large and block the team.
- **Where:** known limitation. Planned: a later spec where an admin approves each bar owner and links them to their venue, before bar owners can post offers or reply to reviews.

### D-019 · Client secret kept out of Git; local address only for now
*18 Nov 2026 · step 2*

- **What:** the Google client ID and secret are stored privately and shared only by private message. Google accepts logins that return to `http://localhost:8501/oauth2callback` only. The deployed address is added when the app is deployed.
- **Why:** anyone with the secret could pretend to be our app. Google sends users back only to addresses we listed, so a fake site cannot receive their login.
- **Instead of:** committing the secret to the repo, or listing addresses we do not use yet.
- **Where:** Google Auth Platform → Clients. In the code: `.streamlit/secrets.toml` (step 3), which Git ignores.

### D-020 · A random cookie secret, stored with the Google values
*18 Nov 2026 · step 3*

- **What:** `.streamlit/secrets.toml` holds the Google client ID and secret plus a random 64-character cookie secret made with Python's `secrets` module. Git ignores the file.
- **Why:** after login, Streamlit keeps the user's identity in a cookie signed with this secret. Without it, nobody can forge a cookie that says they are someone else.
- **Instead of:** a made-up password such as "bocknbros123", which can be guessed.
- **Where:** `.streamlit/secrets.toml` on each member's computer, never in the repo.

### D-021 · Login is built on its own branch and merged first
*18 Nov 2026 · step 4*

- **What:** all login work happens on the branch `google-login` and reaches `main` through one pull request, reviewed by a teammate. It is merged before the other features.
- **Why:** `main` always works while login is half-built. Login changes the users table and the top of `app.py`, which every feature uses, so merging it first means conflicts appear once, early.
- **Instead of:** working directly on `main`, or merging login last, when every other branch would conflict with it.
- **Where:** GitHub, branch `google-login`.
