"""Render account screens and the logged-in venue browser."""

import html
from datetime import date, datetime, time

import streamlit as st

import logic


try:
    logic.initialize_app_data()
except RuntimeError as error:
    st.error(str(error))
    st.stop()
st.title("Bock'n Bros")

def google_auth_is_configured():
    """Return whether the required Streamlit auth settings are available."""
    try:
        auth = st.secrets.get("auth")
    except Exception:
        return False
    required = {"redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url"}
    return auth is not None and required.issubset(auth)


if not google_auth_is_configured():
    st.write("Find Lisbon bars and cafés, rate venues, and meet up for a beer.")
    st.warning("Google login is not set up — see README")
    st.stop()

if not st.user.is_logged_in:
    st.write("Find Lisbon bars and cafés, rate venues, and meet up for a beer.")
    if st.button("Log in with Google"):
        st.login()
    st.stop()

user = logic.find_app_google_user(st.user.sub)
if user is None:
    st.header("Finish your profile")
    with st.form("profile_form"):
        username = st.text_input("Username")
        role_label = st.radio("Account type", ["Customer", "Bar owner"])
        age_confirmed = st.checkbox("I confirm I am 18 or older")
        submitted = st.form_submit_button("Finish profile")
    if submitted:
        role = "business" if role_label == "Bar owner" else "customer"
        result = logic.complete_app_profile(
            st.user.sub, st.user.email, username, role, age_confirmed
        )
        if result.success:
            st.rerun()
        st.error(result.message)
    if st.button("Log out", key="profile-logout"):
        st.logout()
    st.stop()

@st.fragment(run_every=5)
def show_conversation(user, conversation_id):
    """Show a conversation's messages and refresh them every few seconds."""
    messages = logic.get_app_conversation_messages(user, conversation_id)
    if messages is None:
        st.error("You are not part of this conversation.")
        return
    if not messages:
        st.caption("No messages yet. Say hi!")
    for message in messages:
        is_mine = message["user_id"] == user["id"]
        with st.chat_message(message["username"]):
            label = "You" if is_mine else message["username"]
            if not is_mine and message["role"] == "business":
                label += " · Bar owner"
            st.caption(f"{label} · {logic.format_message_time(message['created_at'])}")
            st.text(message["text"])


def show_messages_page(user):
    """Show the conversation list, or one open conversation."""
    conversation_id = st.session_state.get("conversation_id")
    if conversation_id is not None:
        conversation = logic.get_app_conversation_details(user, conversation_id)
        if conversation is None:
            st.session_state.pop("conversation_id", None)
            st.rerun()
        title = conversation["title"]
        if st.button("← All conversations"):
            st.session_state.pop("conversation_id", None)
            st.rerun()
        st.subheader(title)
        if conversation["is_group"]:
            show_group_controls(user, conversation)
            show_group_events(user, conversation_id)
        show_conversation(user, conversation_id)
        text = st.chat_input("Write a message", max_chars=logic.MAX_MESSAGE_LENGTH)
        if text:
            result = logic.send_app_message(user, conversation_id, text)
            if result.success:
                st.rerun()
            st.error(result.message)
        return

    st.header("Messages")
    with st.expander("New message"):
        query = st.text_input("Search by username", key="message_search")
        people = logic.search_app_people(user, query)
        if query.strip() and not people:
            st.write("No users found.")
        for person in people:
            avatar_col, name_col, button_col = st.columns([1, 3, 1])
            show_avatar(person, 40, avatar_col)
            name_col.write(person["username"])
            if person["role"] == "business":
                name_col.caption("Bar")
            if button_col.button("Message", key=f"message-{person['id']}"):
                result = logic.start_app_direct_conversation(user, person["id"])
                if result.success:
                    st.session_state.conversation_id = result.conversation_id
                    st.rerun()
                st.error(result.message)

    with st.expander("New group"):
        group_name = st.text_input("Group name (optional)", max_chars=logic.MAX_GROUP_NAME_LENGTH)
        candidates = logic.get_app_group_candidates(user)
        names_by_id = {person["id"]: person["username"] for person in candidates}
        member_ids = st.multiselect("Members", list(names_by_id), format_func=names_by_id.get)
        if st.button("Create group", key="create-group"):
            result = logic.create_app_group(user, group_name, member_ids)
            if result.success:
                st.session_state.conversation_id = result.conversation_id
                st.rerun()
            st.error(result.message)

    conversations = logic.list_app_conversations(user)
    if not conversations:
        st.write("No conversations yet. Use New message to find someone.")
    for conversation in conversations:
        avatar_col, text_col, button_col = st.columns([1, 4, 1])
        show_avatar({"username": conversation["title"],
                     "image_id": conversation.get("other_image_id")}, 40, avatar_col)
        text_col.write(conversation["title"] + (" · Bar owner" if conversation["other_role"] == "business" else ""))
        if conversation["last_message"]:
            preview = conversation["last_message"]
            if conversation["last_sender_id"] == user["id"]:
                preview = "You: " + preview
            text_col.text(preview if len(preview) <= 80 else preview[:77] + "...")
            text_col.caption(logic.format_message_time(conversation["last_message_at"]))
        else:
            text_col.caption("No messages yet")
        if button_col.button("Open", key=f"conversation-{conversation['id']}"):
            st.session_state.conversation_id = conversation["id"]
            st.rerun()


def show_group_controls(user, conversation):
    """Show creator management and member leave actions."""
    creator = conversation["created_by"] == user["id"]
    with st.expander("Group members and settings"):
        if creator:
            with st.form(f"rename-group-{conversation['id']}"):
                name = st.text_input("Group name", value=conversation["name"] or "",
                                     max_chars=logic.MAX_GROUP_NAME_LENGTH)
                rename = st.form_submit_button("Save name")
            if rename:
                result = logic.rename_app_group(user, conversation["id"], name)
                if result.success:
                    st.rerun()
                st.error(result.message)
        st.caption("Members")
        member_ids = {member["id"] for member in conversation["members"]}
        for member in conversation["members"]:
            member_col, action_col = st.columns([4, 1])
            member_col.write(member["username"])
            if creator and member["id"] != user["id"]:
                if action_col.button("Remove", key=f"remove-group-{conversation['id']}-{member['id']}"):
                    result = logic.remove_app_group_member(user, conversation["id"], member["id"])
                    if result.success:
                        st.rerun()
                    st.error(result.message)
        if creator:
            candidates = [person for person in logic.get_app_group_candidates(user)
                          if person["id"] not in member_ids]
            names_by_id = {person["id"]: person["username"] for person in candidates}
            selected = st.selectbox("Add member", [None, *names_by_id],
                                    format_func=lambda person_id: names_by_id.get(person_id, "Choose a person"))
            if st.button("Add member", key=f"add-group-{conversation['id']}") and selected is not None:
                result = logic.add_app_group_member(user, conversation["id"], selected)
                if result.success:
                    st.rerun()
                st.error(result.message)
        elif st.button("Leave group", key=f"leave-group-{conversation['id']}"):
            result = logic.leave_app_group(user, conversation["id"])
            if result.success:
                st.session_state.pop("conversation_id", None)
                st.rerun()
            st.error(result.message)


def show_group_events(user, conversation_id):
    """Show upcoming and previous meetups in a group conversation."""
    event_lists = logic.get_app_conversation_events(user, conversation_id)
    if event_lists is None or not event_lists["is_group"]:
        return
    with st.expander("Create Bock a Bro"):
        venues = {venue["id"]: venue["name"] for venue in logic.get_venues()}
        with st.form(f"create-event-{conversation_id}"):
            venue_id = st.selectbox("Bar or café", list(venues), index=None,
                                    format_func=venues.get, placeholder="Choose a venue")
            title = st.text_input("Meetup title")
            event_date = st.date_input("Date", value=date.today())
            event_time = st.time_input("Time", value=time(20, 0))
            has_limit = st.checkbox("Set a maximum number of attendees")
            max_attendees = st.number_input("Maximum attendees", min_value=1, step=1) if has_limit else None
            submitted = st.form_submit_button("Create meetup")
        if submitted:
            starts_at = datetime.combine(event_date, event_time).isoformat()
            result = logic.create_app_event(user, conversation_id, venue_id, title, starts_at, max_attendees)
            if result.success:
                st.rerun()
            st.error(result.message)

    if event_lists["upcoming"]:
        st.subheader("Bock a Bro")
        for event in event_lists["upcoming"]:
            show_group_event(user, event)
    if event_lists["past"]:
        st.subheader("Tidligere")
        for event in event_lists["past"]:
            show_group_event(user, event)


def show_group_event(user, event):
    """Render one meetup, responses and creator-only cancellation."""
    with st.container(border=True):
        st.write(event["title"])
        st.button(event["venue_name"], key=f"event-venue-{event['id']}",
                  on_click=open_venue, args=(event["venue_id"],))
        attendees = ", ".join(person["username"] for person in event["attendees"]) or "No one yet"
        capacity = f"{event['going_count']} going"
        if event["max_attendees"] is not None:
            capacity += f" / {event['max_attendees']} places"
        st.caption(f"{logic.format_event_time(event['starts_at'])} · {capacity}")
        st.text(f"Going: {attendees}")
        yes_col, no_col = st.columns(2)
        if yes_col.button("Going", key=f"event-going-{event['id']}"):
            result = logic.respond_app_event(user, event["id"], "going")
            if result.success:
                st.rerun()
            st.error(result.message)
        if no_col.button("Not going", key=f"event-not-going-{event['id']}"):
            result = logic.respond_app_event(user, event["id"], "not_going")
            if result.success:
                st.rerun()
            st.error(result.message)
        if event["created_by"] == user["id"] and st.button("Cancel meetup", key=f"event-cancel-{event['id']}"):
            result = logic.cancel_app_event(user, event["id"])
            if result.success:
                st.rerun()
            st.error(result.message)


def open_profile(profile_id, my_id):
    """Button callback: go to a user's profile page."""
    st.session_state.profile_id = profile_id
    st.session_state.page = "My profile" if profile_id == my_id else "People"


def open_venue(venue_id):
    """Button callback: go to a venue's page."""
    st.session_state.venue_id = venue_id
    st.session_state.page = "Venues"


def open_post_in_feed(post_id):
    """Button callback: open a community photo's post in the feed."""
    st.session_state.feed_post_id = post_id
    st.session_state.page = "Feed"


def open_chat(user, other_user_id):
    """Button callback: open or start the direct conversation with a user."""
    result = logic.start_app_direct_conversation(user, other_user_id)
    if result.success:
        st.session_state.conversation_id = result.conversation_id
        st.session_state.page = "Messages"
    else:
        st.session_state.flash_error = result.message


def role_label(person):
    """Return a username with a 'Bar owner' marker for business accounts."""
    return person["username"] + (" · Bar owner" if person["role"] == "business" else "")


def show_person_list(user, people, empty_text, key):
    """Show a list of users, each with a button to open their profile."""
    if not people:
        st.caption(empty_text)
    for person in people:
        avatar_col, name_col, button_col = st.columns([1, 4, 1])
        show_avatar(person, 40, avatar_col)
        name_col.write(person["username"])
        if person["role"] == "business":
            name_col.caption("Bar")
        button_col.button("View", key=f"{key}-{person['id']}",
                          on_click=open_profile, args=(person["id"], user["id"]))


def show_avatar(person, size=48, target=None):
    """Show a stored profile picture or a circular username initial."""
    if target is None:
        target = st
    avatar = logic.get_app_profile_avatar(person)
    if avatar["bytes"]:
        target.image(avatar["bytes"], width=size)
        return
    initial = html.escape(avatar["initial"])
    target.markdown(
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'display:flex;align-items:center;justify-content:center;'
        f'background:#e7edf2;color:#263746;font-weight:700">{initial}</div>',
        unsafe_allow_html=True,
    )


def show_profile(user, profile_id):
    """Show a profile with counts, follow and message buttons and the four lists."""
    profile = logic.get_app_profile(user, profile_id)
    if profile is None:
        st.write("This user could not be found.")
        return
    avatar_col, heading_col = st.columns([1, 5])
    show_avatar(profile, 88, avatar_col)
    heading_col.header(profile["username"])
    notes = []
    if profile["role"] == "business":
        notes.append("Bar owner")
    if profile["follows_me"] and not profile["is_me"]:
        notes.append("Follows you")
    if notes:
        st.caption(" · ".join(notes))

    if profile["is_me"]:
        with st.form("profile-picture-form", clear_on_submit=True):
            picture = st.file_uploader("Profile picture (JPEG or PNG)", type=logic.IMAGE_TYPES)
            save_picture = st.form_submit_button("Save picture")
        if save_picture:
            if picture is None:
                st.error("Choose a picture first.")
            else:
                result = logic.set_app_profile_picture(user, picture.getvalue(), picture.name)
                if result.success:
                    st.rerun()
                st.error(result.message)
        if profile["image_id"] and st.button("Remove picture", key="remove-profile-picture"):
            result = logic.remove_app_profile_picture(user)
            if result.success:
                st.rerun()
            st.error(result.message)

    columns = st.columns(4)
    for column, (label, items) in zip(columns, [
        ("Friends", profile["friends"]), ("Followers", profile["followers"]),
        ("Following", profile["following"]), ("Bars", profile["bars"]),
    ]):
        column.metric(label, len(items))

    if not profile["is_me"]:
        follow_col, message_col, _ = st.columns([1, 1, 3])
        if profile["is_followed_by_me"]:
            if follow_col.button("Unfollow", key="unfollow-user"):
                logic.unfollow_app_user(user, profile["id"])
                st.rerun()
        elif follow_col.button("Follow", key="follow-user", type="primary"):
            result = logic.follow_app_user(user, profile["id"])
            if result.success:
                st.rerun()
            st.error(result.message)
        message_col.button("Message", key="message-user", on_click=open_chat, args=(user, profile["id"]))

    friends_tab, followers_tab, following_tab, bars_tab = st.tabs(["Friends", "Followers", "Following", "Bars"])
    with friends_tab:
        show_person_list(user, profile["friends"], "No friends yet. Friends are people who follow each other.", "friend")
    with followers_tab:
        show_person_list(user, profile["followers"], "No followers yet.", "follower")
    with following_tab:
        show_person_list(user, profile["following"], "Not following anyone yet.", "following")
    with bars_tab:
        if not profile["bars"]:
            st.caption("Not following any bars yet.")
        for venue in profile["bars"]:
            name_col, button_col = st.columns([4, 1])
            name_col.write(f"{venue['name']} · {venue['neighbourhood']}")
            button_col.button("View", key=f"bar-{venue['id']}", on_click=open_venue, args=(venue["id"],))

    st.subheader("Posts")
    show_post_list(user, logic.get_app_user_posts(profile["id"], user), "No posts yet.", "profile")


def show_people_page(user):
    """Show user search, or the selected profile."""
    if st.session_state.get("profile_id") is not None:
        if st.button("← Search people"):
            st.session_state.pop("profile_id", None)
            st.rerun()
        show_profile(user, st.session_state.profile_id)
        return
    st.header("People")
    query = st.text_input("Search by username", key="people_search")
    people = logic.search_app_people(user, query)
    if query.strip() and not people:
        st.write("No users found.")
    show_person_list(user, people, "", "search")


def show_post(user, post, key):
    """Show one post: author, bar, photo, text and time."""
    with st.container(border=True):
        author_image_col, author_col, venue_col = st.columns([1, 2, 2])
        show_avatar({"username": post["username"], "image_id": post["author_image_id"]},
                    40, author_image_col)
        author_col.button(role_label(post), key=f"{key}-author-{post['id']}", type="tertiary",
                          icon=":material/person:", on_click=open_profile, args=(post["user_id"], user["id"]))
        venue_col.button(post["venue_name"], key=f"{key}-venue-{post['id']}", type="tertiary",
                         icon=":material/sports_bar:", on_click=open_venue, args=(post["venue_id"],))
        if post["image_id"]:
            image_bytes = logic.get_app_post_image(post)
            if image_bytes is not None:
                st.image(image_bytes, width="stretch")
            else:
                st.caption("Photo unavailable")
        if post["text"]:
            st.text(post["text"])
        st.caption(logic.format_post_time(post["created_at"]))
        like_label = "Unlike" if post["liked_by_me"] else "Like"
        if st.button(f"{like_label} · {post['like_count']}", key=f"{key}-like-{post['id']}"):
            result = logic.toggle_app_like(user, post["id"])
            if result.success:
                st.rerun()
            st.error(result.message)
        comments = logic.get_app_comments(post["id"])
        with st.expander(f"💬 {len(comments)} comments"):
            for comment in comments:
                author_role = "Bar owner" if comment["role"] == "business" else "Customer"
                st.caption(f"{comment['username']} · {author_role} · "
                           f"{logic.format_message_time(comment['created_at'])}")
                st.text(comment["text"])
                if comment["user_id"] == user["id"]:
                    if st.button("Delete", key=f"{key}-delete-comment-{comment['id']}"):
                        result = logic.delete_app_comment(user, comment["id"])
                        if result.success:
                            st.rerun()
                        st.error(result.message)
            with st.form(f"{key}-comment-form-{post['id']}", clear_on_submit=True):
                comment_text = st.text_input("Write a comment", max_chars=500)
                submitted = st.form_submit_button("Send")
            if submitted:
                result = logic.add_app_comment(user, post["id"], comment_text)
                if result.success:
                    st.rerun()
                st.error(result.message)


def show_post_form(user, key, venue_id=None):
    """Show the form for a new post; the venue is fixed on a venue page."""
    with st.form(f"{key}-post-form", clear_on_submit=True):
        if venue_id is None:
            venues = {venue["id"]: venue["name"] for venue in logic.get_venues()}
            chosen_venue = st.selectbox("Bar or café", list(venues), index=None,
                                        format_func=venues.get, placeholder="Choose where you are")
        else:
            chosen_venue = venue_id
        text = st.text_area("What's happening?", max_chars=logic.MAX_POST_LENGTH)
        photo = st.file_uploader("Photo (optional)", type=logic.IMAGE_TYPES)
        submitted = st.form_submit_button("Post", type="primary")
    if submitted:
        result = logic.create_app_post(user, chosen_venue, text,
                                       photo.getvalue() if photo else None,
                                       photo.name if photo else None)
        if result.success:
            st.toast(result.message)
        else:
            st.error(result.message)


def show_post_list(user, posts, empty_text, key):
    """Show a list of posts, or a note when there are none."""
    if not posts:
        st.caption(empty_text)
    for post in posts:
        show_post(user, post, key)


def show_feed_page(user):
    """Show the new-post form and the feed."""
    st.header("Feed")
    with st.expander("New post", icon=":material/add_a_photo:"):
        show_post_form(user, "feed")
    feed_posts = logic.get_app_feed(user)
    selected_post_id = st.session_state.pop("feed_post_id", None)
    if selected_post_id is not None:
        selected_post = logic.get_app_post_for_viewer(selected_post_id, user)
        if selected_post is not None:
            st.caption("Opened from venue photos")
            show_post(user, selected_post, "feed-selected")
            feed_posts = [post for post in feed_posts if post["id"] != selected_post_id]
    show_post_list(user, feed_posts,
                   "Your feed is empty. Follow people under People, or follow bars on their page.", "feed")


def show_venue_community_photos(user, venue_id):
    """Show the venue's recent photo posts when any exist."""
    photos = logic.get_app_venue_community_photos(venue_id)
    if not photos:
        return
    st.subheader("Photos from the community")
    for post in photos:
        photo = logic.get_app_post_image(post)
        if photo is None:
            continue
        st.image(photo, caption=f"{post['username']} · {logic.format_post_time(post['created_at'])}",
                 width="stretch")
        st.button("Open post in feed", key=f"community-photo-{post['id']}",
                  on_click=open_post_in_feed, args=(post["id"],))


PAGES = ["Feed", "Venues", "People", "Messages", "My profile"]

if logic.can_view_venues(user):
    with st.sidebar:
        st.write(user["username"])
        st.write(f"Role: {user['role'].title()}")
        page = st.radio("Go to", PAGES, key="page")
        if st.button("Log out"):
            for key in ("venue_id", "conversation_id", "profile_id"):
                st.session_state.pop(key, None)
            st.logout()

    if "flash_error" in st.session_state:
        st.error(st.session_state.pop("flash_error"))
    if page == "Feed":
        show_feed_page(user)
        st.stop()
    if page == "Messages":
        show_messages_page(user)
        st.stop()
    if page == "People":
        show_people_page(user)
        st.stop()
    if page == "My profile":
        show_profile(user, user["id"])
        st.stop()

    if st.session_state.get("venue_id") is not None:
        selected = logic.get_venue(st.session_state.venue_id)
        if selected is not None:
            st.header(selected["name"])
            st.write(f"Type: {selected['venue_type']}")
            st.write(f"Neighbourhood: {selected['neighbourhood']}")
            st.write(f"Address: {selected['address']}")
            st.write(f"Shows football: {selected['shows_football']}")
            st.write(selected["description"])
            follow_status = logic.get_app_venue_follow_status(user, selected["id"])
            count_col, button_col, _ = st.columns([1, 1, 3])
            count_col.caption(f"{follow_status['followers']} followers")
            if follow_status["is_following"]:
                if button_col.button("Unfollow bar", key="unfollow-venue"):
                    logic.unfollow_app_venue(user, selected["id"])
                    st.rerun()
            elif button_col.button("Follow bar", key="follow-venue", type="primary"):
                result = logic.follow_app_venue(user, selected["id"])
                if result.success:
                    st.rerun()
                st.error(result.message)
            summary = logic.get_venue_review_summary(selected["id"])
            st.subheader("Reviews")
            if summary["review_count"]:
                st.write(f"{summary['overall']:.1f} ★ · {summary['review_count']} reviews")
                st.write(f"Atmosphere {summary['atmosphere']:.1f} · Value {summary['value']:.1f} · Quality {summary['quality']:.1f}")
                price_average = summary["average_super_bock_price"]
                st.write(f"Average Super Bock price: €{price_average:.2f}" if price_average is not None else "No Super Bock prices yet")
            else:
                st.write("No reviews yet")
            if user["role"] == "customer":
                previous = logic.get_customer_review(user["id"], selected["id"])
                with st.form("review_form"):
                    atmosphere = st.slider("Atmosphere", 1, 5, previous["atmosphere"] if previous else 3)
                    value = st.slider("Value for money", 1, 5, previous["value"] if previous else 3)
                    quality = st.slider("Quality", 1, 5, previous["quality"] if previous else 3)
                    old_price = previous["super_bock_price"] if previous else None
                    price_given = st.checkbox("Add Super Bock price", value=old_price is not None)
                    price = st.number_input("Super Bock price (€)", min_value=0.0, max_value=10.0,
                                            value=float(old_price or 0.5), step=0.1)
                    old_comment = (previous["comment"] or "") if previous else ""
                    comment = st.text_area("Comment", value=old_comment, max_chars=500)
                    submitted = st.form_submit_button("Update review" if previous else "Submit review")
                if submitted:
                    result = logic.submit_app_review(user, selected["id"], atmosphere, value, quality,
                                                     price if price_given else None, comment)
                    if result.success:
                        st.success(result.message)
                        st.rerun()
                    st.error(result.message)
            else:
                st.write("Only customers can leave reviews.")
            for review in logic.get_venue_reviews(selected["id"]):
                st.write(f"{review['username']} · Atmosphere {review['atmosphere']} · Value {review['value']} · Quality {review['quality']}")
                if review["super_bock_price"] is not None:
                    st.write(f"Super Bock: €{review['super_bock_price']:.2f}")
                if review["comment"]:
                    st.text(review["comment"])
                st.caption(logic.format_review_date(review))
            show_venue_community_photos(user, selected["id"])
            st.subheader("Posts")
            with st.expander("Post about this venue", icon=":material/add_a_photo:"):
                show_post_form(user, "venue", venue_id=selected["id"])
            show_post_list(user, logic.get_app_venue_posts(selected["id"], user), "No posts about this venue yet.", "venue")
        if st.button("Back to venues"):
            st.session_state.pop("venue_id", None)
            st.rerun()
    else:
        st.header("Venues")
        venues = logic.get_venues()
        if not venues:
            st.write("No venues are available right now. The venue list could not be loaded.")
        else:
            neighbourhoods = ["All"] + sorted({venue["neighbourhood"] for venue in venues})
            venue_types = ["All"] + sorted({venue["venue_type"] for venue in venues})
            left, middle, right = st.columns(3)
            with left:
                neighbourhood = st.selectbox("Neighbourhood", neighbourhoods)
            with middle:
                venue_type = st.selectbox("Type", venue_types)
            with right:
                shows_football = st.toggle("Shows football")
            sort_labels = {
                "Name (A–Z)": "name", "Best overall score": "overall",
                "Best atmosphere": "atmosphere", "Cheapest Super Bock": "price",
                "Most reviews": "reviews",
            }
            sort_label = st.selectbox("Sort by", list(sort_labels))
            search = st.text_input("Search by name")
            matches = logic.find_app_venues(
                neighbourhood=neighbourhood, venue_type=venue_type,
                shows_football=shows_football, search=search, sort_by=sort_labels[sort_label],
            )
            if not matches:
                st.write("No venues match your filters.")
            for venue in matches:
                name_col, area_col, type_col, button_col = st.columns([3, 2, 2, 1])
                name_col.write(venue["name"])
                summary = logic.get_venue_review_summary(venue["id"])
                name_col.write(f"{summary['overall']:.1f} ★ · {summary['review_count']} reviews" if summary["review_count"] else "No reviews yet")
                area_col.write(venue["neighbourhood"])
                type_col.write(venue["venue_type"])
                if button_col.button("View", key=f"venue-{venue['id']}"):
                    st.session_state.venue_id = venue["id"]
                    st.rerun()
