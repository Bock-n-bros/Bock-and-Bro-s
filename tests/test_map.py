"""Tests for map display rules."""

import logic


def test_marker_color_at_3_is_amber():
    assert logic.marker_color(3.0) == {
        "fill": [217, 150, 15], "line": [217, 150, 15]
    }


def test_marker_color_at_4_is_green():
    assert logic.marker_color(4.0) == {
        "fill": [46, 139, 87], "line": [46, 139, 87]
    }


def test_marker_color_below_3_is_red():
    assert logic.marker_color(2.9) == {
        "fill": [196, 52, 44], "line": [196, 52, 44]
    }


def test_marker_color_without_reviews_is_white_with_amber_outline():
    assert logic.marker_color(None) == {
        "fill": [255, 255, 255], "line": [217, 150, 15]
    }


def test_map_rows_keep_fill_and_line_colors_for_all_rating_states():
    venues = [
        {"id": 1, "name": "Green", "neighbourhood": "Baixa", "latitude": 38.7, "longitude": -9.1},
        {"id": 2, "name": "Red", "neighbourhood": "Baixa", "latitude": 38.7, "longitude": -9.1},
        {"id": 3, "name": "Unrated", "neighbourhood": "Baixa", "latitude": 38.7, "longitude": -9.1},
    ]
    summaries = {
        1: {"overall": 4.5, "quality": 4.5, "atmosphere": 4.5, "lowest_super_bock_price": None},
        2: {"overall": 2.0, "quality": 2.0, "atmosphere": 2.0, "lowest_super_bock_price": None},
        3: {"overall": None, "quality": None, "atmosphere": None, "lowest_super_bock_price": None},
    }

    rows = logic.build_map_rows(venues, summaries)

    assert [row["fill"] for row in rows] == [
        [46, 139, 87], [196, 52, 44], [255, 255, 255]
    ]
    assert [row["line"] for row in rows] == [
        [46, 139, 87], [196, 52, 44], [217, 150, 15]
    ]


def test_map_style_url_returns_known_styles():
    assert logic.map_style_url("Light") == "mapbox://styles/mapbox/light-v11"
    assert logic.map_style_url("Streets") == "mapbox://styles/mapbox/streets-v12"
    assert logic.map_style_url("Dark") == "mapbox://styles/mapbox/dark-v11"
    assert logic.map_style_url("Satellite") == "mapbox://styles/mapbox/satellite-streets-v12"


def test_unknown_map_style_uses_light():
    assert logic.map_style_url("Unknown") == logic.map_style_url("Light")


def test_price_label_prefers_available_price():
    assert logic.price_label(1.75, 4.2) == "€1.75"


def test_price_label_falls_back_to_rating_or_no_reviews():
    assert logic.price_label(None, 4.2) == "4.2 ★"
    assert logic.price_label(None, None) == "no reviews"
