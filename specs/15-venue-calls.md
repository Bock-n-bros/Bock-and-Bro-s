# Spec 15 — Venue calls: a bar calling its bros

## Why

A bar with a happy hour starting in an hour has no way to reach the people who follow
it. The feed only helps people who happen to open the app. Businesses are a different
kind of customer than guests: they do not review or meet up, they need to pull people
in. "Call your bros" gives the owner one button that reaches every follower by
notification and email.

Builds on spec 05 (`venue_follows`), 06 (posts), 13 (`venue_owners`) and 14 (`alerts`,
`notify`, `mail.py`).

## What

### 1. Database (`db.py`)
- `alerts.kind` gains `venue_call`. The alert keeps `post_id`, so **Open** leads to the
  post in the feed.
- `get_alerts` joins the venue through the post, so a venue call alert carries
  `venue_name`.
- New table `venue_calls`: id, venue_id, actor_id, post_id, recipients (how many were
  notified), created_at. RLS enabled like the other tables. *Why a table:* the limit is
  per venue, not per recipient, so it cannot be read out of `alerts`.
- `get_venue_followers(venue_id)` returns the users following a venue. Email addresses
  stay private and are exposed only to notification sending code (spec 10).
- `last_venue_call(venue_id)` returns when the venue last called, or None.

### 2. Rules (`logic.py`)
- `VENUE_CALL_COOLDOWN = timedelta(hours=6)` and `MAX_CALL_RECIPIENTS = 200`.
- Only a business user who owns that venue may call (`venue_owners`, as in spec 13).
  Customers, other businesses and signed-out visitors cannot.
- A call is attached to a post: `create_post(..., call_followers=True)`. The call
  happens after the post is saved.
- Recipients are everyone following the venue, except the owner and anyone already
  notified for that post by a tag — nobody gets two notifications for one post.
- **The post is never lost because the call was refused.** A blocked or failed call
  returns the post as created, with a message explaining why nobody was called.
- Limit: one call per venue per 6 hours, whoever sends it. A blocked attempt says how
  long remains. More than `MAX_CALL_RECIPIENTS` followers: the call is refused with a
  message, so we never trip the mail provider's daily limit silently.
- Email: only when SMTP is set up and the recipient has email notifications on. No
  hourly throttle — a call is rare by design and already limited per venue.
- Unlike every other email in the app, a venue call email **may include the post text**
  (at most 300 characters, as plain text). *Why:* this text is public, written by the
  business itself, and the whole point is to say what is happening. Message, comment
  and private post text stay out of email as before.
- A failing email never fails the post or the in-app notification. Each recipient is
  tried on its own; failures are logged and skipped.

### 3. Mail (`mail.py`)
- `send_many(recipients, subject, body)` opens one SMTP connection and sends one message
  per recipient. *Why:* one connection per email would freeze the screen for a minute on
  50 followers, and one shared email would show every follower's address to the others.

### 4. Screens (`app.py`)
- In the post form, a business that owns the chosen venue sees a checkbox
  **"Call your bros"** with a caption: how many follow the bar, and when the bar may
  call again. Within the cooldown the box is disabled and explains why.
- If `[smtp]` is not configured the box still works: followers get the in-app
  notification, and the caption says email is not set up.
- After posting: "Called 23 bros." or the reason nobody was called.
- Followers see the usual pop-up and a line on the Notifications page:
  "The Garden called their bros", with **Open** leading to the post.

## Out of scope

- Scheduling a call for later, or repeating it automatically.
- Muting a single bar (today the user switches all email notifications off in My
  profile). Worth naming as further work in the presentation.
- SMS, push, or calling followers without posting something.
- Checking that the business really owns the bar (D7).

## Done when

- [ ] Approved tests pass with `uv run pytest`; no test sends a real email.
- [ ] Only the owning business can call; customers and other businesses are refused.
- [ ] Every follower gets one notification; the owner gets none; a tagged follower gets
      one notification, not two.
- [ ] A second call within 6 hours is blocked with the time remaining, one after 6 hours
      is allowed, and in both cases the post itself is created.
- [ ] Followers with email notifications off get the in-app notification and no email.
- [ ] A failing SMTP connection leaves the post and the notifications in place.
- [ ] Email addresses never appear in profile, feed, follower or notification data.
- [ ] `venue_calls` is created with RLS enabled on both SQLite and Supabase.
