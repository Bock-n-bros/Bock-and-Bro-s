# Spec 08 — Direct messages and group chats

## Why

Meeting up for a beer needs a way to agree on where and when. Private messages and
small group chats let users plan a meetup without leaving the app.

Needs spec 05 (finding users).

## What

### 1. Database (`db.py`)
- A `conversations` table with: id, name (only for groups, else null), is_group
  (0 or 1), created_by (REFERENCES users), created_at.
- A `conversation_members` table with: conversation_id, user_id, joined_at. Unique on
  (conversation_id, user_id).
- A `messages` table with: id, conversation_id, user_id, text, created_at.
- Functions to: create a conversation with its members (in one transaction), find the
  direct conversation between two users, list a user's conversations (newest message
  first, with name or the other person's username, and the last message), check
  membership, fetch messages in a conversation (oldest first, at most the last 100,
  with username), and add a message.

### 2. Rules (`logic.py`)
- **Direct message:** any user can start a direct conversation with any other user. If
  the two already have one, it is reused instead of creating a second one. Messaging
  yourself is refused.
- **Group chat:** the creator gives it a name (1–40 characters, trimmed) and picks at
  least 2 other users (so at least 3 members, at most 20). The creator is added
  automatically. Duplicate or unknown users are refused.
- **Privacy:** only members can read or send messages in a conversation. This is
  checked in `logic.py` on every read and send, not only by hiding the chat.
- **Messages:** text is trimmed, not empty, at most 1000 characters.

### 3. Screens (`app.py`)
- **Messages page:** a list of your conversations (group name or the other person's
  username, last message, time). A **New message** button (pick one user) and a
  **New group** button (name + pick several users with `st.multiselect`, searchable
  by username).
- **Conversation view:** messages oldest first with `st.chat_message`, showing username
  and time; your own messages are visually distinct. A `st.chat_input` box at the bottom.
- A **Message** button on profile pages (spec 05) opens or starts the direct conversation.
- **Refreshing:** the message list is inside `st.fragment(run_every=5)`, so new messages
  appear within about 5 seconds without reloading the page.
- Message text is shown as plain text, never as Markdown or HTML.

## Out of scope

- Real-time delivery (WebSockets); a 5-second refresh is enough for the demo
- Adding or removing members after a group is created, leaving a group
- Read receipts, typing indicators, unread counts, notifications
- Photos in messages
- Editing or deleting messages
- Blocking users

## Done when

- [ ] Approved tests pass with `uv run pytest` (all earlier tests still pass).
- [ ] Two users can send each other messages; starting a second direct conversation
      between the same two users reopens the first.
- [ ] A group with 3+ members works; every member sees every message.
- [ ] A user who is not a member is refused when reading or sending in a conversation
      (tested in logic, not only in the UI).
- [ ] A group with fewer than 3 members, a missing name, or an empty message or one over
      1000 characters is refused.
- [ ] A message sent in one browser window appears in another member's window within
      about 5 seconds.
- [ ] Still no file other than `db.py` imports `sqlite3`.
