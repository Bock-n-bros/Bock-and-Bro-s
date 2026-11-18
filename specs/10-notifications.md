# Spec 10 — Email notifications

## Why

People may not have the app open when a new direct message arrives or a group meetup
needs a response. A short email reminder brings them back without disclosing message
content.

## What

### 1. Database (`db.py`)
- Add `users.email_notifications`, default 1, and let users change their own setting.
- Add `notifications`: id, conversation_id, sender_id, recipient_id and sent_at. Enable
  RLS with the other application tables.
- Keep email addresses private; expose them only to notification sending code.

### 2. Rules (`logic.py`)
- Only a conversation member can notify another member.
- A direct conversation notification goes to its other member. A meetup notification
  goes only to group members who have not responded to that meetup.
- Do not send when a recipient has disabled email notifications.
- Allow at most one notification per recipient and conversation per hour, regardless
  of sender. A
  blocked request explains how long remains.
- Emails identify the sender and conversation. Meetup emails also include title, venue,
  date and time. Never include message text; include a link to the app.
- SMTP failures return a friendly message and are logged. Missing SMTP settings do not
  crash the app.

### 3. Screens (`app.py` and `mail.py`)
- Direct conversations and upcoming meetups show a **Notify bro** action.
- If `[smtp]` is not configured, the action is disabled and explains that notifications
  are not set up.
- My profile lets the signed-in user turn email notifications on or off.
- `mail.py` sends messages over SMTP using `[smtp]` secrets. `APP_URL` optionally sets
  the link destination; local development defaults to `http://localhost:8501`.

## Out of scope

- Emailing message contents, attachments or event updates after responses
- Push notifications, reminders scheduled for a future time, or notification history UI
- Choosing notification types separately

## Done when

- [ ] Approved tests pass; no test sends a real email.
- [ ] A second notification within one hour is blocked, and one after an hour is allowed.
- [ ] Opted-out users receive nothing and non-members cannot notify.
- [ ] Direct emails omit message text; meetup emails go only to members without responses.
- [ ] SMTP failures are friendly in the app and details are logged.
- [ ] Missing SMTP settings disable the visible action without crashing.
- [ ] Email addresses do not appear in user-facing profile, search, conversation or meetup data.
- [ ] `notifications` is created with RLS enabled, and email preferences default on.
