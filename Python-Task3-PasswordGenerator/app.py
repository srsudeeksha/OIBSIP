"""Random Password Generator - tkinter GUI (Oasis Infobyte, Python Programming Task 3, Advanced tier).

Run:  python app.py
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

import pyperclip

from password_core import (
    AMBIGUOUS,
    HISTORY_SIZE,
    MAX_LENGTH,
    MIN_LENGTH,
    Options,
    PasswordError,
    PasswordHistory,
    generate_password,
    parse_length,
    password_strength,
)
from theme import BG, CARD, ERROR, FONT, MONO, MUTED, SUCCESS, TEXT, apply_theme, banner, card, lighten

ACCENT = "#0f766e"   # teal
STRENGTH_COLOURS = {"Weak": "#c5221f", "Medium": "#d97706", "Strong": "#1e8e3e"}
STATUS_STYLE = {"ok": (SUCCESS, "✓  "), "error": (ERROR, "⚠  "), "info": (MUTED, "")}
SLIDER_MAX = 64


def copy_to_clipboard(text: str, tk_widget: tk.Misc | None = None) -> str:
    """Copy with pyperclip; fall back to tkinter's own clipboard. Returns which method worked."""
    try:
        pyperclip.copy(text)
        return "pyperclip"
    except pyperclip.PyperclipException:
        if tk_widget is None:
            raise
        tk_widget.clipboard_clear()
        tk_widget.clipboard_append(text)
        tk_widget.update()
        return "tkinter"


class PasswordApp(ttk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master)
        style = apply_theme(master, ACCENT)
        for label, colour in STRENGTH_COLOURS.items():
            style.configure(f"{label}.Horizontal.TProgressbar", background=colour, troughcolor="#e3e7f1", bordercolor=CARD,
                            lightcolor=colour, darkcolor=colour, thickness=14)
        self.history = PasswordHistory()
        self.length_var = tk.StringVar(value="16")
        self.slider_var = tk.IntVar(value=16)
        self.lower_var = tk.BooleanVar(value=True)
        self.upper_var = tk.BooleanVar(value=True)
        self.numbers_var = tk.BooleanVar(value=True)
        self.symbols_var = tk.BooleanVar(value=True)
        self.ambiguous_var = tk.BooleanVar(value=False)
        self.password_var = tk.StringVar()
        self.strength_var = tk.StringVar(value="Strength: -")
        self.status_var = tk.StringVar(value="Choose your options and press Generate. The password is copied automatically.")
        self._build()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        banner(self, "Password Generator", "Strong random passwords made with Python's secrets module", ACCENT).grid(
            row=0, column=0, sticky="ew")
        body = ttk.Frame(self, padding=(20, 14, 20, 0))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        # --- options
        options = card(body, "Options")
        options.grid(row=0, column=0, sticky="ew")
        opt = options.body
        opt.columnconfigure(1, weight=1)
        ttk.Label(opt, text="Length", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        self.slider = ttk.Scale(opt, from_=MIN_LENGTH, to=SLIDER_MAX, variable=self.slider_var, orient="horizontal",
                                command=self._on_slider)
        self.slider.grid(row=0, column=1, sticky="ew", padx=14)
        self.spinbox = ttk.Spinbox(opt, from_=MIN_LENGTH, to=MAX_LENGTH, textvariable=self.length_var, width=5,
                                   command=self._on_spinbox, justify="center")
        self.spinbox.grid(row=0, column=2)
        self.spinbox.bind("<KeyRelease>", lambda _e: self._on_spinbox())
        self.spinbox.bind("<Return>", lambda _e: self.generate())
        checks = tk.Frame(opt, bg=CARD)
        checks.grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.upper_check = ttk.Checkbutton(checks, text="Uppercase  A-Z", variable=self.upper_var, style="Card.TCheckbutton")
        self.lower_check = ttk.Checkbutton(checks, text="Lowercase  a-z", variable=self.lower_var, style="Card.TCheckbutton")
        self.numbers_check = ttk.Checkbutton(checks, text="Numbers  0-9", variable=self.numbers_var, style="Card.TCheckbutton")
        self.symbols_check = ttk.Checkbutton(checks, text="Symbols  !@#$%", variable=self.symbols_var, style="Card.TCheckbutton")
        self.ambiguous_check = ttk.Checkbutton(checks, text=f"Exclude ambiguous characters  ({' '.join(AMBIGUOUS)})",
                                               variable=self.ambiguous_var, style="Card.TCheckbutton")
        self.upper_check.grid(row=0, column=0, sticky="w", padx=(0, 28), pady=3)
        self.lower_check.grid(row=0, column=1, sticky="w", padx=(0, 28), pady=3)
        self.numbers_check.grid(row=1, column=0, sticky="w", padx=(0, 28), pady=3)
        self.symbols_check.grid(row=1, column=1, sticky="w", pady=3)
        self.ambiguous_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=3)

        # --- actions
        buttons = ttk.Frame(body)
        buttons.grid(row=1, column=0, sticky="w", pady=12)
        self.generate_button = ttk.Button(buttons, text="Generate password", style="Accent.TButton", command=self.generate)
        self.generate_button.pack(side="left")
        self.copy_button = ttk.Button(buttons, text="Copy to clipboard", style="Secondary.TButton", command=self.copy_current)
        self.copy_button.pack(side="left", padx=10)

        # --- result
        result = card(body, None)
        result.grid(row=2, column=0, sticky="ew")
        res = result.body
        self.password_entry = tk.Entry(res, textvariable=self.password_var, font=(MONO, 18, "bold"), state="readonly",
                                       justify="center", readonlybackground="#f6f8fc", fg=TEXT, relief="flat", bd=0,
                                       highlightthickness=1, highlightbackground="#d3d9e8", highlightcolor=ACCENT)
        self.password_entry.pack(fill="x", ipady=10)
        bar_row = tk.Frame(res, bg=CARD)
        bar_row.pack(fill="x", pady=(12, 0))
        self.strength_bar = ttk.Progressbar(bar_row, maximum=100, style="Weak.Horizontal.TProgressbar")
        self.strength_bar.pack(side="left", fill="x", expand=True)
        self.strength_label = tk.Label(bar_row, textvariable=self.strength_var, font=(FONT, 10, "bold"), width=26, anchor="e",
                                       bg=CARD, fg=MUTED)
        self.strength_label.pack(side="left", padx=(12, 0))

        # --- history
        history = card(body, f"Last {HISTORY_SIZE} passwords this session  (kept in memory only - never saved to disk)")
        history.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        self.history_list = tk.Listbox(history.body, height=HISTORY_SIZE, font=(MONO, 11), activestyle="none", exportselection=False,
                                       relief="flat", bd=0, highlightthickness=1, highlightbackground="#e3e7f1",
                                       selectbackground=lighten(ACCENT, 0.8), selectforeground=TEXT, bg="#fbfcfe", fg=TEXT)
        self.history_list.pack(fill="both", expand=True)
        self.history_list.bind("<Double-Button-1>", self._copy_from_history)

        self.status_label = tk.Label(self, textvariable=self.status_var, anchor="w", justify="left", wraplength=640, bg=BG,
                                     fg=MUTED, font=(FONT, 10), padx=22, pady=10)
        self.status_label.grid(row=2, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        body.rowconfigure(3, weight=1)

    # ------------------------------------------------------------------ helpers
    def _set_status(self, message: str, kind: str = "info") -> None:
        colour, prefix = STATUS_STYLE[kind]
        self.status_var.set(prefix + message)
        self.status_label.configure(fg=colour)

    def _on_slider(self, value: str) -> None:
        self.length_var.set(str(int(float(value))))

    def _on_spinbox(self) -> None:
        try:
            self.slider_var.set(min(SLIDER_MAX, max(MIN_LENGTH, int(self.length_var.get()))))
        except ValueError:
            pass  # half-typed text; generate() reports it properly

    def current_options(self) -> Options:
        return Options(
            length=parse_length(self.length_var.get()),
            lowercase=self.lower_var.get(), uppercase=self.upper_var.get(),
            numbers=self.numbers_var.get(), symbols=self.symbols_var.get(),
            exclude_ambiguous=self.ambiguous_var.get(),
        )

    def _show_password(self, password: str) -> None:
        self.password_var.set(password)
        label, percent, bits = password_strength(password)
        self.strength_bar.configure(style=f"{label}.Horizontal.TProgressbar")
        self.strength_bar["value"] = percent
        self.strength_var.set(f"Strength: {label}  (~{bits:.0f} bits)")
        self.strength_label.configure(fg=STRENGTH_COLOURS[label])

    def _refresh_history(self) -> None:
        self.history_list.delete(0, "end")
        for password in self.history.items():
            self.history_list.insert("end", "  " + password)

    # ------------------------------------------------------------------ actions
    def generate(self) -> str | None:
        try:
            options = self.current_options()
            password = generate_password(options)
        except PasswordError as exc:
            self._set_status(str(exc), "error")
            return None
        self._show_password(password)
        self.history.add(password)
        self._refresh_history()
        self._copy(password, prefix=f"Generated a {len(password)}-character password. ")
        return password

    def copy_current(self) -> None:
        password = self.password_var.get()
        if not password:
            self._set_status("Nothing to copy yet - generate a password first.", "error")
            return
        self._copy(password)

    def _copy_from_history(self, _event=None) -> None:
        selection = self.history_list.curselection()
        if selection:
            self._copy(self.history_list.get(selection[0]).strip(), prefix="History item ")

    def _copy(self, password: str, prefix: str = "") -> None:
        try:
            copy_to_clipboard(password, self)
        except Exception as exc:  # noqa: BLE001 - clipboard problems must never crash the app
            self._set_status(f"{prefix}Could not copy automatically ({exc}). Select the text and press Ctrl+C.", "error")
            return
        self._set_status(f"{prefix}Copied to clipboard.", "ok")


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
    root.title("Random Password Generator")
    PasswordApp(root).pack(fill="both", expand=True)
    root.minsize(660, 600)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
