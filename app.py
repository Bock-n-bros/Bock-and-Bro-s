"""Render account screens and the logged-in venue browser."""

import streamlit as st

import logic


logic.initialize_app_data()
st.title("Bock'n Bros")

saved_user = st.session_state.get("user")
if saved_user is not None and not logic.has_valid_session_user(saved_user):
    st.session_state.pop("user", None)
    st.session_state.pop("venue_id", None)
    st.warning("Your session is out of date. Please log in again.")

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
        selected = logic.get_venue(st.session_state.venue_id)
        if selected is not None:
            st.header(selected["name"])
            st.write(f"Type: {selected['venue_type']}")
            st.write(f"Neighbourhood: {selected['neighbourhood']}")
            st.write(f"Address: {selected['address']}")
            st.write(f"Shows football: {selected['shows_football']}")
            st.write(selected["description"])
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
else:
    login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            result = logic.authenticate_user(username, password)
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
            result = logic.create_account(
                username, password, password_repeat, role_label.lower(), age_confirmed
            )
            if result.success:
                st.success(result.message)
            else:
                st.error(result.message)
