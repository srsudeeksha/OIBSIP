"""BMI Calculator - tkinter GUI (Oasis Infobyte, Python Programming Task 2, Advanced tier).

Run:  python app.py            (history is kept in bmi_records.db next to this file)
      python app.py --db my.db (use another database file)
"""
from __future__ import annotations

import argparse
import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from bmi_core import (  # noqa: E402
    BMIDatabase,
    DatabaseError,
    ValidationError,
    calculate_bmi,
    classify_bmi,
    normalise_name,
    parse_height,
    parse_weight,
)
from theme import (  # noqa: E402
    BG, BORDER, CARD, ERROR, FONT, MUTED, STRIPE, SUCCESS, TEXT,
    apply_theme, banner, card,
)

DEFAULT_DB = Path(__file__).with_name("bmi_records.db")
ACCENT = "#4f46e5"
CATEGORY_COLOURS = {
    "Underweight": "#1d6fb8",  # blue
    "Normal": "#1e8e3e",       # green
    "Overweight": "#e07b00",   # orange
    "Obese": "#c5221f",        # red
}
NEUTRAL = "#8a8fa3"
STATUS_STYLE = {"ok": (SUCCESS, "✓  "), "error": (ERROR, "⚠  "), "info": (MUTED, "")}


class BMIGauge(tk.Canvas):
    """A colour bar (Underweight -> Obese) with a marker showing where the current BMI falls."""

    LOW, HIGH = 12.0, 42.0
    ZONES = ((12.0, 18.5, "Underweight"), (18.5, 25.0, "Normal"), (25.0, 30.0, "Overweight"), (30.0, 42.0, "Obese"))

    def __init__(self, master: tk.Misc, height: int = 76):
        super().__init__(master, height=height, bg=CARD, highlightthickness=0)
        self.bmi: float | None = None
        self.bind("<Configure>", lambda _e: self.redraw())

    def set_value(self, bmi: float | None) -> None:
        self.bmi = bmi
        self.redraw()

    def _x(self, value: float, width: int, pad: int = 8) -> float:
        value = min(self.HIGH, max(self.LOW, value))
        return pad + (value - self.LOW) / (self.HIGH - self.LOW) * (width - 2 * pad)

    def redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        if width < 40:
            return
        top = 24
        for low, high, category in self.ZONES:
            self.create_rectangle(self._x(low, width), top, self._x(high, width), top + 12,
                                  fill=CATEGORY_COLOURS[category] if self.bmi is not None else "#d9dce8", outline=CARD, width=2)
        for tick in (18.5, 25.0, 30.0):
            self.create_text(self._x(tick, width), top + 24, text=f"{tick:g}", fill=MUTED, font=(FONT, 8))
        for low, high, category in self.ZONES:   # zone names, centred under each coloured segment
            self.create_text((self._x(low, width) + self._x(high, width)) / 2, top + 42, text=category,
                             fill=CATEGORY_COLOURS[category], font=(FONT, 8, "bold"))
        if self.bmi is not None:
            x = self._x(self.bmi, width)
            self.create_polygon(x - 7, 6, x + 7, 6, x, 20, fill=TEXT, outline=CARD)


class BMIApp(ttk.Frame):
    """The main window: input form, colour-coded result with gauge, per-user history and a trend chart."""

    def __init__(self, master: tk.Misc, db: BMIDatabase):
        super().__init__(master)
        apply_theme(master, ACCENT)
        self.db = db
        self.name_var = tk.StringVar()
        self.weight_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.bmi_var = tk.StringVar(value="--")
        self.category_var = tk.StringVar(value="Enter your details")
        self.status_var = tk.StringVar(value="Type a name, weight (kg) and height (m), then press Calculate.")
        self.history_title = tk.StringVar(value="History")
        self.trend_window: tk.Toplevel | None = None
        self._build()
        self._refresh_users()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        banner(self, "BMI Calculator", "Calculate, classify and track Body Mass Index for several users", ACCENT).grid(
            row=0, column=0, sticky="ew")
        body = ttk.Frame(self, padding=(20, 16, 20, 4))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1, uniform="cols")
        body.columnconfigure(1, weight=1, uniform="cols")

        # --- details card
        details = card(body, "Your details")
        details.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form = details.body
        for row, text in enumerate(("Name", "Weight (kg)", "Height (m)")):
            ttk.Label(form, text=text, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=5)
        self.name_box = ttk.Combobox(form, textvariable=self.name_var, width=22)
        self.name_box.grid(row=0, column=1, sticky="ew", pady=5, padx=(12, 0))
        self.weight_entry = ttk.Entry(form, textvariable=self.weight_var, width=24)
        self.weight_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=(12, 0))
        self.height_entry = ttk.Entry(form, textvariable=self.height_var, width=24)
        self.height_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=(12, 0))
        form.columnconfigure(1, weight=1)
        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.calc_button = ttk.Button(buttons, text="Calculate", style="Accent.TButton", command=self.calculate)
        self.calc_button.pack(side="left")
        ttk.Button(buttons, text="Clear", style="Secondary.TButton", command=self.clear).pack(side="left", padx=8)
        self.trend_button = ttk.Button(buttons, text="View BMI trend", style="Secondary.TButton", command=self.show_trend)
        self.trend_button.pack(side="left")

        # --- result card
        result = card(body, "Result")
        result.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        res = result.body
        self.value_label = tk.Label(res, textvariable=self.bmi_var, font=(FONT, 38, "bold"), bg=CARD, fg=TEXT)
        self.value_label.pack()
        self.category_label = tk.Label(res, textvariable=self.category_var, font=(FONT, 12, "bold"), fg="white", bg=NEUTRAL,
                                       padx=22, pady=5)
        self.category_label.pack(pady=(2, 6))
        self.gauge = BMIGauge(res)
        self.gauge.pack(fill="x")

        # --- history card
        history = card(self, None)
        history.grid(row=2, column=0, sticky="nsew", padx=20, pady=(12, 0))
        hist = history.body
        tk.Label(hist, textvariable=self.history_title, bg=CARD, fg=TEXT, font=(FONT, 11, "bold")).pack(anchor="w", pady=(0, 6))
        table = tk.Frame(hist, bg=CARD)
        table.pack(fill="both", expand=True)
        columns = ("when", "weight", "height", "bmi", "category")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", height=5)
        for key, title, width in (("when", "Date & time", 170), ("weight", "Weight (kg)", 95), ("height", "Height (m)", 95),
                                  ("bmi", "BMI", 70), ("category", "Category", 110)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center")
        for category, colour in CATEGORY_COLOURS.items():
            self.tree.tag_configure(category, foreground=colour)
        self.tree.tag_configure("stripe", background=STRIPE)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.status_label = tk.Label(self, textvariable=self.status_var, anchor="w", justify="left", wraplength=640,
                                     bg=BG, fg=MUTED, font=(FONT, 10), padx=22, pady=10)
        self.status_label.grid(row=3, column=0, sticky="ew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        for widget in (self.weight_entry, self.height_entry, self.name_box):
            widget.bind("<Return>", lambda _e: self.calculate())
        self.name_box.bind("<<ComboboxSelected>>", self.refresh_history)
        self.name_box.bind("<FocusOut>", self.refresh_history)

    # ------------------------------------------------------------------ helpers
    def _set_status(self, message: str, kind: str = "info") -> None:
        colour, prefix = STATUS_STYLE[kind]
        self.status_var.set(prefix + message)
        self.status_label.configure(fg=colour)

    def _show_result(self, bmi: float | None, category: str | None) -> None:
        if bmi is None or category is None:
            self.bmi_var.set("--")
            self.category_var.set("Enter your details")
            self.category_label.configure(bg=NEUTRAL)
            self.value_label.configure(fg=TEXT)
            self.gauge.set_value(None)
            return
        self.bmi_var.set(f"{bmi:.2f}")
        self.category_var.set(category)
        self.category_label.configure(bg=CATEGORY_COLOURS[category])
        self.value_label.configure(fg=CATEGORY_COLOURS[category])
        self.gauge.set_value(bmi)

    def _refresh_users(self) -> None:
        try:
            self.name_box["values"] = self.db.list_users()
        except DatabaseError as exc:
            self._set_status(str(exc), "error")

    def refresh_history(self, *_event) -> None:
        name = " ".join(self.name_var.get().split())
        self.tree.delete(*self.tree.get_children())
        records = []
        if name:
            try:
                records = self.db.get_history(name)
            except DatabaseError as exc:
                self._set_status(str(exc), "error")
        if records:
            self.history_title.set(f"History for {records[-1].user_name}  -  {len(records)} record{'s' if len(records) != 1 else ''}")
            for index, rec in enumerate(reversed(records)):  # newest first
                tags = (rec.category, "stripe") if index % 2 else (rec.category,)
                self.tree.insert("", "end", tags=tags, values=(
                    rec.recorded_at.strftime("%d %b %Y  %H:%M:%S"), f"{rec.weight_kg:g}", f"{rec.height_m:g}",
                    f"{rec.bmi:.2f}", rec.category))
        else:
            self.history_title.set("History  -  no saved records for this user yet" if name else "History")

    def _read_inputs(self):
        """Validate the three fields in order; on the first problem focus that field and return None."""
        steps = ((normalise_name, self.name_var, self.name_box),
                 (parse_weight, self.weight_var, self.weight_entry),
                 (parse_height, self.height_var, self.height_entry))
        values = []
        for parser, variable, widget in steps:
            try:
                values.append(parser(variable.get()))
            except ValidationError as exc:
                self._show_result(None, None)
                self._set_status(str(exc), "error")
                widget.focus_set()
                return None
        return tuple(values)

    # ------------------------------------------------------------------ actions
    def calculate(self) -> None:
        inputs = self._read_inputs()
        if inputs is None:
            return
        name, weight, height = inputs
        bmi = calculate_bmi(weight, height)
        category = classify_bmi(bmi)
        self._show_result(bmi, category)
        try:
            self.db.add_record(name, weight, height, bmi, category)
        except DatabaseError as exc:
            self._set_status(f"BMI calculated, but it could not be saved: {exc}", "error")
            return
        self._refresh_users()
        self.name_var.set(name)
        self.refresh_history()
        self._set_status(f"Saved for {name}: BMI {bmi:.2f} ({category}).", "ok")

    def clear(self) -> None:
        self.weight_var.set("")
        self.height_var.set("")
        self._show_result(None, None)
        self._set_status("Cleared. Enter new measurements and press Calculate.", "info")
        self.weight_entry.focus_set()

    def show_trend(self) -> tk.Toplevel | None:
        name = " ".join(self.name_var.get().split())
        if not name:
            self._set_status("Choose or type a user name first to see their BMI trend.", "error")
            self.name_box.focus_set()
            return None
        try:
            records = self.db.get_history(name)
        except DatabaseError as exc:
            self._set_status(str(exc), "error")
            return None
        if not records:
            self._set_status(f"No saved records for '{name}' yet - calculate a BMI first.", "error")
            return None
        if self.trend_window is not None and self.trend_window.winfo_exists():
            self.trend_window.destroy()
        win = tk.Toplevel(self)
        win.title(f"BMI trend - {records[-1].user_name}")
        win.configure(bg=CARD)
        figure = build_trend_figure(records)
        canvas = FigureCanvasTkAgg(figure, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.trend_window = win
        self._set_status(f"Showing the BMI trend for {records[-1].user_name} ({len(records)} records).", "info")
        return win


def build_trend_figure(records) -> Figure:
    """Line chart of BMI over time for one user, with the four health categories shaded."""
    figure = Figure(figsize=(7.2, 4.4), dpi=100, facecolor=CARD)
    ax = figure.add_subplot(111)
    ax.set_facecolor(CARD)
    xs = list(range(1, len(records) + 1))
    ys = [r.bmi for r in records]
    low, high = min(15.0, min(ys) - 1), max(32.0, max(ys) + 1)
    for lo, hi, category in ((low, 18.5, "Underweight"), (18.5, 25, "Normal"), (25, 30, "Overweight"), (30, high, "Obese")):
        ax.axhspan(lo, hi, color=CATEGORY_COLOURS[category], alpha=0.12, linewidth=0)
        ax.text(len(records) + 0.45, (lo + hi) / 2, category, va="center", ha="left", fontsize=9, fontweight="bold",
                color=CATEGORY_COLOURS[category], clip_on=False)
    ax.plot(xs, ys, linewidth=2.5, color=ACCENT, zorder=3)
    ax.scatter(xs, ys, s=70, color=[CATEGORY_COLOURS[r.category] for r in records], edgecolor="white", linewidth=1.5, zorder=4)
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0, 11), ha="center", fontsize=9, fontweight="bold", color=TEXT)
    step = max(1, math.ceil(len(records) / 10))
    shown = xs[::step]
    ax.set_xticks(shown)
    ax.set_xticklabels([records[i - 1].recorded_at.strftime("%d %b\n%H:%M") for i in shown], fontsize=8, color=MUTED)
    ax.tick_params(axis="y", colors=MUTED, labelsize=9)
    ax.set_xlim(0.6, len(records) + 0.4)
    ax.set_ylim(low, high)
    ax.set_ylabel("BMI", color=MUTED)
    ax.set_title(f"BMI trend for {records[-1].user_name}", fontsize=13, fontweight="bold", color=TEXT, loc="left", pad=12)
    ax.grid(True, axis="y", color=BORDER, linewidth=0.8)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    figure.subplots_adjust(left=0.09, right=0.86, top=0.88, bottom=0.15)
    return figure


def _enable_high_dpi() -> None:
    """Keep the window sharp on Windows displays that use scaling."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001 - purely cosmetic
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BMI Calculator with per-user history and trend chart")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite file used to store the history")
    args = parser.parse_args(argv)
    _enable_high_dpi()
    root = tk.Tk()
    root.title("BMI Calculator")
    try:
        db = BMIDatabase(args.db)
    except DatabaseError as exc:
        messagebox.showerror("BMI Calculator", f"The history database could not be opened.\n\n{exc}")
        root.destroy()
        return 1
    BMIApp(root, db).pack(fill="both", expand=True)
    root.minsize(700, 600)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
