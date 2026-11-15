"""GUI smoke tests with a fake weather client (offline). Needs a desktop session."""
import io
import tkinter as tk

import pytest
from PIL import Image

from app import WeatherApp
from test_weather import HYDERABAD, make_forecast_json
from weather_core import CityNotFoundError, NetworkError, parse_forecast


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGBA", (100, 100), (255, 200, 0, 255)).save(buffer, "PNG")
    return buffer.getvalue()


class FakeClient:
    def __init__(self, error=None):
        self.error = error
        self.cities = []

    def geocode(self, city):
        self.cities.append(city)
        if self.error:
            raise self.error
        return HYDERABAD

    def locate_by_ip(self):
        return HYDERABAD

    def forecast(self, location):
        return parse_forecast(location, make_forecast_json())


@pytest.fixture(scope="module")
def root():
    try:
        window_root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display available: {exc}")
    window_root.withdraw()
    yield window_root
    window_root.destroy()


def make_gui(root, client=None, icons=True):
    window = WeatherApp(root, client=client or FakeClient(), icon_downloader=(lambda code: png_bytes()) if icons else (lambda code: None),
                        synchronous=True)
    window.pack()
    return window


@pytest.fixture()
def gui(root):
    window = make_gui(root)
    yield window
    window.destroy()


def texts(frame):
    return [child.cget("text") for child in frame.winfo_children() if isinstance(child, tk.Label)]


def all_texts(widget):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Label):
            found.append(child.cget("text"))
        found += all_texts(child)
    return found


def test_get_weather_fills_current_hourly_and_daily_panels(gui):
    gui.city_var.set("Hyderabad")
    gui.get_weather()
    shown = all_texts(gui.current_card)
    assert "Hyderabad, Telangana, India" in shown
    assert "29.1°C" in shown                                         # selected unit
    assert any("Partly cloudy" in t and "84.4°F" in t for t in shown)  # other unit shown too
    assert any(t.startswith("Humidity") and "61%" in t for t in shown)
    assert any(t.startswith("Wind") and "12.4 km/h" in t for t in shown)
    assert len(gui.hourly_box.winfo_children()) == 6
    assert len(gui.daily_box.winfo_children()) == 5
    assert gui.error_var.get() == ""


def test_icons_are_shown_when_download_works_and_text_fallback_otherwise(root):
    with_icons = make_gui(root)
    with_icons.city_var.set("Hyderabad")
    with_icons.get_weather()
    assert with_icons.current_card.winfo_children()[0].winfo_children()[0].cget("image")
    with_icons.destroy()
    without = make_gui(root, icons=False)
    without.city_var.set("Hyderabad")
    without.get_weather()                                              # must not crash
    assert "(icon unavailable)" in all_texts(without.current_card)
    without.destroy()


def test_unit_toggle_switches_every_panel_without_a_new_request(gui):
    gui.city_var.set("Hyderabad")
    gui.get_weather()
    lookups = len(gui.client.cities)
    gui.toggle_unit()
    assert gui.unit == "F" and gui.unit_button.cget("text") == "Switch to °C"
    assert "84.4°F" in all_texts(gui.current_card)
    assert any("°" in t and "/" in t for t in all_texts(gui.daily_box))
    gui.toggle_unit()
    assert "29.1°C" in all_texts(gui.current_card)
    assert len(gui.client.cities) == lookups


def test_empty_city_shows_error_inside_the_window(gui):
    gui.city_var.set("   ")
    gui.get_weather()
    assert "type a city" in gui.error_var.get().lower()
    assert gui.client.cities == []


def test_city_not_found_error_is_shown_and_old_results_are_cleared(root):
    window = make_gui(root)
    window.city_var.set("Hyderabad")
    window.get_weather()
    assert window.forecast is not None
    window.client.error = CityNotFoundError("'Zzzzqx' was not found. Check the spelling.")
    window.city_var.set("Zzzzqx")
    window.get_weather()
    assert "not found" in window.error_var.get()
    assert window.forecast is None
    assert "No weather loaded yet" in all_texts(window.current_card)
    window.destroy()


def test_network_error_is_shown_and_buttons_come_back(gui):
    gui.client.error = NetworkError("Could not connect - please check your internet connection and try again.")
    gui.city_var.set("Paris")
    gui.get_weather()
    assert "internet connection" in gui.error_var.get()
    assert str(gui.get_button.cget("state")) == "normal"


def test_unexpected_exceptions_do_not_crash_the_window(gui):
    gui.client.error = RuntimeError("boom")
    gui.city_var.set("Paris")
    gui.get_weather()
    assert "unexpected" in gui.error_var.get().lower()


def test_use_my_location_button_loads_weather(gui):
    gui.use_my_location()
    assert gui.forecast is not None and gui.forecast.location.name == "Hyderabad"
