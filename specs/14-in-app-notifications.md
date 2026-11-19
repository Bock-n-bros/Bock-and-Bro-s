# Spec 14 — In-app notifications, tagging and notification emails

## Why

Users should notice when something happens to them without refreshing pages: someone
liked or commented on their post, tagged them, added them to a group or sent them a
message. If they are not in the app, an email (when they allow it) brings them back.

Builds on spec 06 (posts), 07/09 (comments, likes), 08 (messages, groups) and
10 (email notifications, `users.email_notifications`, `mail.py`).

## What

### 1. Database (`db.py`)
- `post_tags`: post_id, user_id, unique per pair.
- `alerts`: id, recipient_id, actor_id, kind (`like`, `comment`, `tag`, `group_added`,
  `message`), post_id (nullable), conversation_id (nullable), created_at, read_at
  (nullable), toasted (0/1), emailed_at (nullable). RLS enabled like the other tables.
  Named `alerts` because `notifications` already logs Notify bro emails (spec 10).

### 2. Rules (`logic.py`)
- **Triggers:** like on your post, comment on your post, being tagged in a post, being
  added to a group (when it is created or later), a new meetup in your group, and
  messages in your conversations.
- Never notify people about their own actions.
- Liking, unliking and liking again notifies only once.
- Messages: one unread notification per conversation; a newer message moves it to the
  top and shows it as a new pop-up again.
- **Tags:** chosen from a list when posting; at most 10, not yourself, existing users
  only, duplicates ignored. Shown under the post as "with @a, @b".
- **Email:** only when SMTP is set up, the user has email notifications on, and the
  user has chosen that category in My profile (likes/comments, tags, group invites,
  new meetups, messages, Notify bro; all are on until the user changes them). Likes,
  comments and messages: at most one email per hour for the same post or conversation.
  Tags and group invites: every time. Emails never contain message, comment or post
  text. A failing email never fails the action that caused it.
- Notifications are private: users only ever see their own.

### 3. Screens (`app.py`)
- The sidebar has a **Notifications** button with the unread count. Every 10 seconds it
  checks for new notifications and shows each one once as a pop-up (toast) in the top
  right corner. No pop-up for messages in the chat the user is reading.
- A **Notifications** page lists the newest 50 with an icon, text, time, a "New" marker
  for unread ones, and **Open** (post in the feed, or the conversation). Opening the
  page marks them as read.
- The post form has a **Tag people** picker.
- The manual **Notify bro** button (spec 10) stays.

## Out of scope

- Real push notifications to the phone or desktop when the app is closed (Streamlit
  cannot register a service worker); email covers that case.
- Choosing per notification type which ones to see in the app; deleting notifications.
- Tagging by typing @username in the text.

## Done when

- [ ] Approved tests pass with `uv run pytest`.
- [ ] Each trigger creates a notification for the right person only, never for yourself.
- [ ] A new notification pops up within about 10 seconds while the app is open.
- [ ] Opted-out users get no email; message emails are limited to one per hour per chat.
- [ ] No email contains message, comment or post text.
