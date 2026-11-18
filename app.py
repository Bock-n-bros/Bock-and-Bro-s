"""Render account screens and the logged-in venue browser."""

import streamlit as st

import logic


logic.initialize_app_data()
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

if logic.can_view_venues(user):
    with st.sidebar:
        st.write(user["username"])
        st.write(f"Role: {user['role'].title()}")
        if st.button("Log out"):
            st.session_state.pop("venue_id", None)
            st.logout()

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
