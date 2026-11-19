"""Tests for shared venue card data and its screen wiring."""

import ast
from datetime import datetime, timezone
from pathlib import Path

import logic


def test_cheapest_review_price_uses_only_logged_prices():
    reviews = [
        {"super_bock_price": None},
        {"super_bock_price": 2.20},
        {"super_bock_price": 1.80},
    ]
    assert logic.cheapest_review_price(reviews) == 1.80
    assert logic.cheapest_review_price([{"super_bock_price": None}]) is None


def test_venue_card_summary_is_one_line_and_handles_missing_data():
    summary = {"overall": 4.2, "review_count": 12}
    assert logic.format_venue_card_summary(summary, 1.8) == (
        "★ 4.2 · 12 reviews · from €1.80"
    )
    assert logic.format_venue_card_summary(summary, None) == (
        "★ 4.2 · 12 reviews · no price logged"
    )
    assert logic.format_venue_card_summary({"overall": None, "review_count": 0}, None) == (
        "No reviews yet"
    )


def test_review_rating_is_mean_of_the_three_scores():
    review = {"atmosphere": 5, "value": 4, "quality": 4}
    assert logic.review_rating(review) == 4.3


def test_relative_review_time_uses_a_fixed_clock():
    now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    assert logic.format_time_ago("2026-11-19T11:58:00+00:00", now) == "2 minutes ago"
    assert logic.format_time_ago("2026-11-19T10:00:00+00:00", now) == "2 hours ago"


def test_review_preview_shows_only_three_newest_in_input_order():
    now = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    reviews = [
        {"username": f"User {index}", "atmosphere": 5, "value": 4, "quality": 4,
         "comment": "x" * 160, "created_at": f"2026-11-19T11:{59-index:02}:00+00:00"}
        for index in range(4)
    ]

    preview = logic.review_preview(reviews, now)

    assert [item["username"] for item in preview] == ["User 0", "User 1", "User 2"]
    assert preview[0]["rating"] == 4.3
    assert len(preview[0]["comment"]) == 140
    assert preview[0]["time_ago"] == "1 minute ago"


def test_map_and_full_venue_page_call_the_shared_card_renderer():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }

    def card_calls(node):
        return [call for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "render_venue_card"]

    map_calls = card_calls(functions["render_map"])
    full_calls = [call for call in card_calls(tree)
                  if any(keyword.arg == "compact"
                         and isinstance(keyword.value, ast.Constant)
                         and keyword.value.value is False
                         for keyword in call.keywords)]

    assert len(map_calls) == 1
    assert any(keyword.arg == "compact"
               and isinstance(keyword.value, ast.Constant)
               and keyword.value.value is True
               for keyword in map_calls[0].keywords)
    assert len(full_calls) == 1


def test_compact_card_wires_review_follow_navigation_and_map_actions():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    card = functions["render_venue_card"]
    calls = [node for node in ast.walk(card) if isinstance(node, ast.Call)]

    def button_call(label):
        return next(call for call in calls
                    if isinstance(call.func, ast.Attribute)
                    and call.func.attr == "button"
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                    and call.args[0].value == label)

    write_review = button_call("Write a review")
    see_reviews = button_call("See all reviews")
    assert any(keyword.arg == "on_click" and isinstance(keyword.value, ast.Name)
               and keyword.value.id == "open_review_form"
               for keyword in write_review.keywords)
    assert any(keyword.arg == "on_click" and isinstance(keyword.value, ast.Name)
               and keyword.value.id == "open_venue"
               for keyword in see_reviews.keywords)
    assert any(isinstance(call.func, ast.Attribute)
               and call.func.attr == "follow_app_venue"
               and len(call.args) == 2
               and isinstance(call.args[1], ast.Name)
               and call.args[1].id == "venue_id"
               for call in calls)
    link_labels = {
        call.args[0].value for call in calls
        if isinstance(call.func, ast.Attribute)
        and call.func.attr == "link_button"
        and call.args and isinstance(call.args[0], ast.Constant)
    }
    assert link_labels == {"Open in Google Maps", "Walking directions"}


def test_map_compact_card_is_inside_a_bordered_container():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    render_map = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == "render_map")
    card_contexts = [node for node in ast.walk(render_map)
                     if isinstance(node, ast.With)
                     and any(isinstance(item.context_expr, ast.Call)
                             and isinstance(item.context_expr.func, ast.Attribute)
                             and item.context_expr.func.attr == "container"
                             and any(keyword.arg == "border"
                                     and isinstance(keyword.value, ast.Constant)
                                     and keyword.value.value is True
                                     for keyword in item.context_expr.keywords)
                             for item in node.items)
                     and any(isinstance(call, ast.Call)
                             and isinstance(call.func, ast.Name)
                             and call.func.id == "render_venue_card"
                             for statement in node.body for call in ast.walk(statement))]

    assert len(card_contexts) == 1


def test_weather_lines_share_the_muted_container():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    render_weather = next(node for node in tree.body
                          if isinstance(node, ast.FunctionDef)
                          and node.name == "render_venue_weather")
    weather_containers = [node for node in ast.walk(render_weather)
                          if isinstance(node, ast.With)
                          and any(isinstance(item.context_expr, ast.Call)
                                  and isinstance(item.context_expr.func, ast.Attribute)
                                  and item.context_expr.func.attr == "container"
                                  for item in node.items)]

    assert len(weather_containers) == 1
    captions = [call for statement in weather_containers[0].body
                for call in ast.walk(statement)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "caption"]
    assert len(captions) >= 2


def test_card_actions_use_compact_primary_row_and_tertiary_links():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    card = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "render_venue_card")
    calls = [node for node in ast.walk(card) if isinstance(node, ast.Call)]
    write_review = next(call for call in calls
                        if isinstance(call.func, ast.Attribute)
                        and call.func.attr == "button"
                        and call.args and isinstance(call.args[0], ast.Constant)
                        and call.args[0].value == "Write a review")
    assert any(keyword.arg == "type" and isinstance(keyword.value, ast.Constant)
               and keyword.value.value == "primary"
               for keyword in write_review.keywords)
    link_types = [keyword.value.value for call in calls
                  if isinstance(call.func, ast.Attribute)
                  and call.func.attr == "link_button"
                  for keyword in call.keywords
                  if keyword.arg == "type" and isinstance(keyword.value, ast.Constant)]
    assert link_types == ["tertiary", "tertiary"]
