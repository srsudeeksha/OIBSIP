"""Unit tests for the password generator core and CLI.  Run with:  python -m pytest -q"""
import string

import pytest

import password_cli
from password_core import (
    AMBIGUOUS,
    CHARACTER_SETS,
    HISTORY_SIZE,
    SYMBOLS,
    Options,
    PasswordError,
    PasswordHistory,
    estimate_entropy_bits,
    generate_password,
    parse_length,
    password_strength,
)


# --------------------------------------------------------------------- length
@pytest.mark.parametrize("text,expected", [("8", 8), (" 16 ", 16), (128, 128)])
def test_valid_lengths(text, expected):
    assert parse_length(text) == expected


@pytest.mark.parametrize("text", ["", "  ", "abc", "7", "0", "-12", "129", "12.5"])
def test_invalid_lengths_are_rejected(text):
    with pytest.raises(PasswordError):
        parse_length(text)


# ------------------------------------------------------------------ generation
def test_default_password_has_requested_length_and_all_types():
    password = generate_password(Options(length=20))
    assert len(password) == 20
    assert any(c in string.ascii_lowercase for c in password)
    assert any(c in string.ascii_uppercase for c in password)
    assert any(c in string.digits for c in password)
    assert any(c in SYMBOLS for c in password)


@pytest.mark.parametrize("selected", [
    ("lowercase", "uppercase"), ("lowercase", "numbers"), ("uppercase", "symbols"),
    ("numbers", "symbols"), ("lowercase", "uppercase", "numbers"), tuple(CHARACTER_SETS),
])
def test_every_selected_type_is_present_and_nothing_else(selected):
    flags = {name: name in selected for name in CHARACTER_SETS}
    allowed = "".join(CHARACTER_SETS[name] for name in selected)
    for _ in range(300):  # random, so repeat many times; minimum length makes the guarantee hardest
        password = generate_password(Options(length=8, **flags))
        assert len(password) == 8
        assert set(password) <= set(allowed)
        for name in selected:
            assert any(c in CHARACTER_SETS[name] for c in password), (name, password)


def test_exclude_ambiguous_characters():
    for _ in range(300):
        password = generate_password(Options(length=24, exclude_ambiguous=True))
        assert not set(password) & set(AMBIGUOUS)


def test_ambiguous_characters_can_appear_when_not_excluded():
    seen = set()
    for _ in range(400):
        seen |= set(generate_password(Options(length=40)))
    assert set("0O1lI") <= seen


def test_fewer_than_two_types_is_rejected():
    with pytest.raises(PasswordError, match="at least 2"):
        generate_password(Options(length=12, lowercase=True, uppercase=False, numbers=False, symbols=False))
    with pytest.raises(PasswordError, match="at least 2"):
        generate_password(Options(length=12, lowercase=False, uppercase=False, numbers=False, symbols=False))


def test_too_short_is_rejected():
    with pytest.raises(PasswordError, match="at least 8"):
        generate_password(Options(length=7))


def test_passwords_are_not_repeated():
    batch = {generate_password(Options(length=16)) for _ in range(500)}
    assert len(batch) == 500


def test_generation_uses_secrets_not_random():
    import inspect

    import password_core

    source = inspect.getsource(password_core)
    assert "import secrets" in source and "import random" not in source


def test_characters_are_spread_not_always_at_the_start():
    firsts = {generate_password(Options(length=12))[0] in string.digits for _ in range(400)}
    assert firsts == {True, False}  # the guaranteed digit does not always sit in position 0


# -------------------------------------------------------------------- strength
def test_strength_labels():
    assert password_strength("abc12345")[0] == "Weak"            # 8 chars, 2 types  (~41 bits)
    assert password_strength("Abcdef12")[0] == "Weak"            # 8 chars, 3 types  (~48 bits)
    assert password_strength("Abcde1$x")[0] == "Medium"          # 8 chars, 4 types  (~52 bits)
    assert password_strength("Abcdef1234")[0] == "Medium"        # 10 chars, 3 types (~60 bits)
    assert password_strength("aB3$aB3$aB3$aB3$")[0] == "Strong"  # 16 chars, 4 types (~103 bits)
    assert password_strength("")[0] == "Weak"


def test_longer_and_more_varied_means_more_entropy():
    assert estimate_entropy_bits("abcdefgh") < estimate_entropy_bits("abcdefghijkl") < estimate_entropy_bits("abcDEFghi123")
    assert estimate_entropy_bits("") == 0


def test_strength_percent_is_capped():
    assert 0 <= password_strength("a")[1] <= 100
    assert password_strength("aB3$" * 20)[1] == 100


# --------------------------------------------------------------------- history
def test_history_keeps_last_five_newest_first():
    history = PasswordHistory()
    for i in range(8):
        history.add(f"pw{i}")
    assert history.items() == ["pw7", "pw6", "pw5", "pw4", "pw3"]
    assert len(history) == HISTORY_SIZE == 5
    history.clear()
    assert history.items() == []


def test_history_is_memory_only():
    import inspect

    import password_core

    source = inspect.getsource(password_core)
    assert "open(" not in source and "sqlite" not in source and "write(" not in source


# ------------------------------------------------------------------------- CLI
def scripted(answers):
    it = iter(answers)
    return lambda _prompt="": next(it)


def test_cli_validates_and_can_generate_another(capsys):
    answers = [
        "abc", "5", "12",          # bad length, too short, then valid
        "n", "y", "n", "n",        # only 1 type selected -> asked again
        "n", "y", "y", "n",        # lowercase + numbers
        "y",                       # generate another
        "10", "y", "y", "y", "y",  # second password, all types
        "n",                       # stop
    ]
    password_cli.run(scripted(answers))
    out = capsys.readouterr().out
    assert out.count("Your password:") == 2
    assert "must be a whole number" in out and "at least 8" in out and "at least 2" in out
