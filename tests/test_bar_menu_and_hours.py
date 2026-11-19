"""Tests for a bar account's own venue, its menu and its opening hours."""

from datetime import time

import pytest

import db
import logic


@pytest.fixture
def bar_db(tmp_path, monkeypatch):
    """Use an isolated database for every bar management test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "bars.db")
    monkeypatch.setattr(db, "_database_url", lambda: None)
    db.init_db()
    return db


def make_user(database, username, role="customer"):
    """Create a profile and return the public user dictionary."""
    database.create_user(f"sub-{username}", f"{username}@example.com", username, role)
    return logic.find_google_user(database, f"sub-{username}")


def make_venue(database, name="Park Bar"):
    """Create a minimal venue and return its id."""
    return database.insert_venue({
        "name": name, "neighbourhood": "Bairro Alto", "address": "1 Test Street",
        "venue_type": "bar", "shows_football": "yes", "latitude": 38.72,
        "longitude": -9.14, "description": "Test venue",
    })


def owned_bar(database, username="owner"):
    """Create a bar account that already manages a venue."""
    owner = make_user(database, username, role="business")
    venue_id = make_venue(database, f"{username} bar")
    assert logic.claim_venue(database, owner, venue_id).success
    return owner, venue_id


# --- claiming a venue -------------------------------------------------------

def test_a_bar_account_can_claim_a_venue(bar_db):
    owner = make_user(bar_db, "owner", role="business")
    venue_id = make_venue(bar_db)

    result = logic.claim_venue(bar_db, owner, venue_id)

    assert result.success
    assert logic.get_owned_venue(bar_db, owner)["id"] == venue_id
    assert logic.can_manage_venue(bar_db, owner, venue_id)


def test_a_customer_cannot_claim_a_venue(bar_db):
    customer = make_user(bar_db, "cato")
    venue_id = make_venue(bar_db)

    result = logic.claim_venue(bar_db, customer, venue_id)

    assert not result.success
    assert logic.get_venue_manager_id(bar_db, venue_id) is None


def test_a_logged_out_visitor_cannot_claim_a_venue(bar_db):
    venue_id = make_venue(bar_db)

    assert not logic.claim_venue(bar_db, None, venue_id).success


def test_a_venue_cannot_be_claimed_twice(bar_db):
    first, venue_id = owned_bar(bar_db, "first")
    second = make_user(bar_db, "second", role="business")

    result = logic.claim_venue(bar_db, second, venue_id)

    assert not result.success
    assert logic.get_venue_manager_id(bar_db, venue_id) == first["id"]


def test_one_account_cannot_manage_two_venues(bar_db):
    owner, _ = owned_bar(bar_db)
    other_venue = make_venue(bar_db, "Second Bar")

    result = logic.claim_venue(bar_db, owner, other_venue)

    assert not result.success
    assert logic.get_venue_manager_id(bar_db, other_venue) is None


def test_releasing_a_venue_frees_it_for_another_account(bar_db):
    owner, venue_id = owned_bar(bar_db, "first")
    assert logic.release_venue(bar_db, owner).success
    second = make_user(bar_db, "second", role="business")

    assert logic.claim_venue(bar_db, second, venue_id).success
    assert logic.get_venue_manager_id(bar_db, venue_id) == second["id"]


def test_claiming_an_unknown_venue_is_refused(bar_db):
    owner = make_user(bar_db, "owner", role="business")

    assert not logic.claim_venue(bar_db, owner, 999).success


# --- the menu ---------------------------------------------------------------

def test_the_owner_can_add_items_and_they_keep_their_order(bar_db):
    owner, venue_id = owned_bar(bar_db)

    logic.add_menu_item(bar_db, owner, venue_id, "Super Bock 0.33", 2.50)
    logic.add_menu_item(bar_db, owner, venue_id, "Bifana", 4.00)

    assert [item["name"] for item in logic.get_menu(bar_db, venue_id)] == [
        "Super Bock 0.33", "Bifana"]


def test_another_bar_cannot_change_someone_elses_menu(bar_db):
    owner, venue_id = owned_bar(bar_db, "first")
    intruder, _ = owned_bar(bar_db, "second")

    result = logic.add_menu_item(bar_db, intruder, venue_id, "Sneaky beer", 1.00)

    assert not result.success
    assert logic.get_menu(bar_db, venue_id) == []


def test_a_customer_cannot_change_a_menu(bar_db):
    _, venue_id = owned_bar(bar_db)
    customer = make_user(bar_db, "cato")

    assert not logic.add_menu_item(bar_db, customer, venue_id, "Free beer", 0.10).success


def test_the_owner_can_update_and_remove_an_item(bar_db):
    owner, venue_id = owned_bar(bar_db)
    item_id = logic.add_menu_item(bar_db, owner, venue_id, "Imperial", 1.80).item_id

    assert logic.update_menu_item(bar_db, owner, item_id, "Imperial 0.20", 2.00).success
    changed = logic.get_menu(bar_db, venue_id)[0]
    assert changed["name"] == "Imperial 0.20"
    assert changed["price"] == pytest.approx(2.00)

    assert logic.delete_menu_item(bar_db, owner, item_id).success
    assert logic.get_menu(bar_db, venue_id) == []


def test_another_bar_cannot_update_or_remove_an_item(bar_db):
    owner, venue_id = owned_bar(bar_db, "first")
    intruder, _ = owned_bar(bar_db, "second")
    item_id = logic.add_menu_item(bar_db, owner, venue_id, "Imperial", 1.80).item_id

    assert not logic.update_menu_item(bar_db, intruder, item_id, "Hacked", 0.10).success
    assert not logic.delete_menu_item(bar_db, intruder, item_id).success
    assert logic.get_menu(bar_db, venue_id)[0]["name"] == "Imperial"


@pytest.mark.parametrize("name", ["", "   ", None])
def test_an_item_without_a_name_is_refused(bar_db, name):
    owner, venue_id = owned_bar(bar_db)

    assert not logic.add_menu_item(bar_db, owner, venue_id, name, 2.00).success
    assert logic.get_menu(bar_db, venue_id) == []


def test_name_length_is_checked_at_its_boundary(bar_db):
    owner, venue_id = owned_bar(bar_db)
    longest = "b" * logic.MAX_MENU_NAME_LENGTH

    assert logic.add_menu_item(bar_db, owner, venue_id, longest, 2.00).success
    assert not logic.add_menu_item(bar_db, owner, venue_id, longest + "b", 2.00).success


def test_the_name_is_trimmed(bar_db):
    owner, venue_id = owned_bar(bar_db)

    logic.add_menu_item(bar_db, owner, venue_id, "  Vinho Verde  ", 3.00)

    assert logic.get_menu(bar_db, venue_id)[0]["name"] == "Vinho Verde"


@pytest.mark.parametrize("price", [0.09, 500.01, -1, "2.50", None, True])
def test_prices_outside_the_allowed_range_are_refused(bar_db, price):
    owner, venue_id = owned_bar(bar_db)

    assert not logic.add_menu_item(bar_db, owner, venue_id, "Beer", price).success


@pytest.mark.parametrize("price", [0.10, 500.00, 2.5])
def test_prices_on_and_inside_the_boundary_are_allowed(bar_db, price):
    owner, venue_id = owned_bar(bar_db)

    assert logic.add_menu_item(bar_db, owner, venue_id, "Beer", price).success


def test_a_menu_cannot_grow_past_the_maximum(bar_db):
    owner, venue_id = owned_bar(bar_db)
    for number in range(logic.MAX_MENU_ITEMS):
        assert logic.add_menu_item(bar_db, owner, venue_id, f"Item {number}", 2.00).success

    result = logic.add_menu_item(bar_db, owner, venue_id, "One too many", 2.00)

    assert not result.success
    assert len(logic.get_menu(bar_db, venue_id)) == logic.MAX_MENU_ITEMS


def test_changing_an_unknown_item_is_refused(bar_db):
    owner, _ = owned_bar(bar_db)

    assert not logic.update_menu_item(bar_db, owner, 999, "Ghost", 2.00).success
    assert not logic.delete_menu_item(bar_db, owner, 999).success


# --- opening hours ----------------------------------------------------------

def test_the_owner_can_set_a_weekday(bar_db):
    owner, venue_id = owned_bar(bar_db)

    result = logic.set_venue_hours(bar_db, owner, venue_id, 0, "16:00", "23:00")

    assert result.success
    assert logic.get_opening_hours(bar_db, venue_id)[0]["text"] == "16:00–23:00"


def test_staying_open_past_midnight_is_allowed(bar_db):
    owner, venue_id = owned_bar(bar_db)

    assert logic.set_venue_hours(bar_db, owner, venue_id, 4, "16:00", "02:00").success
    assert logic.get_opening_hours(bar_db, venue_id)[4]["text"] == "16:00–02:00"


def test_identical_opening_and_closing_times_are_refused(bar_db):
    owner, venue_id = owned_bar(bar_db)

    assert not logic.set_venue_hours(bar_db, owner, venue_id, 0, "16:00", "16:00").success


def test_time_objects_from_the_screen_are_accepted(bar_db):
    owner, venue_id = owned_bar(bar_db)

    assert logic.set_venue_hours(bar_db, owner, venue_id, 2, time(17, 30), time(1, 0)).success
    assert logic.get_opening_hours(bar_db, venue_id)[2]["text"] == "17:30–01:00"


@pytest.mark.parametrize("opens,closes", [("25:00", "02:00"), ("16h", "02:00"),
                                          ("16:00", "not a time"), (None, "02:00")])
def test_unreadable_times_are_refused(bar_db, opens, closes):
    owner, venue_id = owned_bar(bar_db)

    assert not logic.set_venue_hours(bar_db, owner, venue_id, 0, opens, closes).success


def test_a_day_can_be_marked_closed_and_clears_its_times(bar_db):
    owner, venue_id = owned_bar(bar_db)
    logic.set_venue_hours(bar_db, owner, venue_id, 1, "16:00", "23:00")

    assert logic.set_venue_hours(bar_db, owner, venue_id, 1, None, None, closed=True).success
    tuesday_after = logic.get_opening_hours(bar_db, venue_id)[1]
    assert tuesday_after["text"] == "Closed"
    assert tuesday_after["opens_at"] is None


def test_a_weekday_that_was_never_set_reads_as_not_set(bar_db):
    _, venue_id = owned_bar(bar_db)

    week = logic.get_opening_hours(bar_db, venue_id)

    assert len(week) == 7
    assert all(day["text"] == "Not set" for day in week)
    assert not logic.has_opening_hours(bar_db, venue_id)


def test_setting_the_same_weekday_twice_updates_it(bar_db):
    owner, venue_id = owned_bar(bar_db)
    logic.set_venue_hours(bar_db, owner, venue_id, 3, "16:00", "23:00")

    logic.set_venue_hours(bar_db, owner, venue_id, 3, "18:00", "01:00")

    assert logic.get_opening_hours(bar_db, venue_id)[3]["text"] == "18:00–01:00"
    assert len(bar_db.get_venue_hours(venue_id)) == 1


@pytest.mark.parametrize("weekday", [-1, 7, "monday", None])
def test_an_impossible_weekday_is_refused(bar_db, weekday):
    owner, venue_id = owned_bar(bar_db)

    assert not logic.set_venue_hours(bar_db, owner, venue_id, weekday, "16:00", "23:00").success


def test_only_the_owner_can_set_hours(bar_db):
    owner, venue_id = owned_bar(bar_db, "first")
    intruder, _ = owned_bar(bar_db, "second")
    customer = make_user(bar_db, "cato")

    assert not logic.set_venue_hours(bar_db, intruder, venue_id, 0, "16:00", "23:00").success
    assert not logic.set_venue_hours(bar_db, customer, venue_id, 0, "16:00", "23:00").success
    assert not logic.set_venue_hours(bar_db, None, venue_id, 0, "16:00", "23:00").success
    assert not logic.has_opening_hours(bar_db, venue_id)


def test_the_new_tables_are_covered_by_row_level_security(bar_db):
    names = bar_db._rls_table_names()
    assert {"venue_owners", "venue_hours", "menu_items"} <= set(names)
