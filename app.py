"""Render account screens and the logged-in venue browser."""

import streamlit as st

import db
import logic
import seed


db.init_db()
seed.load_demo_venues()
st.title("Bock'n Bros")

if logic.can_view_venues(st.session_state.get("user")):
    user = st.session_state.user
    with st.sidebar:
        st.write(user["username"])
        st.write(f"Role: {user['role'].title()}")
        if st.button("Log out"):
            del st.session_state["user"]
            st.session_state.pop("venue_id", None)
            st.rerun()

    if st.session_state.get("venue_id") is not None:
        selected = db.get_venue_by_id(st.session_state.venue_id)
        if selected is not None:
            st.header(selected["name"])
            st.write(f"Type: {selected['venue_type']}")
            st.write(f"Neighbourhood: {selected['neighbourhood']}")
            st.write(f"Address: {selected['address']}")
            st.write(f"Shows football: {selected['shows_football']}")
            st.write(selected["description"])
        if st.button("Back to venues"):
            st.session_state.pop("venue_id", None)
            st.rerun()
    else:
        st.header("Venues")
        venues = db.get_all_venues()
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
            search = st.text_input("Search by name")
            matches = logic.find_venues(
                db, neighbourhood=neighbourhood, venue_type=venue_type,
                shows_football=shows_football, search=search,
            )
            if not matches:
                st.write("No venues match your filters.")
            for venue in matches:
                name_col, area_col, type_col, button_col = st.columns([3, 2, 2, 1])
                name_col.write(venue["name"])
                area_col.write(venue["neighbourhood"])
                type_col.write(venue["venue_type"])
                if button_col.button("View", key=f"venue-{venue['id']}"):
                    st.session_state.venue_id = venue["id"]
                    st.rerun()
else:
    login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            result = logic.login_user(db, username, password)
            if result.success:
                st.session_state.user = result.user
                st.rerun()
            st.error(result.message)
    with signup_tab:
        with st.form("signup_form"):
            username = st.text_input("Username", key="signup_username")
            password = st.text_input("Password", type="password", key="signup_password")
            password_repeat = st.text_input("Repeat password", type="password", key="signup_repeat")
            role_label = st.radio("Account type", ["Customer", "Business"])
            age_confirmed = st.checkbox("I confirm I am 18 or older")
            submitted = st.form_submit_button("Sign up")
        if submitted:
            result = logic.register_user(
                db, username, password, password_repeat, role_label.lower(), age_confirmed
            )
            if result.success:
                st.success(result.message)
            else:
                st.error(result.message)
