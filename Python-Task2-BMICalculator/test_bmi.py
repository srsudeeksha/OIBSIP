"""Unit tests for the BMI Calculator.  Run with:  python -m pytest -q"""
from datetime import datetime, timedelta

import pytest

from bmi_core import (
    BMIDatabase,
    DatabaseError,
    ValidationError,
    calculate_bmi,
    classify_bmi,
    normalise_name,
    parse_height,
    parse_weight,
)


# ----------------------------------------------------------------- calculation
def test_bmi_formula_and_rounding():
    assert calculate_bmi(70, 1.75) == 22.86
    assert calculate_bmi(50, 1.6) == 19.53


@pytest.mark.parametrize("weight,height", [(0, 1.7), (-5, 1.7), (60, 0), (60, -1.7)])
def test_calculate_rejects_non_positive(weight, height):
    with pytest.raises(ValidationError):
        calculate_bmi(weight, height)


@pytest.mark.parametrize("bmi,expected", [
    (10, "Underweight"), (18.49, "Underweight"),
    (18.5, "Normal"), (24.9, "Normal"), (24.99, "Normal"),
    (25, "Overweight"), (29.9, "Overweight"),
    (30, "Obese"), (45.2, "Obese"),
])
def test_classification_boundaries(bmi, expected):
    assert classify_bmi(bmi) == expected


# ------------------------------------------------------------------ validation
@pytest.mark.parametrize("text", ["", "   ", "abc", "6x", "-60", "0", "nan", "inf", "1e999", "5000"])
def test_weight_rejects_bad_input(text):
    with pytest.raises(ValidationError):
        parse_weight(text)


@pytest.mark.parametrize("text", ["", "tall", "-1.7", "0", "165", "0.1", "nan"])
def test_height_rejects_bad_input(text):
    with pytest.raises(ValidationError):
        parse_height(text)


def test_height_cm_typo_gets_a_helpful_message():
    with pytest.raises(ValidationError, match="metres"):
        parse_height("165")


def test_valid_numbers_accept_comma_and_spaces():
    assert parse_weight(" 65,5 ") == 65.5
    assert parse_height("1.65") == 1.65


def test_name_rules():
    assert normalise_name("  Asha   Rao ") == "Asha Rao"
    with pytest.raises(ValidationError):
        normalise_name("   ")
    with pytest.raises(ValidationError):
        normalise_name("x" * 41)


# --------------------------------------------------------------------- storage
@pytest.fixture()
def db(tmp_path):
    return BMIDatabase(tmp_path / "bmi.db")


def test_records_are_stored_per_user_in_time_order(db):
    start = datetime(2026, 1, 1, 9, 0, 0)
    for i, weight in enumerate([80, 78, 76]):
        bmi = calculate_bmi(weight, 1.8)
        db.add_record("Ravi", weight, 1.8, bmi, classify_bmi(bmi), start + timedelta(days=i))
    db.add_record("Meena", 55, 1.6, calculate_bmi(55, 1.6), "Normal", start)
    history = db.get_history("Ravi")
    assert [r.weight_kg for r in history] == [80, 78, 76]
    assert len(db.get_history("Meena")) == 1
    assert db.list_users() == ["Meena", "Ravi"]


def test_user_lookup_is_case_insensitive(db):
    db.add_record("ravi", 80, 1.8, 24.69, "Normal")
    db.add_record("RAVI  ", 79, 1.8, 24.38, "Normal")
    assert len(db.get_history("Ravi")) == 2
    assert db.list_users() == ["RAVI"]


def test_unknown_or_empty_user_has_no_history(db):
    assert db.get_history("nobody") == []
    assert db.get_history("") == []


def test_database_failures_become_friendly_errors(tmp_path):
    with pytest.raises(DatabaseError):
        BMIDatabase(tmp_path / "missing_folder" / "bmi.db")  # cannot create the file


def test_write_failure_is_reported(db, monkeypatch):
    import sqlite3

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr("bmi_core.sqlite3.connect", boom)
    with pytest.raises(DatabaseError, match="open the database"):
        db.add_record("Ravi", 80, 1.8, 24.69, "Normal")
