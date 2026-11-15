"""Offline unit tests for the weather core (no network needed).  Run with:  python -m pytest -q"""
from datetime import datetime, timedelta

import pytest
import requests

from weather_core import (
    ApiError,
    CityNotFoundError,
    InvalidInputError,
    Location,
    NetworkError,
    WeatherClient,
    c_to_f,
    describe,
    download_icon,
    format_temp,
    format_temp_short,
    icon_code,
    icon_codes_needed,
    kmh_to_mph,
    parse_forecast,
    validate_city,
)


# ------------------------------------------------------------------- test doubles
class FakeResponse:
    def __init__(self, status=200, payload=None, content=b"", bad_json=False):
        self.status_code = status
        self._payload = payload
        self.content = content
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


def make_forecast_json(now="2026-11-15T14:45", start="2026-11-15T00:00", hours=96):
    first = datetime.fromisoformat(start)
    times = [(first + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    return {
        "current": {"time": now, "temperature_2m": 29.1, "apparent_temperature": 31.4, "relative_humidity_2m": 61.0,
                    "wind_speed_10m": 12.4, "weather_code": 2, "is_day": 1},
        "hourly": {"time": times, "temperature_2m": [20 + (i % 24) / 2 for i in range(hours)],
                   "weather_code": [61 if i % 24 > 18 else 1 for i in range(hours)],
                   "is_day": [1 if 6 <= i % 24 < 18 else 0 for i in range(hours)]},
        "daily": {"time": [(first + timedelta(days=d)).strftime("%Y-%m-%d") for d in range(6)],
                  "weather_code": [2, 3, 61, 95, 0, 71], "temperature_2m_max": [30, 31, 28, 27, 29, -1],
                  "temperature_2m_min": [21, 22, 20, 19, 20, -5]},
    }


HYDERABAD = Location("Hyderabad", "India", "Telangana", 17.38, 78.48)


def client_returning(response=None, error=None):
    def get(url, params=None, timeout=None, headers=None):
        if error:
            raise error
        return response
    return WeatherClient(get=get)


# --------------------------------------------------------------------- validation
@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_city_is_rejected(text):
    with pytest.raises(InvalidInputError):
        validate_city(text)


def test_city_is_trimmed_and_length_limited():
    assert validate_city("  New   York ") == "New York"
    with pytest.raises(InvalidInputError):
        validate_city("x" * 81)


# ------------------------------------------------------------------ geocoding
def test_geocode_success():
    payload = {"results": [{"name": "Hyderabad", "country": "India", "admin1": "Telangana", "latitude": 17.38, "longitude": 78.48}]}
    location = client_returning(FakeResponse(payload=payload)).geocode("Hyderabad")
    assert location.title == "Hyderabad, Telangana, India"
    assert (location.latitude, location.longitude) == (17.38, 78.48)


PARIS_RESULTS = {"results": [
    {"name": "Paris", "country": "France", "country_code": "FR", "admin1": "Ile-de-France", "latitude": 48.85, "longitude": 2.35},
    {"name": "Paris", "country": "United States", "country_code": "US", "admin1": "Texas", "latitude": 33.66, "longitude": -95.55},
]}


def test_geocode_without_a_hint_takes_the_best_match_and_asks_for_one_result():
    seen = {}

    def get(url, params=None, timeout=None, headers=None):
        seen.update(params)
        return FakeResponse(payload=PARIS_RESULTS)

    assert WeatherClient(get=get).geocode("Paris").country == "France"
    assert seen["count"] == 1 and seen["name"] == "Paris"


@pytest.mark.parametrize("query,country", [
    ("Paris, Texas", "United States"), ("paris , us", "United States"), ("Paris, United States", "United States"),
    ("Paris, France", "France"), ("Paris, fr", "France"),
])
def test_geocode_hint_after_a_comma_picks_the_matching_place(query, country):
    seen = {}

    def get(url, params=None, timeout=None, headers=None):
        seen.update(params)
        return FakeResponse(payload=PARIS_RESULTS)

    assert WeatherClient(get=get).geocode(query).country == country
    assert seen["name"].lower() == "paris" and seen["count"] == 10     # only the part before the comma is searched


def test_geocode_hint_that_matches_nothing_is_reported_as_not_found():
    with pytest.raises(CityNotFoundError, match="Paris, Narnia"):
        client_returning(FakeResponse(payload=PARIS_RESULTS)).geocode("Paris, Narnia")


def test_geocode_city_not_found():
    with pytest.raises(CityNotFoundError, match="Zzzzqx"):
        client_returning(FakeResponse(payload={"generationtime_ms": 0.3})).geocode("Zzzzqx")
    with pytest.raises(CityNotFoundError):
        client_returning(FakeResponse(payload={"results": []})).geocode("Zzzzqx")


def test_geocode_empty_input_never_calls_the_network():
    def get(*_a, **_k):
        raise AssertionError("network must not be called for empty input")
    with pytest.raises(InvalidInputError):
        WeatherClient(get=get).geocode("   ")


def test_geocode_reply_missing_fields():
    with pytest.raises(ApiError):
        client_returning(FakeResponse(payload={"results": [{"name": "X"}]})).geocode("X")


# --------------------------------------------------------------- network errors
def test_timeout_becomes_friendly_network_error():
    with pytest.raises(NetworkError, match="too long"):
        client_returning(error=requests.exceptions.Timeout()).geocode("Paris")


def test_no_connection_becomes_friendly_network_error():
    with pytest.raises(NetworkError, match="internet connection"):
        client_returning(error=requests.exceptions.ConnectionError()).geocode("Paris")


def test_other_request_errors_are_wrapped():
    with pytest.raises(NetworkError):
        client_returning(error=requests.exceptions.InvalidURL("bad")).geocode("Paris")


@pytest.mark.parametrize("status,match", [(500, "HTTP 500"), (404, "HTTP 404"), (429, "busy")])
def test_http_errors_become_api_errors(status, match):
    with pytest.raises(ApiError, match=match):
        client_returning(FakeResponse(status=status, payload={})).geocode("Paris")


def test_invalid_json_becomes_api_error():
    with pytest.raises(ApiError, match="understood"):
        client_returning(FakeResponse(bad_json=True)).geocode("Paris")


# ------------------------------------------------------------------- forecast
def test_forecast_is_parsed_into_current_hourly_and_daily():
    forecast = parse_forecast(HYDERABAD, make_forecast_json())
    assert forecast.current.temp_c == 29.1 and forecast.current.humidity == 61 and forecast.current.wind_kmh == 12.4
    assert forecast.current.is_day is True
    assert [h.label for h in forecast.hourly] == ["15:00", "16:00", "17:00", "18:00", "19:00", "20:00"]
    assert len(forecast.daily) == 5
    assert forecast.daily[0].label == "Mon 16 Nov"          # tomorrow, not today
    assert forecast.daily[-1].label == "Fri 20 Nov"


def test_hourly_forecast_rolls_over_midnight():
    forecast = parse_forecast(HYDERABAD, make_forecast_json(now="2026-11-15T22:10"))
    assert [h.label for h in forecast.hourly] == ["23:00", "00:00", "01:00", "02:00", "03:00", "04:00"]


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("current"), lambda d: d.pop("hourly"), lambda d: d.pop("daily"),
    lambda d: d["current"].pop("temperature_2m"),
    lambda d: d["daily"].update(time=d["daily"]["time"][:3]),
    lambda d: d["current"].update(time="2030-01-01T10:00"),     # current hour not present in the hourly table
])
def test_incomplete_forecast_replies_raise_api_error(mutate):
    data = make_forecast_json()
    mutate(data)
    with pytest.raises(ApiError, match="incomplete"):
        parse_forecast(HYDERABAD, data)


def test_forecast_request_uses_location_and_auto_timezone():
    seen = {}

    def get(url, params=None, timeout=None, headers=None):
        seen.update(url=url, params=params)
        return FakeResponse(payload=make_forecast_json())

    forecast = WeatherClient(get=get).forecast(HYDERABAD)
    assert seen["params"]["latitude"] == 17.38 and seen["params"]["timezone"] == "auto"
    assert forecast.location is HYDERABAD


# --------------------------------------------------------------- IP location bonus
def test_locate_by_ip_success_and_failure():
    ok = client_returning(FakeResponse(payload={"city": "Pune", "region": "Maharashtra", "country": "IN", "loc": "18.52,73.85"}))
    location = ok.locate_by_ip()
    assert location.name == "Pune" and location.latitude == 18.52
    with pytest.raises(ApiError):
        client_returning(FakeResponse(payload={"bogon": True})).locate_by_ip()


# -------------------------------------------------------------------- conversions
def test_temperature_conversions_and_formatting():
    assert c_to_f(0) == 32 and c_to_f(100) == 212 and c_to_f(-40) == -40
    assert format_temp(29.1, "C") == "29.1°C"
    assert format_temp(29.1, "F") == "84.4°F"
    assert format_temp_short(29.6, "C") == "30°" and format_temp_short(0, "F") == "32°"
    assert round(kmh_to_mph(100), 1) == 62.1


def test_weather_codes_map_to_descriptions_and_owm_icons():
    assert describe(0) == "Clear sky" and describe(95) == "Thunderstorm" and describe(12345) == "Unknown conditions"
    assert icon_code(0, True) == "01d" and icon_code(0, False) == "01n"
    assert icon_code(63) == "10d" and icon_code(73) == "13d" and icon_code(45) == "50d" and icon_code(999) == "03d"


def test_scene_colour_depends_on_conditions_and_daylight():
    import re

    from weather_core import WMO, scene_colour

    for code in list(WMO) + [12345]:
        for is_day in (True, False):
            assert re.fullmatch(r"#[0-9a-f]{6}", scene_colour(code, is_day))
    assert scene_colour(0, True) != scene_colour(0, False)       # clear day vs clear night
    assert scene_colour(0, True) != scene_colour(63, True)       # clear vs rain
    assert scene_colour(95, True) != scene_colour(73, True)      # thunderstorm vs snow


def test_icon_codes_needed_covers_current_hours_and_days():
    codes = icon_codes_needed(parse_forecast(HYDERABAD, make_forecast_json()))
    assert "03d" in codes and "13d" in codes          # current partly cloudy, snow day
    assert all(len(code) == 3 for code in codes)


def test_download_icon_returns_none_on_any_failure():
    assert download_icon("10d", get=lambda *_a, **_k: FakeResponse(content=b"PNG")) == b"PNG"
    assert download_icon("10d", get=lambda *_a, **_k: FakeResponse(status=404)) is None

    def boom(*_a, **_k):
        raise requests.exceptions.ConnectionError()
    assert download_icon("10d", get=boom) is None
