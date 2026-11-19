"""Tests for weather descriptions, terrace rules, and source adapters."""

from urllib.parse import parse_qs, urlparse

import logic
import weather


def test_describe_weather_maps_common_codes_and_unknown_values():
    assert logic.describe_weather(0) == "Clear sky"
    assert logic.describe_weather(2) == "Partly cloudy"
    assert logic.describe_weather(3) == "Overcast"
    assert logic.describe_weather(61) == "Rain"
    assert logic.describe_weather(95) == "Thunderstorm"
    assert logic.describe_weather(999) == "Unknown conditions"


def test_terrace_weather_requires_all_conditions():
    assert logic.is_terrace_weather(18, 0, 0, 29, 0)
    assert logic.is_terrace_weather(18, 0, 0, 29, 1)
    assert logic.is_terrace_weather(20, 0, 0, 0, 2)


def test_terrace_weather_rejects_each_unmet_condition():
    cases = [
        (17.9, 0, 0, 0, 0),
        (18, 0.1, 0, 0, 0),
        (18, 0, 0.1, 0, 0),
        (18, 0, 0, 30, 0),
        (18, 0, 0, 0, 3),
    ]
    assert all(not logic.is_terrace_weather(*case) for case in cases)


def test_closest_station_returns_nearest_and_empty_returns_none():
    stations = [
        {"geometry": {"coordinates": [-9.20, 38.72]},
         "properties": {"idEstacao": 1, "localEstacao": "Lisboa West"}},
        {"geometry": {"coordinates": [-9.14, 38.72]},
         "properties": {"idEstacao": 2, "localEstacao": "Lisboa Central"}},
    ]
    assert logic.closest_station(38.7169, -9.1399, stations) == stations[1]
    assert logic.closest_station(38.7169, -9.1399, []) is None


def test_open_meteo_reads_current_and_next_hour_probability(monkeypatch):
    payload = {
        "current": {
            "time": "2026-11-19T10:15", "temperature_2m": 17.4,
            "precipitation": 0, "weather_code": 3,
        },
        "hourly": {
            "time": ["2026-11-19T10:00", "2026-11-19T11:00"],
            "precipitation_probability": [15, 40],
        },
    }
    calls = []

    def fake_get_json(url):
        calls.append(url)
        return payload

    monkeypatch.setattr(weather, "_get_json", fake_get_json)
    weather.get_open_meteo_weather.clear()

    result = weather.get_open_meteo_weather(38.7169, -9.1399)

    assert result == {
        "temperature": 17.4, "precipitation": 0, "weather_code": 3,
        "rain_chance": 40, "time": "10:15",
    }
    query = parse_qs(urlparse(calls[0]).query)
    assert query["latitude"] == ["38.7169"]
    assert query["longitude"] == ["-9.1399"]
    assert query["timezone"] == ["Europe/Lisbon"]
    assert "temperature_2m,precipitation,weather_code" in query["current"][0]
    assert query["hourly"] == ["precipitation_probability"]


def test_open_meteo_failure_returns_no_weather(monkeypatch):
    def failing_get_json(_url):
        raise TimeoutError

    monkeypatch.setattr(weather, "_get_json", failing_get_json)
    weather.get_open_meteo_weather.clear()
    assert weather.get_open_meteo_weather(38.7169, -9.1399) is None


def test_ipma_uses_nearest_lisbon_station_and_latest_valid_observation(monkeypatch):
    stations = [
        {"geometry": {"coordinates": [-9.20, 38.72]},
         "properties": {"idEstacao": 1, "localEstacao": "Lisboa West"}},
        {"geometry": {"coordinates": [-9.14, 38.72]},
         "properties": {"idEstacao": 2, "localEstacao": "Lisboa, Geofísico"}},
        {"geometry": {"coordinates": [-8.0, 40.0]},
         "properties": {"idEstacao": 3, "localEstacao": "Other City"}},
    ]
    observations = {
        "2026-11-19T09:00": {"2": {"temperatura": 16.8, "precAcumulada": 0.4}},
        "2026-11-19T10:00": {"2": {"temperatura": 17.0, "precAcumulada": 0.0}},
    }
    payloads = iter([stations, observations])
    monkeypatch.setattr(weather, "_get_json", lambda _url: next(payloads))
    weather.get_ipma_weather.clear()

    result = weather.get_ipma_weather(38.7169, -9.1399)

    assert result == {
        "temperature": 17.0, "precipitation": 0.0,
        "station": "Lisboa, Geofísico", "time": "10:00",
    }


def test_ipma_failure_returns_no_weather(monkeypatch):
    def failing_get_json(_url):
        raise TimeoutError

    monkeypatch.setattr(weather, "_get_json", failing_get_json)
    weather.get_ipma_weather.clear()
    assert weather.get_ipma_weather(38.7169, -9.1399) is None


def test_both_sources_failing_returns_empty_weather_without_raising(monkeypatch):
    def failing_source(*_args):
        raise TimeoutError

    monkeypatch.setattr(weather, "get_open_meteo_weather", failing_source)
    monkeypatch.setattr(weather, "get_ipma_weather", failing_source)

    assert weather.get_venue_weather(38.7169, -9.1399) == {
        "open_meteo": None, "ipma": None,
    }


def test_ipma_observation_with_no_valid_station_data_returns_none(monkeypatch):
    stations = [{
        "geometry": {"coordinates": [-9.14, 38.72]},
        "properties": {"idEstacao": 2, "localEstacao": "Lisboa Central"},
    }]
    observations = {"2026-11-19T10:00": {"2": None}}
    payloads = iter([stations, observations])
    monkeypatch.setattr(weather, "_get_json", lambda _url: next(payloads))
    weather.get_ipma_weather.clear()

    assert weather.get_ipma_weather(38.7169, -9.1399) is None


def test_empty_ipma_station_list_returns_none(monkeypatch):
    monkeypatch.setattr(weather, "_get_json", lambda _url: [])
    weather.get_ipma_weather.clear()

    assert weather.get_ipma_weather(38.7169, -9.1399) is None


def test_json_request_uses_five_second_timeout(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return Response()

    monkeypatch.setattr(weather, "urlopen", fake_urlopen)

    assert weather._get_json("https://weather.invalid/example") == {}
    assert calls == [("https://weather.invalid/example", 5)]
