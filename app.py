"""Render account screens and the logged-in venue browser."""

import streamlit as st
import pydeck as pdk
from urllib.parse import quote_plus

import logic
import styles


logic.initialize_app_data()
st.title("Bock'n Bros")


def render_map(venues):
    """Render the filtered Lisbon venue map and selected venue card."""
    st.markdown(styles.MAP_LAYOUT_CSS, unsafe_allow_html=True)
    heading_col, filter_col = st.columns([2, 3], vertical_alignment="center")
    with heading_col:
        st.subheader("Bars in Lisbon")
        st.caption("Tap a dot to see prices and ratings")
    with filter_col:
        minimum_rating = st.segmented_control(
            "Minimum rating", ["All", "3+", "4+", "4.5+"],
            default="All", key="map_rating", label_visibility="collapsed",
            width="stretch",
        )

    try:
        mapbox_token = st.secrets["mapbox_token"]
    except Exception:
        mapbox_token = None

    map_rows = []
    for venue in venues:
        summary = logic.get_venue_review_summary(venue["id"])
        if minimum_rating != "All":
            threshold = float(minimum_rating[:-1])
            if summary["overall"] is None or summary["overall"] < threshold:
                continue
        reviews = logic.get_venue_reviews(venue["id"])
        prices = [review["super_bock_price"] for review in reviews
                  if review["super_bock_price"] is not None]
        price = min(prices) if prices else summary["average_super_bock_price"]
        pin_label = logic.price_label(price, summary["overall"])
        taste_label = f"{summary['quality']:.1f}" if summary["quality"] is not None else "no reviews"
        vibe_label = f"{summary['atmosphere']:.1f}" if summary["atmosphere"] is not None else "no reviews"
        map_rows.append({
            "id": venue["id"], "name": venue["name"],
            "neighbourhood": venue["neighbourhood"],
            "latitude": venue["latitude"], "longitude": venue["longitude"],
            "rating": summary["overall"],
            "taste": taste_label, "vibe": vibe_label,
            "price": price, "pin_label": pin_label,
            "color": logic.marker_color(summary["overall"]),
        })

    if mapbox_token:
        map_provider = "mapbox"
        map_style = logic.map_style_url("Streets")
        api_keys = {"mapbox": mapbox_token}
    else:
        map_provider = "carto"
        map_style = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
        api_keys = {}
        st.caption("Mapbox token not configured; showing the free Positron map style.")

    points = pdk.Layer(
        "ScatterplotLayer", data=map_rows, id="venue-pins", pickable=True,
        get_position="[longitude, latitude]", get_fill_color="color",
        get_line_color=[255, 255, 255], radius_units="pixels", get_radius=7,
        radius_min_pixels=5, radius_max_pixels=10,
        line_width_min_pixels=2, stroked=True, auto_highlight=True,
    )
    labels = pdk.Layer(
        "TextLayer", data=map_rows, id="venue-labels",
        get_position="[longitude, latitude]", get_text="pin_label",
        get_size=14, get_color=[35, 35, 35], get_pixel_offset=[0, -22],
        get_text_anchor="middle", get_alignment_baseline="bottom",
    )
    deck = pdk.Deck(
        layers=[points, labels],
        initial_view_state=pdk.ViewState(latitude=38.7169, longitude=-9.1399, zoom=13),
        map_provider=map_provider, map_style=map_style, api_keys=api_keys,
        tooltip={"text": "{name}\n{neighbourhood}\nPrice: {pin_label}\nTaste avg: {taste}\nVibe avg: {vibe}"},
    )
    with st.container(key="lisbon_map_frame"):
        selection = st.pydeck_chart(
            deck, on_select="rerun", selection_mode="single-object",
            key="venue_map", height=518, width="stretch",
        )
    st.markdown(
        styles.MAP_LEGEND_HTML.format(shown=len(map_rows), total=len(venues)),
        unsafe_allow_html=True,
    )
    selected_objects = selection.selection.get("objects", {}).get("venue-pins", [])
    if selected_objects:
        selected_id = selected_objects[0]["id"]
        selected = next((venue for venue in venues if venue["id"] == selected_id), None)
        if selected:
            st.subheader(selected["name"])
            st.write(f"{selected['neighbourhood']} · {selected['address']}")
            maps_query = quote_plus(f"{selected['name']} {selected['address']}")
            directions_query = quote_plus(
                f"{selected['latitude']},{selected['longitude']}"
            )
            button_col, directions_col = st.columns(2)
            button_col.link_button(
                "Open in Google Maps",
                f"https://www.google.com/maps/search/?api=1&query={maps_query}",
            )
            directions_col.link_button(
                "Walking directions",
                "https://www.google.com/maps/dir/?api=1&destination="
                f"{directions_query}&travelmode=walking",
            )

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
        venues = logic.get_venues()
        map_tab, venues_tab = st.tabs(["Map", "Venues"])
        with map_tab:
            if not venues:
                st.write("No venues are available right now. The venue list could not be loaded.")
            else:
                render_map(venues)
        with venues_tab:
            st.header("Venues")
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
