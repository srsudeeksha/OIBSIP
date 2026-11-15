"""Core logic for the BMI Calculator (Oasis Infobyte - Python Programming, Task 2, Advanced tier).

This module has no GUI code, so everything in it can be unit tested:

* ``calculate_bmi`` / ``classify_bmi``  - the maths and the health categories
* ``parse_measurement`` / ``normalise_name`` - input validation with friendly messages
* ``BMIDatabase``                        - multi-user history stored in SQLite
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Sensible human limits - they only exist to catch typos such as "165" for a height in metres.
MIN_WEIGHT_KG, MAX_WEIGHT_KG = 1.0, 500.0
MIN_HEIGHT_M, MAX_HEIGHT_M = 0.5, 2.5
MAX_NAME_LENGTH = 40

CATEGORY_RANGES = {
    "Underweight": "BMI below 18.5",
    "Normal": "BMI 18.5 - 24.9",
    "Overweight": "BMI 25 - 29.9",
    "Obese": "BMI 30 and above",
}


class ValidationError(ValueError):
    """Raised when the user typed something that cannot be used."""


class DatabaseError(RuntimeError):
    """Raised when reading from / writing to the SQLite file fails."""


# --------------------------------------------------------------------------- maths
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """BMI = weight / (height squared), rounded to 2 decimal places."""
    if weight_kg <= 0 or height_m <= 0:
        raise ValidationError("Weight and height must both be greater than zero.")
    return round(weight_kg / (height_m ** 2), 2)


def classify_bmi(bmi: float) -> str:
    """Standard adult categories: <18.5, 18.5-24.9, 25-29.9, >=30."""
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"


# --------------------------------------------------------------------- validation
def parse_measurement(text: str, label: str, unit: str, low: float, high: float, example: str) -> float:
    """Turn the text typed in a field into a number, or raise ``ValidationError``.

    Rejects: empty text, non-numeric text, NaN/infinity, zero/negative values and
    values outside ``low``..``high`` (so a height of 165 is caught with a hint to use metres).
    """
    cleaned = (text or "").strip().replace(",", ".")
    if not cleaned:
        raise ValidationError(f"Please enter your {label.lower()} in {unit} (for example {example}).")
    try:
        value = float(cleaned)
    except ValueError:
        raise ValidationError(f"{label} must be a number such as {example}, not '{text.strip()}'.") from None
    if math.isnan(value) or math.isinf(value):
        raise ValidationError(f"{label} must be a real number such as {example}.")
    if value <= 0:
        raise ValidationError(f"{label} must be greater than zero - negative values are not allowed.")
    if not low <= value <= high:
        raise ValidationError(
            f"{label} must be between {low:g} and {high:g} {unit} (you entered {value:g}). Example: {example}."
        )
    return value


def parse_weight(text: str) -> float:
    return parse_measurement(text, "Weight", "kg", MIN_WEIGHT_KG, MAX_WEIGHT_KG, "65.5")


def parse_height(text: str) -> float:
    return parse_measurement(text, "Height", "metres", MIN_HEIGHT_M, MAX_HEIGHT_M, "1.65")


def normalise_name(name: str) -> str:
    """Trim and collapse spaces; reject empty or over-long names."""
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise ValidationError("Please enter a name so the record can be saved for that user.")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValidationError(f"Name can be at most {MAX_NAME_LENGTH} characters.")
    return cleaned


# ------------------------------------------------------------------------ storage
@dataclass(frozen=True)
class Record:
    id: int
    user_name: str
    weight_kg: float
    height_m: float
    bmi: float
    category: str
    recorded_at: datetime


_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name   TEXT NOT NULL,
    user_key    TEXT NOT NULL,
    weight_kg   REAL NOT NULL,
    height_m    REAL NOT NULL,
    bmi         REAL NOT NULL,
    category    TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_user ON records (user_key, recorded_at);
"""
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class BMIDatabase:
    """Tiny repository around one SQLite file. User names are matched case-insensitively."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not prepare the database file '{self.path}': {exc}") from exc

    # one short-lived connection per operation keeps things simple and avoids locked files
    def _connect(self):
        try:
            conn = sqlite3.connect(self.path, timeout=5)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not open the database file '{self.path}': {exc}") from exc
        return _ManagedConnection(conn)

    def add_record(self, user_name: str, weight_kg: float, height_m: float, bmi: float,
                   category: str, recorded_at: datetime | None = None) -> Record:
        name = normalise_name(user_name)
        when = (recorded_at or datetime.now()).replace(microsecond=0)
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO records (user_name, user_key, weight_kg, height_m, bmi, category, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name, name.casefold(), weight_kg, height_m, bmi, category, when.strftime(_TIME_FORMAT)),
                )
                new_id = cur.lastrowid
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not save the record: {exc}") from exc
        return Record(new_id, name, weight_kg, height_m, bmi, category, when)

    def list_users(self) -> list[str]:
        """Every user that has at least one record (latest spelling of each name), A-Z."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT user_name FROM records WHERE id IN (SELECT MAX(id) FROM records GROUP BY user_key) "
                    "ORDER BY user_key"
                ).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not read the list of users: {exc}") from exc
        return [row["user_name"] for row in rows]

    def get_history(self, user_name: str) -> list[Record]:
        """All records for a user, oldest first (this is the order the trend chart needs)."""
        key = " ".join((user_name or "").split()).casefold()
        if not key:
            return []
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM records WHERE user_key = ? ORDER BY recorded_at, id", (key,)
                ).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not read the history: {exc}") from exc
        return [
            Record(r["id"], r["user_name"], r["weight_kg"], r["height_m"], r["bmi"], r["category"],
                   datetime.strptime(r["recorded_at"], _TIME_FORMAT))
            for r in rows
        ]


class _ManagedConnection:
    """Context manager: commit on success, roll back on error, always close."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def __enter__(self) -> sqlite3.Connection:
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
        return False
