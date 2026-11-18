# Spec 08 — Direct messages, groups and Bock a Bro meetups

## Why

Meeting up for a beer needs a way to agree on where and when. Private messages, group
chats and venue-based meetups let users plan together without leaving the app.

Needs spec 05 (finding users).

## What

### 1. Database (`db.py`)
- `conversations`: id, optional name, is_group (0 or 1), created_by and created_at.
- `conversation_members`: conversation_id, user_id, joined_at; unique per conversation
  and user.
- `messages`: id, conversation_id, user_id, text and created_at.
- `events`: id, conversation_id, venue_id, title, starts_at, optional max_attendees,
  created_by and created_at.
- `event_responses`: event_id, user_id, response (`going` or `not_going`) and
  responded_at; unique per event and user.
- All tables are created with RLS enabled. Database functions create and list
  conversations, manage membership, store and fetch messages and meetups, and save
  event responses.

### 2. Rules (`logic.py`)
- **Direct message:** any user can start a direct conversation with another user. If
  one already exists, it is reused. Messaging yourself is refused.
- **Group chat:** the creator chooses at least 2 other users (at least 3 members total,
  at most 20) and may set a trimmed name of up to 50 characters. An empty name is
  allowed; the first three members' usernames become its display title. Duplicate or
  unknown users are refused.
- **Group management:** only the creator can change the name or add/remove members.
  Other members can leave themselves. The creator stays in the group.
- **Privacy:** only members can read or send messages or access meetups in a
  conversation. Membership is checked in `logic.py` for every action.
- **Messages:** text is trimmed, not empty and at most 1000 characters.
- **Meetups:** only group members can create and answer a meetup. It requires a title,
  an existing venue and an ISO start time; max_attendees is optional and, when set, is
  a positive whole number. Members can switch between going and not going. A new going
  response is refused when the maximum is reached. Only the creator can cancel.

### 3. Screens (`app.py`)
- **Messages page:** list conversations with a **New message** action and a **New group**
  action. Groups can be named or unnamed and include a searchable member picker. The
  creator can edit group details; other members can leave.
- **Conversation view:** messages oldest first with `st.chat_message`, username and
  time. The current user's messages are visually distinct. Message text is plain text.
- **Group meetups:** show upcoming events at the top, including title, venue link, local
  date and time, and names of members who are going. Past events appear under
  **Earlier**. Members can answer yes/no; the event creator can cancel.
- A **Message** button on profile pages (spec 05) opens or starts a direct conversation.
- The message list refreshes every 5 seconds with `st.fragment(run_every=5)`.

## Out of scope

- Deleting an entire group
- Real-time delivery (WebSockets); a 5-second refresh is enough for the demo
- Read receipts, typing indicators, unread counts and notifications
- Photos in messages
- Editing or deleting messages
- Blocking users

## Done when

- [ ] Approved tests pass with `uv run pytest`; all earlier tests still pass.
- [ ] Two users can message each other; a second direct start reopens the first.
- [ ] Groups have 3–20 members; names may be blank or up to 50 characters.
- [ ] The creator can rename and manage members; other members can leave.
- [ ] A non-member cannot read or send messages or access group meetups.
- [ ] A member can create a venue-based meetup and members can change their response.
- [ ] A full meetup rejects the next going response with a clear message.
- [ ] Upcoming and past meetups show their venue link, readable date, attendees and
      creator-only cancellation.
- [ ] `events` and `event_responses` are created with RLS enabled.
- [ ] No file other than `db.py` imports a database driver or contains SQL.
