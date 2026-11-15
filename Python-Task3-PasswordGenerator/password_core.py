"""Core logic for the Random Password Generator (Oasis Infobyte - Python Programming, Task 3, Advanced tier).

Everything here is free of GUI code so it can be unit tested:

* ``generate_password``  - cryptographically secure generation (``secrets``, never ``random``)
* ``password_strength``  - Weak / Medium / Strong from length and character diversity
* ``PasswordHistory``    - the last few passwords of THIS session only (kept in memory, never written to disk)
"""
from __future__ import annotations

import math
import secrets
import string
from collections import deque
from dataclasses import dataclass

MIN_LENGTH = 8
MAX_LENGTH = 128
MIN_CHARACTER_TYPES = 2
HISTORY_SIZE = 5

SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/"
AMBIGUOUS = "0O1lI|"  # characters that are easy to confuse when read aloud or copied by hand

CHARACTER_SETS = {
    "lowercase": string.ascii_lowercase,
    "uppercase": string.ascii_uppercase,
    "numbers": string.digits,
    "symbols": SYMBOLS,
}


class PasswordError(ValueError):
    """Raised for invalid options (bad length, too few character types ...)."""


@dataclass(frozen=True)
class Options:
    length: int = 16
    lowercase: bool = True
    uppercase: bool = True
    numbers: bool = True
    symbols: bool = True
    exclude_ambiguous: bool = False

    def selected_types(self) -> list[str]:
        return [name for name in CHARACTER_SETS if getattr(self, name)]


def parse_length(text: str | int) -> int:
    """Convert what the user typed into a valid length (8-128) or raise ``PasswordError``."""
    raw = str(text).strip()
    if not raw:
        raise PasswordError("Please enter a password length.")
    try:
        length = int(raw)
    except ValueError:
        raise PasswordError(f"Length must be a whole number, not '{raw}'.") from None
    if length < MIN_LENGTH:
        raise PasswordError(f"Password length must be at least {MIN_LENGTH} characters.")
    if length > MAX_LENGTH:
        raise PasswordError(f"Password length can be at most {MAX_LENGTH} characters.")
    return length


def build_pools(options: Options) -> dict[str, str]:
    """The characters allowed for every selected type (ambiguous ones removed if requested)."""
    selected = options.selected_types()
    if len(selected) < MIN_CHARACTER_TYPES:
        raise PasswordError(f"Select at least {MIN_CHARACTER_TYPES} character types (uppercase, lowercase, numbers, symbols).")
    pools = {}
    for name in selected:
        chars = CHARACTER_SETS[name]
        if options.exclude_ambiguous:
            chars = "".join(c for c in chars if c not in AMBIGUOUS)
        pools[name] = chars
    return pools


def generate_password(options: Options | None = None) -> str:
    """Return a random password that satisfies ``options``.

    Guarantees at least one character from every selected type, then fills the remaining positions from
    the combined pool and shuffles the result so the guaranteed characters are not always at the start.
    """
    options = options or Options()
    length = parse_length(options.length)
    pools = build_pools(options)
    combined = "".join(pools.values())
    chars = [secrets.choice(pool) for pool in pools.values()]
    chars += [secrets.choice(combined) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


# ---------------------------------------------------------------------- strength
def estimate_entropy_bits(password: str) -> float:
    """Rough entropy: length x log2(size of the character pool the password draws from)."""
    if not password:
        return 0.0
    pool = 0
    if any(c in string.ascii_lowercase for c in password):
        pool += 26
    if any(c in string.ascii_uppercase for c in password):
        pool += 26
    if any(c in string.digits for c in password):
        pool += 10
    if any(not c.isalnum() for c in password):
        pool += len(SYMBOLS)
    return len(password) * math.log2(pool) if pool else 0.0


def password_strength(password: str) -> tuple[str, int, float]:
    """Return ``(label, percent, entropy_bits)`` - label is Weak, Medium or Strong.

    Thresholds: under 50 bits = Weak, 50-79 bits = Medium, 80+ bits = Strong. ``percent`` (0-100) drives the bar.
    """
    bits = estimate_entropy_bits(password)
    if bits < 50:
        label = "Weak"
    elif bits < 80:
        label = "Medium"
    else:
        label = "Strong"
    percent = max(0, min(100, round(bits)))  # 100 bits or more fills the bar
    return label, percent, bits


# ----------------------------------------------------------------------- history
class PasswordHistory:
    """Last ``HISTORY_SIZE`` passwords of the current session, newest first. Memory only - nothing is saved to disk."""

    def __init__(self, size: int = HISTORY_SIZE):
        self._items: deque[str] = deque(maxlen=size)

    def add(self, password: str) -> None:
        self._items.appendleft(password)

    def items(self) -> list[str]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
