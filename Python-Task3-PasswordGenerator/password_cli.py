"""Command-line version (the Beginner tier of Task 3) - uses the same secure generator as the GUI.

Run:  python password_cli.py
"""
from __future__ import annotations

from password_core import (
    MAX_LENGTH,
    MIN_CHARACTER_TYPES,
    MIN_LENGTH,
    Options,
    PasswordError,
    generate_password,
    parse_length,
    password_strength,
)

PROMPTS = (
    ("uppercase", "Include UPPERCASE letters?"),
    ("lowercase", "Include lowercase letters?"),
    ("numbers", "Include numbers?"),
    ("symbols", "Include symbols?"),
)


def ask_yes_no(question: str, input_fn=input) -> bool:
    while True:
        answer = input_fn(f"{question} (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please answer y or n.")


def ask_length(input_fn=input) -> int:
    while True:
        try:
            return parse_length(input_fn(f"Password length ({MIN_LENGTH}-{MAX_LENGTH}): "))
        except PasswordError as exc:
            print(f"  {exc}")


def ask_options(input_fn=input) -> Options:
    length = ask_length(input_fn)
    while True:
        choices = {name: ask_yes_no(question, input_fn) for name, question in PROMPTS}
        if sum(choices.values()) >= MIN_CHARACTER_TYPES:
            return Options(length=length, **choices)
        print(f"  Please choose at least {MIN_CHARACTER_TYPES} character types.")


def run(input_fn=input) -> None:
    print("=== Random Password Generator ===")
    while True:
        options = ask_options(input_fn)
        password = generate_password(options)
        label, _percent, bits = password_strength(password)
        print(f"\nYour password: {password}")
        print(f"Strength: {label} (about {bits:.0f} bits)\n")
        if not ask_yes_no("Generate another password?", input_fn):
            print("Goodbye - keep your passwords private!")
            return


if __name__ == "__main__":
    run()
