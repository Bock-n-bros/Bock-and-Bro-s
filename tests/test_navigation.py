"""Tests for shareable navigation state."""

import ast
from pathlib import Path

import logic

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_detail_query_builds_and_parses_ids_for_supported_pages():
    for detail_type, key in (("venue", "venue"), ("profile", "user"),
                             ("post", "post"), ("chat", "chat")):
        query = logic.build_detail_query(detail_type, 12, "Feed")
        assert query[key] == "12"
        assert query["from"] == "Feed"
        assert logic.parse_detail_id(query, detail_type) == 12


def test_detail_query_rejects_invalid_ids_and_unknown_types():
    assert logic.parse_detail_id({"venue": "abc"}, "venue") is None
    assert logic.parse_detail_id({"venue": "0"}, "venue") is None
    assert logic.parse_detail_id({}, "venue") is None
    assert logic.parse_detail_id({"other": "12"}, "unknown") is None
    assert logic.parse_detail_id({"venue": "999999"}, "venue") == 999999


def test_feed_venue_and_profile_links_use_lowercase_feed_source():
    assert logic.venue_link_params(12, "Feed") == {"venue": "12", "from": "feed"}
    assert logic.profile_link_params(5, "Feed") == {"user": "5", "from": "feed"}
    assert logic.parse_return_page({"from": "feed"}, {"Feed", "Venues"}, "Venues") == "Feed"


def test_map_pin_selection_only_sets_a_preview_until_view_bar_is_clicked():
    assert logic.map_preview_selection([{"id": 7}], {7, 8}) == 7
    assert logic.map_preview_selection([], {7, 8}, 7) == 7
    assert logic.map_preview_selection([{"id": 99}], {7, 8}, 7) == 7
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    map_source = ast.get_source_segment(source, functions["render_map"])
    assert "logic.map_preview_selection" in map_source
    assert "map_preview_id" in map_source
    assert "st.query_params" not in map_source
    card_source = ast.get_source_segment(source, functions["render_venue_card"])
    assert '"View bar"' in card_source and "on_click=open_venue" in card_source
    assert "Directions ↗" in card_source


def test_detail_query_builder_rejects_invalid_target():
    try:
        logic.build_detail_query("venue", "abc")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid ids must be refused")


def test_return_page_uses_valid_origin_and_falls_back_for_invalid_origin():
    allowed = {"Feed", "Venues", "People", "Messages", "Profile", "Notifications"}
    assert logic.parse_return_page({"from": "People"}, allowed, "Feed") == "People"
    assert logic.parse_return_page({"from": "notifications"}, allowed, "Feed") == "Notifications"
    assert logic.parse_return_page({"from": "../../admin"}, allowed, "Feed") == "Feed"


def test_app_uses_sidebar_navigation_with_all_five_icon_pages_in_order():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    pages = next(node for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "NAV_PAGES"
                         for target in node.targets))
    configured = {}
    for key, value in zip(pages.value.keys, pages.value.values):
        title = next(keyword.value.value for keyword in value.keywords if keyword.arg == "title")
        icon = next(keyword.value.value for keyword in value.keywords if keyword.arg == "icon")
        configured[key.value] = (title, icon)
    assert configured == {
        "Feed": ("Feed", "🏠"), "Venues": ("Venues", "🗺️"),
        "People": ("People", "👥"), "Messages": ("Messages", "💬"),
        "Profile": ("Profile", "👤"),
    }
    assert '[*NAV_PAGES.values(), NOTIFICATIONS_PAGE], position="sidebar"' in source
    assert 'url_path="notifications", visibility="hidden"' in source
    assert "show_alert_bell(user)" in source
    assert "logic.take_app_new_alerts(user)" in source
    assert "logic.mark_app_alerts_read(user)" in source
    sidebar_start = source.index("with st.sidebar:", source.index("if logic.can_view_venues(user):"))
    sidebar_end = source.index("navigation.run()", sidebar_start)
    sidebar = source[sidebar_start:sidebar_end]
    assert source.index("st.logo(") < sidebar_start
    assert sidebar.index("show_avatar(user, 48)") < sidebar.index('st.write(user["username"])')
    assert sidebar.index('st.write(user["username"])') < sidebar.index('st.caption(user["role"].title())')
    assert sidebar.index('st.caption(user["role"].title())') < sidebar.index("st.navigation(")
    assert sidebar.index("st.navigation(") < sidebar.index('st.button("Log out"')
    style_source = (APP_PATH.parent / "styles.py").read_text(encoding="utf-8")
    assert '[data-testid="stHeader"]' not in style_source


def test_each_detail_route_handles_unknown_ids_with_not_found_and_back():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in ("run_feed_page", "run_venues_page", "run_people_page", "run_messages_page", "run_profile_page"):
        function_source = ast.get_source_segment(source, functions[name])
        assert "parse_detail_id" in function_source
        assert "render_not_found" in function_source
    assert "on_click=go_back_from_detail" in source
    assert "st.query_params.clear()" in source


def test_social_actions_show_toast_feedback_and_reviewers_open_profiles():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in ("render_review_form", "render_venue_card", "show_profile",
                 "show_post", "show_open_conversation"):
        function_source = ast.get_source_segment(source, functions[name])
        assert "st.toast" in function_source
    assert "on_click=open_profile" in ast.get_source_segment(source, functions["render_venue_card"])


def test_post_header_uses_inline_link_helpers_and_keeps_time_below():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    post_source = ast.get_source_segment(source, functions["show_post"])
    venue_open_source = ast.get_source_segment(source, functions["open_venue"])
    profile_open_source = ast.get_source_segment(source, functions["open_profile"])
    assert "logic.profile_link_params(post[\"user_id\"], \"Feed\")" in post_source
    assert "logic.venue_link_params(post[\"venue_id\"], \"Feed\")" in post_source
    assert "logic.venue_link_params" in venue_open_source
    assert "logic.profile_link_params" in profile_open_source
    assert "detail_text_link" in post_source
    assert "header_col.caption(logic.format_post_time(post[\"created_at\"]))" in post_source
    style_source = (APP_PATH.parent / "styles.py").read_text(encoding="utf-8")
    assert ".detail-text-link:hover" in style_source
    assert "text-decoration: underline" in style_source


def test_back_context_restores_venue_query_and_map_preview_state():
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    open_source = ast.get_source_segment(source, functions["open_detail"])
    back_source = ast.get_source_segment(source, functions["go_back_from_detail"])
    venue_source = ast.get_source_segment(source, functions["run_venues_page"])
    list_source = ast.get_source_segment(source, functions["show_venue_list"])
    assert 'history.append({"page": source, "query": dict(st.query_params)})' in open_source
    assert 'st.query_params.update(previous["query"])' in back_source
    assert "st.session_state.map_preview_id = venue_id" in venue_source
    assert 'key="venue_search"' in list_source
    assert 'key="venue_neighbourhood"' in list_source
    assert 'key="venue_type"' in list_source


