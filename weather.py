"""Read cached weather observations from Open-Meteo and IPMA."""

import json
import math
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st

import logic


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
IPMA_STATIONS_URL = (
    "https://api.ipma.pt/open-data/observation/meteorology/stations/stations.json"
)
IPMA_OBSERVATIONS_URL = (
    "https://api.ipma.pt/open-data/observation/meteorology/stations/observations.json"
)


def _get_json(url):
    """Fetch JSON with a short timeout so weather cannot stall the app."""
    request = Request(url, headers={"User-Agent": "Bock-and-Bros/1.0"})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _number(value):
    """Return a finite observation number, or reject missing/sentinel data."""
    if value is None or isinstance(value, bool):
        raise ValueError("Missing weather value")
    number = float(value)
    if number == -99 or not math.isfinite(number):
        raise ValueError("Invalid weather value")
    return number


def _parse_timestamp(value):
    """Parse provider timestamps consistently in Lisbon time."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Europe/Lisbon"))
    return parsed


def _time_label(value):
    """Return the local hour and minute from an API timestamp."""
    return _parse_timestamp(value).astimezone(ZoneInfo("Europe/Lisbon")).strftime("%H:%M")


@st.cache_data(ttl=900, show_spinner=False)
def get_open_meteo_weather(lat, lon):
    """Return current Open-Meteo conditions and the next-hour rain chance."""
    try:
        query = urlencode({
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,weather_code",
            "hourly": "precipitation_probability",
            "forecast_hours": 48,
            "timezone": "Europe/Lisbon",
        })
        payload = _get_json(f"{OPEN_METEO_URL}?{query}")
        current = payload["current"]
        hourly = payload["hourly"]
        current_time = _parse_timestamp(current["time"])
        next_hour_index = next(
            index for index, value in enumerate(hourly["time"])
            if _parse_timestamp(value) > current_time
        )
        return {
            "temperature": _number(current["temperature_2m"]),
            "precipitation": _number(current["precipitation"]),
            "weather_code": int(current["weather_code"]),
            "rain_chance": _number(
                hourly["precipitation_probability"][next_hour_index]
            ),
            "time": _time_label(current["time"]),
        }
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def get_ipma_weather(lat, lon):
    """Return the latest valid observation from the nearest Lisbon IPMA station."""
    try:
        stations = _get_json(IPMA_STATIONS_URL)
        lisbon_stations = [
            station for station in stations
            if "lisboa" in station.get("properties", {}).get("localEstacao", "").casefold()
        ]
        station = logic.closest_station(lat, lon, lisbon_stations)
        if station is None:
            return None

        station_properties = station["properties"]
        station_id = str(station_properties["idEstacao"])
        observations = _get_json(IPMA_OBSERVATIONS_URL)
        latest_time = max(
            timestamp for timestamp in observations
            if station_id in observations[timestamp]
        )
        reading = observations[latest_time][station_id]
        if reading is None:
            return None
        return {
            "temperature": _number(reading["temperatura"]),
            "precipitation": _number(reading["precAcumulada"]),
            "station": station_properties["localEstacao"],
            "time": _time_label(latest_time),
        }
    except Exception:
        return None


def get_venue_weather(lat, lon):
    """Fetch both providers independently and represent failed sources as absent."""
    result = {}
    for key, source in (
        ("open_meteo", get_open_meteo_weather),
        ("ipma", get_ipma_weather),
    ):
        try:
            result[key] = source(lat, lon)
        except Exception:
            result[key] = None
    return result
