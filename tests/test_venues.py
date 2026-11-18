"""Tests for loading, storing, and finding Lisbon venues."""

import csv

import pytest

import db
import logic


FIELDS = [
    "name",
    "neighbourhood",
    "address",
    "venue_type",
    "shows_football",
    "latitude",
    "longitude",
    "description",
]


@pytest.fixture
def venue_db(tmp_path, monkeypatch):
    """Use an isolated database for every venue test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "venues.db")
    db.init_db()
    return db


def write_csv(path, rows, encoding="utf-8"):
    """Write venue rows to a test-owned CSV file."""
    with path.open("w", encoding=encoding, newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def venue(default_name="Demo Super Bar", **changes):
    """Return a valid venue with selected fields changed."""
    row = {
        "name": default_name,
        "neighbourhood": "Bairro Alto",
        "address": "1 Test Street",
        "venue_type": "bar",
        "shows_football": "yes",
        "latitude": "38.72",
        "longitude": "-9.14",
        "description": "A fictional test venue.",
    }
    row.update(changes)
    return row


def test_loads_valid_rows_from_csv(venue_db, tmp_path):
    csv_path = write_csv(tmp_path / "venues.csv", [venue(), venue("Demo Other")])
    assert logic.load_venues(venue_db, csv_path) == 2
    assert venue_db.count_venues() == 2


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"name": ""}, "name"),
        ({"neighbourhood": ""}, "neighbourhood"),
        ({"address": ""}, "address"),
        ({"venue_type": "restaurant"}, "venue_type"),
        ({"shows_football": "sometimes"}, "shows_football"),
        ({"latitude": "not-a-number"}, "latitude"),
        ({"longitude": "not-a-number"}, "longitude"),
    ],
)
def test_invalid_csv_rows_are_skipped_and_reported(venue_db, tmp_path, changes, reason, capsys):
    csv_path = write_csv(tmp_path / "venues.csv", [venue(), venue("Demo Invalid", **changes)])
    assert logic.load_venues(venue_db, csv_path) == 1
    output = capsys.readouterr().out
    assert "row 3" in output.lower()
    assert reason in output.lower()
    assert venue_db.count_venues() == 1


@pytest.mark.parametrize(
    ("field", "boundary"),
    [
        ("latitude", "38.68"),
        ("latitude", "38.80"),
        ("longitude", "-9.25"),
        ("longitude", "-9.08"),
    ],
)
def test_accepts_lisbon_coordinate_limits(venue_db, tmp_path, field, boundary):
    csv_path = write_csv(tmp_path / "venues.csv", [venue(**{field: boundary})])
    assert logic.load_venues(venue_db, csv_path) == 1


@pytest.mark.parametrize(
    ("field", "outside"),
    [
        ("latitude", "38.6799"),
        ("latitude", "38.8001"),
        ("longitude", "-9.2501"),
        ("longitude", "-9.0799"),
    ],
)
def test_rejects_coordinates_just_outside_lisbon_limits(venue_db, tmp_path, field, outside):
    csv_path = write_csv(tmp_path / "venues.csv", [venue(**{field: outside})])
    assert logic.load_venues(venue_db, csv_path) == 0


def test_loads_missing_rows_into_database_with_existing_venues(venue_db, tmp_path):
    existing_id = venue_db.insert_venue(venue())
    csv_path = write_csv(tmp_path / "venues.csv", [venue("Demo Super Bar"), venue("Demo Second")])
    assert logic.load_venues(venue_db, csv_path) == 1
    assert venue_db.count_venues() == 2
    assert venue_db.get_venue_by_id(existing_id)["name"] == "Demo Super Bar"


def test_skips_venue_names_that_match_case_insensitively(venue_db, tmp_path):
    existing_id = venue_db.insert_venue(venue("Pensão Amor"))
    csv_path = write_csv(tmp_path / "venues.csv", [venue("PENSÃO AMOR"), venue("New Bar")])
    assert logic.load_venues(venue_db, csv_path) == 1
    assert venue_db.count_venues() == 2
    assert venue_db.get_venue_by_id(existing_id)["name"] == "Pensão Amor"


def test_seeding_preserves_reviews_for_existing_venue(venue_db, tmp_path):
    venue_id = venue_db.insert_venue(venue("Pensão Amor"))
    user_id = venue_db.create_user("reviewer", "not-a-real-password-hash", "customer")
    values = {
        "atmosphere": 5, "value": 4, "quality": 5,
        "super_bock_price": 2.5, "comment": "Keep this review",
    }
    venue_db.save_review(venue_id, user_id, values, now="2026-11-18T12:00:00+00:00")
    csv_path = write_csv(tmp_path / "venues.csv", [venue("PENSÃO AMOR"), venue("New Bar")])

    assert logic.load_venues(venue_db, csv_path) == 1
    review = venue_db.get_user_review(user_id, venue_id)
    assert review["comment"] == "Keep this review"
    assert venue_db.count_reviews(venue_id) == 1


def test_seed_csv_contains_more_lisbon_venues():
    from pathlib import Path

    csv_path = Path(__file__).resolve().parents[1] / "data" / "venues.csv"
    rows, errors = logic.validate_venues_csv(csv_path)
    assert errors == []
    assert len(rows) >= 20
    assert {row["neighbourhood"] for row in rows} >= {
        "Bairro Alto", "Cais do Sodré", "Chiado", "Príncipe Real",
        "Alfama", "Graça", "Intendente", "Santos",
    }


def test_loads_valid_rows_when_another_row_is_invalid(venue_db, tmp_path, capsys):
    csv_path = write_csv(tmp_path / "venues.csv", [venue(), venue("Demo Bad", latitude="91")])
    assert logic.load_venues(venue_db, csv_path) == 1
    assert venue_db.count_venues() == 1
    assert "row 3" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("contents", [None, ""])
def test_missing_or_empty_csv_returns_zero_and_clear_message(venue_db, tmp_path, contents, capsys):
    csv_path = tmp_path / "missing.csv"
    if contents is not None:
        csv_path.write_text(contents, encoding="utf-8")
    assert logic.load_venues(venue_db, csv_path) == 0
    message = capsys.readouterr().out.lower()
    assert "csv" in message
    assert "empty" in message or "not found" in message or "no rows" in message
    assert venue_db.count_venues() == 0


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_loads_portuguese_characters_from_utf8_csv(venue_db, tmp_path, encoding):
    csv_path = write_csv(
        tmp_path / "venues.csv",
        [venue("Demo Café", neighbourhood="Cais do Sodré", venue_type="café")],
        encoding=encoding,
    )
    assert logic.load_venues(venue_db, csv_path) == 1
    stored = venue_db.get_all_venues()[0]
    assert stored["name"] == "Demo Café"
    assert stored["neighbourhood"] == "Cais do Sodré"
    assert stored["venue_type"] == "café"


def test_real_venues_csv_is_valid():
    """Validate the committed data file without opening a database."""
    from pathlib import Path

    csv_path = Path(__file__).resolve().parents[1] / "data" / "venues.csv"
    rows, errors = logic.validate_venues_csv(csv_path)
    assert rows
    assert errors == []


def test_filters_by_neighbourhood(venue_db):
    venue_db.insert_venue(venue())
    venue_db.insert_venue(venue("Demo Chiado", neighbourhood="Chiado"))
    assert [v["name"] for v in logic.find_venues(venue_db, neighbourhood="Chiado")] == ["Demo Chiado"]
    assert len(logic.find_venues(venue_db, neighbourhood="All")) == 2


def test_filters_by_venue_type(venue_db):
    venue_db.insert_venue(venue())
    venue_db.insert_venue(venue("Demo Cafe", venue_type="café"))
    assert [v["name"] for v in logic.find_venues(venue_db, venue_type="café")] == ["Demo Cafe"]
    assert len(logic.find_venues(venue_db, venue_type="All")) == 2


def test_filters_by_shows_football_toggle(venue_db):
    venue_db.insert_venue(venue())
    venue_db.insert_venue(venue("Demo Quiet", shows_football="no"))
    assert [v["name"] for v in logic.find_venues(venue_db, shows_football=True)] == ["Demo Super Bar"]
    assert len(logic.find_venues(venue_db, shows_football=False)) == 2


@pytest.mark.parametrize("query", ["super", "SUPER", "SuPeR"])
def test_search_is_case_insensitive_partial_match(venue_db, query):
    venue_db.insert_venue(venue())
    venue_db.insert_venue(venue("Demo Quiet Bar"))
    assert [v["name"] for v in logic.find_venues(venue_db, search=query)] == ["Demo Super Bar"]


def test_combines_filters_and_search(venue_db):
    venue_db.insert_venue(venue())
    venue_db.insert_venue(venue("Demo Super Pub", venue_type="pub"))
    venue_db.insert_venue(venue("Demo Super Chiado", neighbourhood="Chiado"))
    result = logic.find_venues(
        venue_db, neighbourhood="Bairro Alto", venue_type="bar", shows_football=True, search="super"
    )
    assert [v["name"] for v in result] == ["Demo Super Bar"]


def test_sorts_venues_alphabetically(venue_db):
    venue_db.insert_venue(venue("Demo Zulu"))
    venue_db.insert_venue(venue("Demo Alpha"))
    assert [v["name"] for v in logic.find_venues(venue_db)] == ["Demo Alpha", "Demo Zulu"]


def test_empty_search_returns_all_venues(venue_db):
    venue_db.insert_venue(venue("Demo Zulu"))
    venue_db.insert_venue(venue("Demo Alpha"))
    assert len(logic.find_venues(venue_db, search="")) == 2


def test_no_matches_returns_empty_list(venue_db):
    venue_db.insert_venue(venue())
    assert logic.find_venues(venue_db, search="nonexistent") == []


def test_access_allows_logged_in_roles_and_refuses_logged_out_user():
    assert not logic.can_view_venues(None)
    assert logic.can_view_venues({"username": "Customer", "role": "customer"})
    assert logic.can_view_venues({"username": "Business", "role": "business"})


def test_creates_venues_table_on_initialization(venue_db):
    assert venue_db.count_venues() == 0


def test_inserts_and_counts_venues(venue_db):
    venue_db.insert_venue(venue())
    assert venue_db.count_venues() == 1


def test_fetches_all_venues(venue_db):
    venue_db.insert_venue(venue())
    assert venue_db.get_all_venues()[0]["name"] == "Demo Super Bar"


def test_fetches_venue_by_id_and_returns_none_for_unknown_id(venue_db):
    venue_id = venue_db.insert_venue(venue())
    assert venue_db.get_venue_by_id(venue_id)["name"] == "Demo Super Bar"
    assert venue_db.get_venue_by_id(99999) is None
