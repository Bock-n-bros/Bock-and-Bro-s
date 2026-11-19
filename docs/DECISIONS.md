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

### D-022 · The decision log is a rule in AGENTS.md
*18 Nov 2026 · step 5*

- **What:** AGENTS.md tells every Codex session to add an entry to `docs/DECISIONS.md` after each task.
- **Why:** every member is asked about code they did not write. One log written as the work happens is easier to learn than reading all the code.
- **Instead of:** writing the log from memory before the presentation, when the reasons are forgotten.
- **Where:** `AGENTS.md`, section "Decision log".

### D-023 · Rules are tested automatically; login screens are checked by hand
*18 Nov 2026 · step 6*

- **What:** pytest tests every rule in `logic.py` and `db.py` with fake Google ids. The screens (Google button, profile form, logout, missing-secrets message) are checked by hand against the spec's "Done when" list.
- **Why:** a test cannot log in to Google. The rules are where mistakes would let the wrong person in, so they get the automatic tests.
- **Instead of:** faking Google inside the tests, which adds complex code that tests our fake rather than our app.
- **Where:** `tests/test_auth.py`, `tests/test_reviews.py`; manual list in `specs/04-google-login.md`.

### D-024 · Only the Streamlit auth extra replaces bcrypt
*18 Nov 2026 · step 6*

- **What:** the project uses `streamlit[auth]` and removes `bcrypt`.
- **Why:** Streamlit's OpenID Connect login supplies the approved Google login without a separate password library.
- **Instead of:** adding a direct Authlib dependency or keeping password hashing in the app.
- **Where:** `pyproject.toml` and `uv.lock`.

### D-025 · The users schema follows the new profile shape without a migration
*18 Nov 2026 · step 6*

- **What:** `db.py` creates users with Google subject, email, username, username key, role, and creation time only.
- **Why:** the spec explicitly asks the team to delete the local database once, so migration code would add work outside the feature.
- **Instead of:** converting old password and lockout columns at startup.
- **Where:** `db.py` users table and the setup note in `README.md`.

### D-026 · App authentication stays behind logic wrappers
*18 Nov 2026 · step 6*

- **What:** `app.py` passes the Streamlit Google identity to logic wrappers, which call the database functions and return the stable public user dictionary.
- **Why:** the existing screen/database boundary remains explainable and the email stays out of logged-in user data used by venue features.
- **Instead of:** importing `db.py` directly in the Streamlit screen.
- **Where:** `app.py` and `logic.py`.

### D-027 · Missing auth settings show a setup warning
*18 Nov 2026 · step 6*

- **What:** the app checks the required `[auth]` keys and shows "Google login is not set up — see README" when they are unavailable.
- **Why:** an unfinished local setup should be understandable instead of raising a configuration exception.
- **Instead of:** letting `st.login()` fail with a raw Streamlit error.
- **Where:** `app.py` and `.streamlit/secrets.toml.example`.

### D-028 · Review rows expose usernames but not reviewer emails
*18 Nov 2026 · step 6*

- **What:** venue review results include the reviewer's username and omit their Google email.
- **Why:** users need an identifiable display name, but email is private account data.
- **Instead of:** selecting all user columns when joining reviews.
- **Where:** `db.py` review query and `tests/test_reviews.py`.

---

## Direct messages (spec 08, part 1)

### D-029 · Direct messages use the same tables as future group chats
*18 Nov 2026 · spec 08*

- **What:** `conversations`, `conversation_members` and `messages` tables; a direct message is a conversation with `is_group = 0` and two members.
- **Why:** group chats (rest of spec 08) only need a name and more members, not new tables.
- **Instead of:** a single `messages` table with sender and receiver columns.
- **Where:** `db.py` `init_db`.

### D-030 · One direct conversation per pair of users
*18 Nov 2026 · spec 08*

- **What:** starting a message to someone you already talk to reopens the existing conversation, from either side.
- **Why:** one continuous dialogue per pair, like every chat app.
- **Instead of:** a new thread every time someone presses Message.
- **Where:** `logic.start_direct_conversation`.

### D-031 · Membership is checked in logic on every read and send
*18 Nov 2026 · spec 08*

- **What:** `get_conversation_messages` returns nothing and `send_message` refuses unless the user is a member.
- **Why:** private messages must stay private even if a conversation id is guessed (same idea as D-009).
- **Instead of:** only hiding other people's conversations in the list.
- **Where:** `logic.py` and `tests/test_messages.py`.

### D-032 · New messages appear by refreshing every 5 seconds
*18 Nov 2026 · spec 08*

- **What:** the open conversation is a `st.fragment(run_every=5)`, which re-reads only the message list.
- **Why:** Streamlit has no push/WebSocket for app data; a short refresh is simple and enough for the demo.
- **Instead of:** real-time delivery through an external service.
- **Where:** `app.py` `show_conversation`.

### D-033 · Messages are plain text, max 1000 characters, trimmed
*18 Nov 2026 · spec 08*

- **What:** empty or over-long messages are refused; text is shown with `st.text`.
- **Why:** same protection against injected formatting and links as reviews (D-012).
- **Instead of:** Markdown rendering.
- **Where:** `logic.send_message`, `app.py`.

### D-034 · User search escapes LIKE wildcards
*18 Nov 2026 · spec 08*

- **What:** `%` and `_` typed in the search box match literally.
- **Why:** usernames may contain `_`, which SQL `LIKE` would otherwise treat as "any character".
- **Instead of:** passing the raw search text into the pattern.
- **Where:** `db.search_users`.

### D-035 · Message times are shown in Lisbon time
*18 Nov 2026 · spec 08*

- **What:** timestamps are stored in UTC and displayed as "18 Nov, 21:30" in Europe/Lisbon time.
- **Why:** the app is Lisbon-only, and summer time would otherwise show times an hour off.
- **Instead of:** showing UTC.
- **Where:** `logic.format_message_time`.

### D-054 · Venue weather combines independent public sources

- **What:** venue cards show Open-Meteo forecasts and the nearest Lisbon IPMA station reading independently, cached for 15 minutes.
- **Why:** customers can compare a forecast with a measured hourly observation, while a failed source never produces a guessed reading.
- **Instead of:** relying on one provider or filling missing data with defaults.
- **Where:** `weather.py`, weather rules in `logic.py`, venue cards in `app.py`.

## Following and profiles (spec 05)

### D-036 · Friends are mutual follows, not a separate friend request
*18 Nov 2026 · spec 05*

- **What:** "Friends" on a profile are the users you follow who also follow you back.
- **Why:** one simple follow model (like Instagram) gives both a follower list and a friend list without extra tables or accept/decline screens.
- **Instead of:** Facebook-style friend requests.
- **Where:** `logic.get_profile`.

### D-037 · Users follow bars (venues), not bar-owner accounts
*18 Nov 2026 · spec 05*

- **What:** a separate `venue_follows` table; the Follow bar button is on the venue page.
- **Why:** bar owners are not linked to a venue yet (spec 04), and users think of following "Park Bar", not an account.
- **Instead of:** following the bar owner's user account as the way to follow a bar.
- **Where:** `db.py` `venue_follows`, `logic.follow_venue`.

### D-038 · Following twice or unfollowing twice is not an error
*18 Nov 2026 · spec 05*

- **What:** repeat follows and unfollows succeed and change nothing; the database also has a unique constraint per pair.
- **Why:** a double click or a stale page should never create duplicates or show an error.
- **Instead of:** refusing the second click.
- **Where:** `db.add_follow`, `db.add_venue_follow`, `tests/test_follows.py`.

### D-039 · Page changes from buttons use callbacks
*18 Nov 2026 · spec 05*

- **What:** View / Message / bar buttons set the sidebar page through `on_click` callbacks.
- **Why:** Streamlit only allows changing a widget's value (the page radio) before it is drawn, which is when callbacks run.
- **Instead of:** setting `st.session_state.page` after the sidebar, which raises an error.
- **Where:** `app.py` `open_profile`, `open_venue`, `open_chat`.

## Posts and feed (spec 06)

### D-040 · Photos are files in `uploads/`, only the file name is in the database (Replaced by D-045)
*18 Nov 2026 · spec 06*

- **What:** `db.create_post` writes the photo to `uploads/` under a random name and stores that name in `posts.image_path`; `uploads/` is in `.gitignore`.
- **Why:** keeps the database small, and storage stays in `db.py` so a later move to Supabase Storage touches one file (like D-004).
- **Instead of:** storing image bytes in SQLite.
- **Where:** `db.py` `UPLOADS_DIR`, `create_post`, `get_image_file`.

### D-041 · Photos are checked by type, size and file signature (Replaced by D-045)
*18 Nov 2026 · spec 06*

- **What:** only JPG/PNG/WEBP up to 5 MB, and the first bytes must match the type; `.streamlit/config.toml` also caps uploads at 5 MB.
- **Why:** a renamed file (for example a script called `photo.png`) is refused, without adding an image library.
- **Instead of:** trusting the file extension, or adding Pillow as a new dependency.
- **Where:** `logic._image_problem`, `.streamlit/config.toml`.

### D-042 · The feed includes posts about bars you follow
*18 Nov 2026 · spec 06*

- **What:** feed = your own posts + posts by people you follow + posts tagged with bars you follow, newest first, max 50.
- **Why:** following a bar (D-037) should show what happens there, which is the point of following it.
- **Instead of:** only posts from followed people.
- **Where:** `db.get_feed_posts`.

### D-043 · A post must be tied to a venue and have text, a photo or both
*18 Nov 2026 · spec 06*

- **What:** venue is required; text max 500 characters; empty posts are refused; if saving the row fails the photo file is deleted again.
- **Why:** every post becomes content on a venue page, and no orphan files are left behind.
- **Instead of:** optional venue tags.
- **Where:** `logic.create_post`, `db.create_post`.

### D-044 · SQLite and Postgres share one portable database layer
*18 Nov 2026 · feature/supabase merged into feature/feed*

- **What:** table setup and feed, follow, and messaging queries use backend-aware statements, placeholders and insert helpers.
- **Why:** local SQLite and deployed Postgres need to run the same application behavior without Supabase in local tests.
- **Instead of:** SQLite-specific SQL in feed and chat functions.
- **Where:** `db.py` `_table_statements`, `_execute`, `_insert` and feed/chat storage functions.

### D-045 · Post images are compressed database records
*18 Nov 2026 · permanent image storage*

- **What:** validated JPEG and PNG images are resized to at most 1200 pixels wide and stored as BLOB/BYTEA records; posts keep an `image_id`.
- **Why:** database storage survives Streamlit restarts and one image is fetched only when displayed.
- **Instead of:** files in `uploads/` or loading image bytes into every feed result.
- **Where:** `db.py` `images`, `create_post`, `get_post_image` and post queries.

### D-046 · Comments allow 500 characters and author-only deletion
*18 Nov 2026 · spec 07 update*

- **What:** comments are trimmed, limited to 500 characters, shown as plain text, and deletable only by their author; business users may also comment.
- **Why:** the project uses the same 500-character ceiling as reviews and lets people correct their own posts without granting broad moderation powers.
- **Instead of:** the earlier 300-character limit with no deletion; text formatting through Markdown or HTML.
- **Where:** `logic.py`, `app.py`, `db.py`, and `specs/07-comments.md`.

### D-047 · Likes toggle per user and post
*18 Nov 2026 · spec 09*

- **What:** a unique database constraint allows one like per user and post; the button toggles it, and Python calculates visible counts and the current user's state.
- **Why:** the database protects integrity even when logic is bypassed, while aggregation stays simple and portable.
- **Instead of:** duplicate likes, SQL `GROUP BY`, notifications or a list of likers.
- **Where:** `db.py`, `logic.py`, `app.py`, and `specs/09-likes.md`.

### D-048 · Profile pictures use the shared image table
*18 Nov 2026 · spec 05 update*

- **What:** users reference JPEG or PNG images in the existing image table; uploads are capped at 5 MB and resized to 400 pixels wide. Missing pictures use a circular username initial.
- **Why:** one permanent storage path serves posts and profiles without external avatar services.
- **Instead of:** profile-specific file storage, remote avatar lookup or a blank placeholder.
- **Where:** `db.py`, `logic.py`, `app.py` and `specs/05-follows-and-profiles.md`.

### D-049 · People marks businesses with the text “Bar”
*18 Nov 2026 · spec 05 update*

- **What:** People results show the word “Bar” for business profiles and no badge for customers; search remains username-only.
- **Why:** text communicates the account type without relying on color and preserves email privacy.
- **Instead of:** a color-only marker or searching account email.
- **Where:** `app.py`, `db.py`, `logic.py` and `specs/05-follows-and-profiles.md`.

### D-050 · Groups have a creator and a 20-member limit
*18 Nov 2026 · group messaging*

- **What:** group creators manage members and names; other members may leave. Unnamed groups use the first three member usernames as their title.
- **Why:** groups need clear ownership and a readable fallback without requiring every creator to name the conversation.
- **Instead of:** required names, unrestricted membership or allowing the creator to leave while retaining creator permissions.
- **Where:** `logic.py`, `db.py`, `app.py` and `specs/08-messages.md`.

### D-051 · Meetups belong to group conversations
*18 Nov 2026 · Bock a Bro events*

- **What:** group members create venue-linked meetups, update yes/no responses, and only the creator may cancel; capacity is checked before accepting a yes. Cancellation deletes the event and its responses.
- **Why:** events stay within the group context and capacity feedback is clear; the current schema has no cancellation state to preserve.
- **Instead of:** standalone events, immutable responses, silently rejecting full events or adding a cancelled-state column.
- **Where:** `db.py`, `logic.py`, `app.py` and `specs/08-messages.md`.

### D-052 · Venue community photos remain separate from reviews
*18 Nov 2026 · venue photos*

- **What:** venue pages show up to twelve newest photo posts in a separate section after reviews; selecting one opens that post in the feed.
- **Why:** community posts add visual context without changing review counts or averages, and the section stays absent when there are no photos.
- **Instead of:** mixing posts into review data or loading image bytes with every feed and venue query.
- **Where:** `db.py`, `logic.py`, `app.py` and `tests/test_venue_photos.py`.

### D-053 · Email notices respect consent and a per-recipient cooldown
*18 Nov 2026 · email notifications*

- **What:** direct chats and unanswered meetups send content-free email through `mail.py`; users can opt out, and each recipient gets at most one notice per conversation per hour, regardless of sender.
- **Why:** email can bring members back without revealing private message text, and a recipient-wide cooldown prevents a group from repeatedly notifying one person.
- **Instead of:** message excerpts, app-layer SMTP calls, notifications for opted-out users or a separate cooldown for every sender.
- **Where:** `db.py`, `logic.py`, `mail.py`, `app.py`, `specs/10-notifications.md` and `.streamlit/secrets.toml.example`.

### D-046 · Tables are created once per run, not on every query
*18 Nov 2026 · Supabase performance*

- **What:** `init_db()` remembers which database it has already prepared and returns immediately on later calls.
- **Why:** on Supabase every CREATE/ALTER statement is a network round trip; with init_db called from many read functions, the map page sent hundreds of them and became very slow.
- **Instead of:** checking all ten tables before every read.
- **Where:** `db.init_db`.

### D-055 · Compact map cards and venue pages share one renderer

- **What:** the selected map venue and full venue page use `render_venue_card` with a compact mode for the map.
- **Why:** weather, summaries and review actions stay consistent while the map keeps a shorter card.
- **Instead of:** maintaining separate copies of the same venue details and actions.
- **Where:** `app.py` and the card data helpers in `logic.py`.

### D-056 · Demo venues are removed only when unreferenced

- **What:** the seed CSV contains real venues only, and a one-off script deletes `Demo ` rows only when they have no reviews, venue followers, posts or events.
- **Why:** unused placeholders can be removed without losing user activity or breaking venue-linked records.
- **Instead of:** deleting every matching venue or retaining fictional seed rows.
- **Where:** `data/venues.csv`, `remove_demo_venues.py`, `db.py` and `tests/test_remove_demo_venues.py`.

### D-057 · Compact venue summaries keep status and actions scannable

- **What:** rating, count and cheapest price share one line; weather uses a muted box and actions use two compact rows.
- **Why:** the selected map card keeps the key facts visible without repeating its no-review state.
- **Instead of:** separate status lines and equally prominent navigation buttons.
- **Where:** `logic.format_venue_card_summary`, `styles.py` and `app.py`.

### D-058 · App logic references are checked against the logic module

- **What:** a source-level test checks every `logic.<name>` used by `app.py` against `logic.py` definitions and imports.
- **Why:** missing screen helpers fail in pytest instead of appearing only when a user opens the screen.
- **Instead of:** relying on a manual app launch to find broken screen-to-logic references.
- **Where:** `tests/test_app_logic_references.py`.

### D-059 · Map and venue list read all review summaries in one query
*19 Nov 2026 · Supabase performance*

- **What:** `db.get_all_review_summaries()` reads every review once and builds the summary per venue in Python; the map, the venue list and sorting use it.
- **Why:** one query per venue (two on the map) meant 40–60 network round trips per page on Supabase.
- **Instead of:** calling `get_review_summary` and `get_reviews_for_venue` in a loop over venues.
- **Where:** `db.get_all_review_summaries`, `logic.get_review_summaries`, `logic.sort_venues`, `app.py` map and venue list.

### D-060 · Bock'n Bros theme: beer red, gold and cream
*19 Nov 2026 · design*

- **What:** colours and fonts (Oswald headings, Inter text) in `[theme]` in `.streamlit/config.toml`; a red top banner with our own beer illustration, gold heading underlines and cream cards in `styles.THEME_CSS`; logo, illustration and font files in `static/`.
- **Why:** gives the app a recognisable Lisbon beer-bar look inspired by Super Bock colours, mostly through Streamlit's built-in theme so little custom CSS is needed.
- **Instead of:** Super Bock's own logo or label, which is their trademark; the logo and bottles are our own drawings.
- **Where:** `.streamlit/config.toml`, `styles.py`, `app.py` (top), `static/`.

### D-061 · Venue seeding runs only for an empty venues table

- **What:** CSV venues are inserted only when the database has no venue rows.
- **Why:** old app versions re-seeded missing rows into the shared Supabase database after it was already populated.
- **Instead of:** filling in missing CSV names on every startup.
- **Where:** `logic.load_venues`, `seed.py` and `specs/02-venues.md`.

### D-062 · iPhone (HEIC) and WEBP photos are accepted and converted to JPEG
*19 Nov 2026 · posts and profile pictures*

- **What:** uploads may be JPG, PNG, HEIC/HEIF or WEBP; HEIC and WEBP are converted to JPEG, and every photo is turned upright using its EXIF orientation. The 5 MB limit and the content check (the file must really be that image type) stay.
- **Why:** iPhones save photos as HEIC by default, and browsers cannot display HEIC; phone photos also store their rotation separately.
- **Instead of:** asking users to convert photos themselves, or storing HEIC that most browsers cannot show.
- **Where:** `db._prepare_image`, `db._image_mime_type`, `logic.IMAGE_TYPES`; new dependency `pillow-heif` (adds HEIC support to Pillow). Two older tests that required WEBP to be refused were changed.

### D-063 · Posts can use a typed-in "Other" location instead of a venue
*19 Nov 2026 · posts*

- **What:** the venue list in the post form ends with "Other – type your own location"; such posts store `location_name` (max 60 characters, extra spaces removed) and no `venue_id`. They show in feeds and on profiles, with a pin icon instead of a link, but not on any venue page.
- **Why:** people also meet at viewpoints, parks or private places that are not in the venue list.
- **Instead of:** letting users add new venues, which would need moderation.
- **Where:** `posts.location_name`, nullable `posts.venue_id`, `logic.create_post`, `app.show_post_form`, `app.show_post`. Existing databases are upgraded at startup (Postgres drops NOT NULL; local SQLite copies the posts table once). One test now only checks the row-level-security statements, since startup also runs this upgrade.

### D-064 · Map pins and legend share rating colors

- **What:** map rows carry rating-based fill and outline colors, with a white fill and amber outline for venues without reviews.
- **Why:** pin colors match the legend, and the selected card reuses the map's review summary so both show the same average.
- **Instead of:** separate color and rating calculations for the map and card.
- **Where:** `logic.marker_color`, `app.render_map`, `styles.MAP_LEGEND_HTML` and `tests/test_map.py`.

### D-065 · Map rows are built in testable logic code

- **What:** `logic.build_map_rows` creates map data and reads fill and outline values from the marker color dictionary.
- **Why:** a direct row-building test catches color-shape mismatches before the map renders.
- **Instead of:** creating rows inline in the Streamlit screen, where the conversion is harder to test.
- **Where:** `logic.py`, `app.render_map` and `tests/test_map.py`.
