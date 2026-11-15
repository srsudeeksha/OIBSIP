"""GUI smoke tests: drive the real tkinter window through its public methods (needs a desktop session)."""
import tkinter as tk

import pytest

from app import CATEGORY_COLOURS, BMIApp
from bmi_core import BMIDatabase


@pytest.fixture(scope="module")
def root():
    # One Tk root for the whole module: creating and destroying many roots in a single process is
    # flaky on Windows ("Tcl wasn't installed properly"), so every test gets a fresh BMIApp frame instead.
    try:
        window_root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display available: {exc}")
    window_root.withdraw()
    yield window_root
    window_root.destroy()


@pytest.fixture()
def gui(root, tmp_path):
    # NOTE: not called "app" on purpose - the pytest-flask plugin treats a fixture of that name as a Flask app.
    window = BMIApp(root, BMIDatabase(tmp_path / "gui.db"))
    window.pack()
    yield window
    if window.trend_window is not None and window.trend_window.winfo_exists():
        window.trend_window.destroy()
    window.destroy()


def fill(gui, name, weight, height):
    gui.name_var.set(name)
    gui.weight_var.set(weight)
    gui.height_var.set(height)


def test_calculate_shows_colour_coded_result_and_saves(gui):
    fill(gui, "Asha", "70", "1.75")
    gui.calculate()
    assert gui.bmi_var.get() == "22.86"
    assert gui.category_var.get() == "Normal"
    assert gui.category_label.cget("bg") == CATEGORY_COLOURS["Normal"]
    assert len(gui.tree.get_children()) == 1
    assert "Saved for Asha" in gui.status_var.get()


def test_obese_is_red(gui):
    fill(gui, "Asha", "110", "1.70")
    gui.calculate()
    assert gui.category_var.get() == "Obese"
    assert gui.category_label.cget("bg") == CATEGORY_COLOURS["Obese"]


@pytest.mark.parametrize("weight,height", [("abc", "1.7"), ("-5", "1.7"), ("70", ""), ("70", "170")])
def test_bad_input_shows_error_in_the_window_and_saves_nothing(gui, weight, height):
    fill(gui, "Asha", weight, height)
    gui.calculate()
    assert gui.bmi_var.get() == "--"
    assert gui.status_label.cget("fg") == "#c5221f"
    assert gui.db.get_history("Asha") == []


def test_two_users_keep_separate_histories(gui):
    fill(gui, "Asha", "70", "1.75")
    gui.calculate()
    fill(gui, "Ravi", "90", "1.80")
    gui.calculate()
    assert len(gui.tree.get_children()) == 1  # only Ravi's rows are shown
    gui.name_var.set("Asha")
    gui.refresh_history()
    assert len(gui.tree.get_children()) == 1
    assert set(gui.name_box["values"]) == {"Asha", "Ravi"}


def test_trend_window_opens_only_with_records(gui):
    gui.name_var.set("Asha")
    assert gui.show_trend() is None
    fill(gui, "Asha", "70", "1.75")
    gui.calculate()
    fill(gui, "Asha", "68", "1.75")
    gui.calculate()
    assert gui.show_trend() is not None
