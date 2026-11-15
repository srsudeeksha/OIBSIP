"""Weather App - tkinter GUI (Oasis Infobyte, Python Programming Task 4, Advanced tier).

Run:  python app.py
"""
from __future__ import annotations

import io
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from theme import BG, ERROR, FONT, MUTED, apply_theme, banner, blend
from weather_core import (
    DAYS_SHOWN,
    HOURS_SHOWN,
    Forecast,
    InvalidInputError,
    WeatherClient,
    WeatherError,
    describe,
    download_icon,
    format_temp,
    format_temp_short,
    icon_code,
    icon_codes_needed,
    kmh_to_mph,
    scene_colour,
    validate_city,
)

ACCENT = "#0369a1"          # sky blue
EMPTY_SCENE = "#e7edf7"     # panel colour before any weather is loaded
WHITE = "#ffffff"


class WeatherApp(ttk.Frame):
    """City box + 'Get Weather' button, current conditions, next 6 hours, next 5 days, and a C/F switch."""

    def __init__(self, master: tk.Misc, client: WeatherClient | None = None, icon_downloader=download_icon,
                 synchronous: bool = False):
        super().__init__(master)
        apply_theme(master, ACCENT)
        self.client = client or WeatherClient()
        self.icon_downloader = icon_downloader
        self.synchronous = synchronous          # tests / demos can run the lookup on the UI thread
        self.unit = "C"
        self.forecast: Forecast | None = None
        self._icon_bytes: dict[str, bytes | None] = {}
        self._photos: dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self._results: queue.Queue = queue.Queue()
        self._scene_bg = EMPTY_SCENE
        self.city_var = tk.StringVar()
        self.info_var = tk.StringVar(value="Type a city (add a country or state after a comma to be exact) and press Get Weather.")
        self.error_var = tk.StringVar()
        self._build()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        banner(self, "Weather", "Live conditions and forecast from Open-Meteo - no API key needed", ACCENT).grid(
            row=0, column=0, sticky="ew")
        body = ttk.Frame(self, padding=(20, 14, 20, 0))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        bar = ttk.Frame(body)
        bar.grid(row=0, column=0, sticky="ew")
        self.city_entry = ttk.Entry(bar, textvariable=self.city_var, font=(FONT, 12), width=26)
        self.city_entry.pack(side="left", ipady=3)
        self.city_entry.bind("<Return>", lambda _e: self.get_weather())
        self.get_button = ttk.Button(bar, text="Get Weather", style="Accent.TButton", command=self.get_weather)
        self.get_button.pack(side="left", padx=(10, 0))
        self.location_button = ttk.Button(bar, text="Use my location", style="Secondary.TButton", command=self.use_my_location)
        self.location_button.pack(side="left", padx=8)
        self.unit_button = ttk.Button(bar, text="Switch to °F", style="Secondary.TButton", command=self.toggle_unit, width=13)
        self.unit_button.pack(side="right")

        self.error_label = tk.Label(body, textvariable=self.error_var, fg=ERROR, bg=BG, anchor="w", justify="left",
                                    wraplength=700, font=(FONT, 10, "bold"))
        self.error_label.grid(row=1, column=0, sticky="ew", pady=(6, 2))

        # the "scene": one coloured panel that holds current weather, hourly and daily forecast
        self.scene = tk.Frame(body, bg=self._scene_bg, padx=18, pady=14)
        self.scene.grid(row=2, column=0, sticky="ew")
        self.scene.columnconfigure(0, weight=1)
        self.current_card = tk.Frame(self.scene, bg=self._scene_bg)
        self.current_card.grid(row=0, column=0, sticky="ew")
        self.hourly_caption = tk.Label(self.scene, text=f"NEXT {HOURS_SHOWN} HOURS", font=(FONT, 9, "bold"), bg=self._scene_bg, fg=WHITE, anchor="w")
        self.hourly_box = tk.Frame(self.scene, bg=self._scene_bg)
        self.daily_caption = tk.Label(self.scene, text=f"NEXT {DAYS_SHOWN} DAYS", font=(FONT, 9, "bold"), bg=self._scene_bg, fg=WHITE, anchor="w")
        self.daily_box = tk.Frame(self.scene, bg=self._scene_bg)

        self.info_label = tk.Label(self, textvariable=self.info_var, fg=MUTED, bg=BG, anchor="w", font=(FONT, 9), padx=22, pady=8)
        self.info_label.grid(row=2, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self._clear_result()

    # ------------------------------------------------------------------ messages
    def _show_error(self, message: str) -> None:
        self.error_var.set("⚠  " + message)
        self.info_var.set("")

    def _clear_error(self) -> None:
        self.error_var.set("")

    # ----------------------------------------------------------------- lookups
    def get_weather(self) -> None:
        try:
            city = validate_city(self.city_var.get())
        except InvalidInputError as exc:
            self._clear_result()
            self._show_error(str(exc))
            self.city_entry.focus_set()
            return
        self._start(lambda: self._load(self.client.geocode(city)), f"Looking up the weather for {city}...")

    def use_my_location(self) -> None:
        self._start(lambda: self._load(self.client.locate_by_ip()), "Detecting your location from your IP address...")

    def _load(self, location):
        forecast = self.client.forecast(location)
        icons = {code: self.icon_downloader(code) for code in icon_codes_needed(forecast)}
        return forecast, icons

    def _start(self, job, message: str) -> None:
        self._clear_error()
        self.info_var.set(message)
        self._set_busy(True)
        if self.synchronous:
            self._finish(self._run(job))
            return
        threading.Thread(target=lambda: self._results.put(self._run(job)), daemon=True).start()
        self.after(100, self._poll)

    @staticmethod
    def _run(job):
        try:
            return "ok", job()
        except WeatherError as exc:
            return "error", str(exc)
        except Exception as exc:  # noqa: BLE001 - never let a background failure freeze the window
            return "error", f"Something unexpected went wrong: {exc}"

    def _poll(self) -> None:
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            self.after(100, self._poll)
            return
        self._finish(result)

    def _finish(self, result) -> None:
        self._set_busy(False)
        kind, payload = result
        if kind == "error":
            self._clear_result()
            self._show_error(payload)
            return
        self.forecast, self._icon_bytes = payload
        self._photos.clear()
        self.info_var.set(f"Updated for {self.forecast.location.title}  (local time {self.forecast.current.time.replace('T', ' ')})")
        self.render()

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (self.get_button, self.location_button):
            button.configure(state=state)

    # ---------------------------------------------------------------- unit toggle
    def toggle_unit(self) -> None:
        self.unit = "F" if self.unit == "C" else "C"
        self.unit_button.configure(text="Switch to °C" if self.unit == "F" else "Switch to °F")
        if self.forecast:
            self.render()

    # ------------------------------------------------------------------- drawing
    def _photo(self, code: str, size: int):
        raw = self._icon_bytes.get(code)
        if not raw:
            return None
        key = (code, size)
        if key not in self._photos:
            try:
                image = Image.open(io.BytesIO(raw)).convert("RGBA").resize((size, size), Image.LANCZOS)
                self._photos[key] = ImageTk.PhotoImage(image, master=self)
            except Exception:  # noqa: BLE001 - a broken icon must not break the page
                return None
        return self._photos[key]

    def _icon_label(self, parent, code: str, size: int, bg: str) -> tk.Label:
        photo = self._photo(code, size)
        label = tk.Label(parent, image=photo, bg=bg) if photo else tk.Label(parent, text="(icon unavailable)", fg=WHITE, bg=bg, font=(FONT, 8))
        label.image = photo  # keep a reference so tkinter does not discard the image
        return label

    @staticmethod
    def _wipe(frame: tk.Misc) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def _paint_scene(self, colour: str) -> None:
        """Re-colour the panel (and its caption labels) to ``colour``."""
        self._scene_bg = colour
        for widget in (self.scene, self.current_card, self.hourly_box, self.daily_box, self.hourly_caption, self.daily_caption):
            widget.configure(bg=colour)

    def _clear_result(self) -> None:
        self.forecast = None
        self._paint_scene(EMPTY_SCENE)
        for frame in (self.current_card, self.hourly_box, self.daily_box):
            self._wipe(frame)
        for widget in (self.hourly_caption, self.hourly_box, self.daily_caption, self.daily_box):
            widget.grid_remove()
        tk.Label(self.current_card, text="No weather loaded yet", bg=EMPTY_SCENE, fg=MUTED, font=(FONT, 13)).pack(anchor="w", pady=26)

    def render(self) -> None:
        forecast = self.forecast
        if forecast is None:
            return
        cur = forecast.current
        bg = scene_colour(cur.code, cur.is_day)
        chip = blend(bg, WHITE, 0.14)
        soft = blend(bg, WHITE, 0.78)
        self._paint_scene(bg)

        self._wipe(self.current_card)
        left = tk.Frame(self.current_card, bg=bg)
        left.pack(side="left")
        self._icon_label(left, icon_code(cur.code, cur.is_day), 92, bg).pack(side="left")
        text = tk.Frame(left, bg=bg)
        text.pack(side="left", padx=12)
        tk.Label(text, text=forecast.location.title, font=(FONT, 13, "bold"), bg=bg, fg=WHITE).pack(anchor="w")
        tk.Label(text, text=format_temp(cur.temp_c, self.unit), font=(FONT, 34, "bold"), bg=bg, fg=WHITE).pack(anchor="w")
        other = "F" if self.unit == "C" else "C"
        tk.Label(text, text=f"{describe(cur.code)}   ({format_temp(cur.temp_c, other)})", font=(FONT, 11), bg=bg, fg=soft).pack(anchor="w")
        right = tk.Frame(self.current_card, bg=chip, padx=16, pady=10)
        right.pack(side="right")
        for line in (
            f"Feels like   {format_temp(cur.feels_like_c, self.unit)}",
            f"Humidity   {cur.humidity}%",
            f"Wind   {cur.wind_kmh:.1f} km/h  ({kmh_to_mph(cur.wind_kmh):.1f} mph)",
        ):
            tk.Label(right, text=line, font=(FONT, 10), bg=chip, fg=WHITE, anchor="w").pack(anchor="w", pady=1)

        self._wipe(self.hourly_box)
        for column, hour in enumerate(forecast.hourly):
            cell = tk.Frame(self.hourly_box, bg=chip, padx=6, pady=6)
            cell.grid(row=0, column=column, padx=4, sticky="nsew")
            tk.Label(cell, text=hour.label, font=(FONT, 9, "bold"), bg=chip, fg=soft).pack()
            self._icon_label(cell, icon_code(hour.code, hour.is_day), 38, chip).pack()
            tk.Label(cell, text=format_temp_short(hour.temp_c, self.unit), font=(FONT, 11, "bold"), bg=chip, fg=WHITE).pack()
            self.hourly_box.columnconfigure(column, weight=1, uniform="hour")

        self._wipe(self.daily_box)
        for column, day in enumerate(forecast.daily):
            cell = tk.Frame(self.daily_box, bg=chip, padx=6, pady=6)
            cell.grid(row=0, column=column, padx=4, sticky="nsew")
            tk.Label(cell, text=day.label, font=(FONT, 9, "bold"), bg=chip, fg=soft).pack()
            self._icon_label(cell, icon_code(day.code, True), 38, chip).pack()
            tk.Label(cell, text=f"{format_temp_short(day.max_c, self.unit)} / {format_temp_short(day.min_c, self.unit)}",
                     font=(FONT, 11, "bold"), bg=chip, fg=WHITE).pack()
            tk.Label(cell, text=describe(day.code), font=(FONT, 8), bg=chip, fg=soft, wraplength=100).pack()
            self.daily_box.columnconfigure(column, weight=1, uniform="day")

        self.hourly_caption.grid(row=1, column=0, sticky="ew", pady=(14, 4))
        self.hourly_box.grid(row=2, column=0, sticky="ew")
        self.daily_caption.grid(row=3, column=0, sticky="ew", pady=(14, 4))
        self.daily_box.grid(row=4, column=0, sticky="ew")


def _enable_high_dpi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001 - cosmetic only
            pass


def main() -> int:
    _enable_high_dpi()
    root = tk.Tk()
    root.title("Weather App")
    WeatherApp(root).pack(fill="both", expand=True)
    root.minsize(740, 600)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
