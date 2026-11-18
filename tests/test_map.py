"""Tests for map display rules."""

import logic


def test_marker_color_uses_rating_boundaries():
    assert logic.marker_color(2.9) == [220, 53, 69]
    assert logic.marker_color(3) == [245, 166, 35]
    assert logic.marker_color(3.9) == [245, 166, 35]
    assert logic.marker_color(4) == [46, 160, 67]


def test_marker_color_is_grey_without_reviews():
    assert logic.marker_color(None) == [128, 128, 128]


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
