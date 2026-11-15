"""Shared look-and-feel for the GUI: colours, fonts and ttk styles (plain tkinter - no extra packages).

The same small file is used by all three projects; only the accent colour passed to ``apply_theme`` differs.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

FONT = "Segoe UI"
MONO = "Consolas"

BG = "#f3f5fb"        # window background
CARD = "#ffffff"      # card background
BORDER = "#dfe3ee"
TEXT = "#1f2937"
MUTED = "#6b7280"
ERROR = "#c5221f"
SUCCESS = "#1e8e3e"
STRIPE = "#f7f8fd"    # alternate table row


def _rgb(colour: str) -> tuple[int, int, int]:
    colour = colour.lstrip("#")
    return int(colour[0:2], 16), int(colour[2:4], 16), int(colour[4:6], 16)


def blend(first: str, second: str, amount: float) -> str:
    """Mix two #rrggbb colours: amount 0 = first, 1 = second."""
    (r1, g1, b1), (r2, g2, b2) = _rgb(first), _rgb(second)
    mixed = (round(r1 + (r2 - r1) * amount), round(g1 + (g2 - g1) * amount), round(b1 + (b2 - b1) * amount))
    return "#%02x%02x%02x" % mixed


def lighten(colour: str, amount: float = 0.2) -> str:
    return blend(colour, "#ffffff", amount)


def darken(colour: str, amount: float = 0.15) -> str:
    return blend(colour, "#000000", amount)


def apply_theme(root: tk.Misc, accent: str) -> ttk.Style:
    """Configure every ttk widget style used by the apps."""
    style = ttk.Style(root)
    style.theme_use("clam")
    if isinstance(root, (tk.Tk, tk.Toplevel)):
        root.configure(bg=BG)
    style.configure(".", background=BG, foreground=TEXT, font=(FONT, 10), focuscolor=BG)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT)
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED)

    # buttons: a filled accent button and a quiet outlined one
    style.configure("Accent.TButton", background=accent, foreground="white", bordercolor=accent, lightcolor=accent,
                    darkcolor=accent, borderwidth=0, focusthickness=0, relief="flat", padding=(20, 9), font=(FONT, 10, "bold"))
    style.map("Accent.TButton",
              background=[("disabled", "#b9bfd0"), ("pressed", darken(accent, 0.22)), ("active", darken(accent, 0.1))],
              bordercolor=[("disabled", "#b9bfd0"), ("pressed", darken(accent, 0.22)), ("active", darken(accent, 0.1))],
              lightcolor=[("pressed", darken(accent, 0.22)), ("active", darken(accent, 0.1))],
              darkcolor=[("pressed", darken(accent, 0.22)), ("active", darken(accent, 0.1))],
              foreground=[("disabled", "white")])
    style.configure("Secondary.TButton", background="#f1f3fa", foreground=TEXT, bordercolor="#c5cbdd", lightcolor="#f1f3fa",
                    darkcolor="#f1f3fa", borderwidth=1, focusthickness=0, relief="flat", padding=(16, 8), font=(FONT, 10))
    style.map("Secondary.TButton", background=[("pressed", "#dfe3f1"), ("active", "#e8ebf6")],
              lightcolor=[("pressed", "#dfe3f1"), ("active", "#e8ebf6")], darkcolor=[("pressed", "#dfe3f1"), ("active", "#e8ebf6")],
              bordercolor=[("active", accent)], foreground=[("disabled", MUTED)])

    # inputs get a thin border that turns accent-coloured while typing
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, fieldbackground="white", background="white", foreground=TEXT, bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER, padding=6, arrowcolor=MUTED, insertcolor=TEXT)
        style.map(name, bordercolor=[("focus", accent)], lightcolor=[("focus", accent)], darkcolor=[("focus", accent)],
                  fieldbackground=[("readonly", "white")])
    style.configure("Card.TCheckbutton", background=CARD, foreground=TEXT, font=(FONT, 10), focuscolor=CARD)
    style.map("Card.TCheckbutton", background=[("active", CARD)], indicatorcolor=[("selected", accent), ("!selected", "white")])
    style.configure("Horizontal.TScale", background=CARD, troughcolor="#e3e7f1", bordercolor=CARD, lightcolor=accent, darkcolor=accent)
    style.map("Horizontal.TScale", background=[("active", darken(accent, 0.1)), ("!active", accent)])

    # tables
    style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=30, borderwidth=0, font=(FONT, 10))
    style.map("Treeview", background=[("selected", lighten(accent, 0.82))], foreground=[("selected", TEXT)])
    style.configure("Treeview.Heading", background="#eceff8", foreground=TEXT, relief="flat", borderwidth=0, padding=(6, 8),
                    font=(FONT, 10, "bold"))
    style.map("Treeview.Heading", background=[("active", "#e3e7f4")])
    style.configure("Vertical.TScrollbar", background="#d5d9e6", troughcolor=CARD, bordercolor=CARD, arrowcolor=MUTED, relief="flat")
    return style


def banner(parent: tk.Misc, title: str, subtitle: str, accent: str) -> tk.Frame:
    """Coloured header strip with the app name."""
    frame = tk.Frame(parent, bg=accent, padx=24, pady=14)
    tk.Label(frame, text=title, bg=accent, fg="white", font=(FONT, 20, "bold")).pack(anchor="w")
    tk.Label(frame, text=subtitle, bg=accent, fg=lighten(accent, 0.8), font=(FONT, 10)).pack(anchor="w")
    return frame


def card(parent: tk.Misc, title: str | None = None, padding: int = 16) -> tk.Frame:
    """White panel with a thin border; optional bold title. Put your widgets in the returned frame."""
    outer = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
    inner = tk.Frame(outer, bg=CARD, padx=padding, pady=padding - 4)
    inner.pack(fill="both", expand=True)
    if title:
        tk.Label(inner, text=title, bg=CARD, fg=TEXT, font=(FONT, 11, "bold")).pack(anchor="w", pady=(0, 8))
    content = tk.Frame(inner, bg=CARD)          # a separate frame so callers may use grid() or pack() freely
    content.pack(fill="both", expand=True)
    outer.body = content  # type: ignore[attr-defined]
    return outer
