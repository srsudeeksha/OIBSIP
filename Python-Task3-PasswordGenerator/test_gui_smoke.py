"""GUI smoke tests: drive the real tkinter window through its public methods (needs a desktop session)."""
import tkinter as tk

import pytest

import app as app_module
from app import PasswordApp
from password_core import AMBIGUOUS


@pytest.fixture(scope="module")
def root():
    # One Tk root for the whole module - creating many roots in one process is flaky on Windows.
    try:
        window_root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display available: {exc}")
    window_root.withdraw()
    yield window_root
    window_root.destroy()


@pytest.fixture()
def gui(root, monkeypatch):
    # NOTE: not called "app" - the pytest-flask plugin treats a fixture of that name as a Flask app.
    copied = []
    monkeypatch.setattr(app_module, "copy_to_clipboard", lambda text, widget=None: copied.append(text) or "fake")
    window = PasswordApp(root)
    window.copied = copied
    window.pack()
    yield window
    window.destroy()


def test_generate_shows_password_strength_and_copies_automatically(gui):
    gui.length_var.set("20")
    password = gui.generate()
    assert len(password) == 20
    assert gui.password_var.get() == password
    assert gui.copied == [password]
    assert "Copied to clipboard" in gui.status_var.get()
    assert gui.strength_var.get().startswith("Strength: Strong")
    assert gui.strength_bar["value"] > 80


def test_slider_and_spinbox_stay_in_sync(gui):
    gui._on_slider("30.4")
    assert gui.length_var.get() == "30"
    gui.length_var.set("12")
    gui._on_spinbox()
    assert gui.slider_var.get() == 12


@pytest.mark.parametrize("text", ["", "abc", "5", "500"])
def test_bad_length_shows_error_in_the_window(gui, text):
    gui.length_var.set(text)
    assert gui.generate() is None
    assert gui.status_label.cget("fg") == "#c5221f"
    assert gui.password_var.get() == ""
    assert gui.copied == []


def test_fewer_than_two_types_shows_error(gui):
    gui.upper_var.set(False)
    gui.numbers_var.set(False)
    gui.symbols_var.set(False)
    assert gui.generate() is None
    assert "at least 2" in gui.status_var.get()


def test_exclude_ambiguous_checkbox_is_honoured(gui):
    gui.ambiguous_var.set(True)
    gui.length_var.set("64")
    for _ in range(50):
        assert not set(gui.generate()) & set(AMBIGUOUS)


def test_history_shows_last_five_newest_first(gui):
    made = [gui.generate() for _ in range(7)]
    shown = [line.strip() for line in gui.history_list.get(0, "end")]   # the list adds a little left padding
    assert shown == list(reversed(made))[:5]


def test_weak_password_gets_a_weak_label(gui):
    gui.upper_var.set(False)
    gui.symbols_var.set(False)
    gui.length_var.set("8")
    gui.generate()
    assert gui.strength_var.get().startswith("Strength: Weak")


def test_copy_button_needs_a_password_first(gui):
    gui.copy_current()
    assert "Nothing to copy" in gui.status_var.get()
    password = gui.generate()
    gui.copied.clear()
    gui.copy_current()
    assert gui.copied == [password]
