"""Core logic for the Weather App (Oasis Infobyte - Python Programming, Task 4, Advanced tier).

Data comes from the free Open-Meteo API (https://open-meteo.com) - no API key is needed.
Weather icons are the public OpenWeatherMap icon images (https://openweathermap.org/img/wn/<code>@2x.png).

This module has no GUI code and takes an injectable ``get`` function, so all of it can be tested offline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
IP_LOCATION_URL = "https://ipinfo.io/json"
ICON_URL = "https://openweathermap.org/img/wn/{code}@2x.png"
TIMEOUT_SECONDS = 10
HOURS_SHOWN = 6
DAYS_SHOWN = 5
MAX_CITY_LENGTH = 80


# ----------------------------------------------------------------------- errors
class WeatherError(Exception):
    """Base class: the message is always safe to show to the user."""


class InvalidInputError(WeatherError):
    pass


class CityNotFoundError(WeatherError):
    pass


class NetworkError(WeatherError):
    pass


class ApiError(WeatherError):
    pass


# ----------------------------------------------------------------------- models
@dataclass(frozen=True)
class Location:
    name: str
    country: str
    region: str
    latitude: float
    longitude: float

    @property
    def title(self) -> str:
        parts = [self.name]
        if self.region and self.region != self.name:
            parts.append(self.region)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass(frozen=True)
class Current:
    temp_c: float
    feels_like_c: float
    humidity: int
    wind_kmh: float
    code: int
    is_day: bool
    time: str


@dataclass(frozen=True)
class HourPoint:
    label: str       # e.g. "15:00"
    temp_c: float
    code: int
    is_day: bool


@dataclass(frozen=True)
class DayPoint:
    label: str       # e.g. "Mon 16 Nov"
    max_c: float
    min_c: float
    code: int


@dataclass(frozen=True)
class Forecast:
    location: Location
    current: Current
    hourly: list[HourPoint]
    daily: list[DayPoint]


# ---------------------------------------------------------- weather code table
# WMO weather interpretation codes -> (description, OpenWeatherMap icon number)
WMO = {
    0: ("Clear sky", "01"), 1: ("Mainly clear", "02"), 2: ("Partly cloudy", "03"), 3: ("Overcast", "04"),
    45: ("Fog", "50"), 48: ("Freezing fog", "50"),
    51: ("Light drizzle", "09"), 53: ("Drizzle", "09"), 55: ("Heavy drizzle", "09"),
    56: ("Light freezing drizzle", "09"), 57: ("Freezing drizzle", "09"),
    61: ("Light rain", "10"), 63: ("Rain", "10"), 65: ("Heavy rain", "10"),
    66: ("Light freezing rain", "10"), 67: ("Freezing rain", "10"),
    71: ("Light snow", "13"), 73: ("Snow", "13"), 75: ("Heavy snow", "13"), 77: ("Snow grains", "13"),
    80: ("Light rain showers", "09"), 81: ("Rain showers", "09"), 82: ("Violent rain showers", "09"),
    85: ("Light snow showers", "13"), 86: ("Heavy snow showers", "13"),
    95: ("Thunderstorm", "11"), 96: ("Thunderstorm with hail", "11"), 99: ("Severe thunderstorm with hail", "11"),
}


def describe(code: int) -> str:
    return WMO.get(code, ("Unknown conditions", "03"))[0]


def icon_code(code: int, is_day: bool = True) -> str:
    """OpenWeatherMap icon id such as '10d' (rain, day) or '01n' (clear, night)."""
    number = WMO.get(code, ("", "03"))[1]
    return number + ("d" if is_day else "n")


def scene_colour(code: int, is_day: bool = True) -> str:
    """Background colour for the weather panel: bright blue for a clear day, navy at night, slate for rain, and so on."""
    if code in (0, 1):
        group = ("#2f80d1", "#1b2a52")
    elif code in (2, 3):
        group = ("#5a7a9c", "#2d3856")
    elif code in (45, 48):
        group = ("#76879a", "#3b4658")
    elif code in (71, 73, 75, 77, 85, 86):
        group = ("#7d9fc0", "#3b4c69")
    elif code in (95, 96, 99):
        group = ("#4a4a68", "#2b2b45")
    elif code in WMO:                                  # drizzle, rain, showers
        group = ("#3f6288", "#26344f")
    else:
        group = ("#3f6ea5", "#26344f")
    return group[0] if is_day else group[1]


# --------------------------------------------------------------------- helpers
def c_to_f(celsius: float) -> float:
    return celsius * 9 / 5 + 32


def kmh_to_mph(kmh: float) -> float:
    return kmh * 0.621371


def format_temp(celsius: float, unit: str) -> str:
    """'29.1°C' or '84.4°F' depending on ``unit`` ('C' or 'F')."""
    return f"{c_to_f(celsius):.1f}°F" if unit == "F" else f"{celsius:.1f}°C"


def format_temp_short(celsius: float, unit: str) -> str:
    return f"{c_to_f(celsius):.0f}°" if unit == "F" else f"{celsius:.0f}°"


def validate_city(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise InvalidInputError("Please type a city name first, for example Hyderabad or Paris, France.")
    if len(cleaned) > MAX_CITY_LENGTH:
        raise InvalidInputError(f"That is too long - please use at most {MAX_CITY_LENGTH} characters.")
    return cleaned


# ---------------------------------------------------------------------- client
class WeatherClient:
    """Thin wrapper around the HTTP calls. ``get`` is injectable so tests never touch the network."""

    def __init__(self, get=requests.get, timeout: int = TIMEOUT_SECONDS):
        self._get = get
        self._timeout = timeout

    def _json(self, url: str, params: dict | None = None) -> dict:
        try:
            response = self._get(url, params=params, timeout=self._timeout, headers={"User-Agent": "oasis-weather-app/1.0"})
        except requests.exceptions.Timeout:
            raise NetworkError("The weather service took too long to answer. Please try again.") from None
        except requests.exceptions.ConnectionError:
            raise NetworkError("Could not connect - please check your internet connection and try again.") from None
        except requests.exceptions.RequestException as exc:
            raise NetworkError(f"The request failed: {exc}") from None
        if response.status_code == 429:
            raise ApiError("The weather service is busy (too many requests). Please wait a minute and try again.")
        if response.status_code >= 400:
            raise ApiError(f"The weather service returned an error (HTTP {response.status_code}).")
        try:
            return response.json()
        except ValueError:
            raise ApiError("The weather service sent a reply that could not be understood.") from None

    def geocode(self, city: str) -> Location:
        """Find a place. 'Paris' gives the best match; 'Paris, Texas' / 'Hyderabad, India' narrow it by region or country."""
        city = validate_city(city)
        name, _, hint = (part.strip() for part in city.partition(","))
        data = self._json(GEOCODING_URL, {"name": name or city, "count": 10 if hint else 1, "language": "en", "format": "json"})
        results = data.get("results") or []
        if hint:
            wanted = hint.casefold()
            results = [r for r in results if wanted in {str(r.get(k, "")).casefold() for k in ("country", "country_code", "admin1", "admin2")}]
        if not results:
            raise CityNotFoundError(f"'{city}' was not found. Check the spelling, or try just the city name.")
        top = results[0]
        try:
            return Location(top["name"], top.get("country", ""), top.get("admin1", ""), float(top["latitude"]), float(top["longitude"]))
        except (KeyError, TypeError, ValueError):
            raise ApiError("The location reply was missing some details.") from None

    def locate_by_ip(self) -> Location:
        """Bonus feature: guess the user's location from their IP address using ipinfo.io (free tier)."""
        data = self._json(IP_LOCATION_URL)
        try:
            latitude, longitude = (float(part) for part in data["loc"].split(","))
            return Location(data.get("city") or "Your location", data.get("country", ""), data.get("region", ""), latitude, longitude)
        except (KeyError, AttributeError, ValueError):
            raise ApiError("Could not work out your location automatically. Please type a city instead.") from None

    def forecast(self, location: Location) -> Forecast:
        data = self._json(FORECAST_URL, {
            "latitude": location.latitude, "longitude": location.longitude, "timezone": "auto", "forecast_days": DAYS_SHOWN + 1,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day",
            "hourly": "temperature_2m,weather_code,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "wind_speed_unit": "kmh",
        })
        return parse_forecast(location, data)


def parse_forecast(location: Location, data: dict) -> Forecast:
    """Turn the Open-Meteo JSON into our own small dataclasses (raises ``ApiError`` if anything is missing)."""
    try:
        cur = data["current"]
        current = Current(
            temp_c=float(cur["temperature_2m"]), feels_like_c=float(cur["apparent_temperature"]),
            humidity=int(round(cur["relative_humidity_2m"])), wind_kmh=float(cur["wind_speed_10m"]),
            code=int(cur["weather_code"]), is_day=bool(cur["is_day"]), time=str(cur["time"]),
        )
        hourly = data["hourly"]
        now_hour = current.time[:13] + ":00"                      # "2026-11-15T14:45" -> "2026-11-15T14:00"
        start = hourly["time"].index(now_hour) + 1                  # the hours AFTER the current one
        hours = [
            HourPoint(hourly["time"][i][11:16], float(hourly["temperature_2m"][i]), int(hourly["weather_code"][i]), bool(hourly["is_day"][i]))
            for i in range(start, start + HOURS_SHOWN)
        ]
        daily = data["daily"]
        days = [
            DayPoint(datetime.strptime(daily["time"][i], "%Y-%m-%d").strftime("%a %d %b"), float(daily["temperature_2m_max"][i]),
                     float(daily["temperature_2m_min"][i]), int(daily["weather_code"][i]))
            for i in range(1, DAYS_SHOWN + 1)                       # tomorrow and the 4 days after
        ]
    except (KeyError, IndexError, ValueError, TypeError):
        raise ApiError("The weather reply was incomplete. Please try again in a moment.") from None
    return Forecast(location, current, hours, days)


def icon_codes_needed(forecast: Forecast) -> set[str]:
    codes = {icon_code(forecast.current.code, forecast.current.is_day)}
    codes |= {icon_code(h.code, h.is_day) for h in forecast.hourly}
    codes |= {icon_code(d.code, True) for d in forecast.daily}
    return codes


def download_icon(code: str, get=requests.get, timeout: int = TIMEOUT_SECONDS) -> bytes | None:
    """PNG bytes for one OpenWeatherMap icon, or ``None`` if it cannot be downloaded (the UI then shows text only)."""
    try:
        response = get(ICON_URL.format(code=code), timeout=timeout)
        return response.content if response.status_code == 200 else None
    except requests.exceptions.RequestException:
        return None
