"""
utils/validators.py
--------------------
Input validation helpers. All return (value, error_string_or_None).
"""

from typing import Optional, Any


def validate_age(value: Any) -> tuple[Optional[int], Optional[str]]:
    try:
        age = int(value)
        if not (5 <= age <= 120):
            return None, "Age must be between 5 and 120."
        return age, None
    except (TypeError, ValueError):
        return None, "Please enter a valid age (number)."


def validate_height(value: Any) -> tuple[Optional[float], Optional[str]]:
    try:
        h = float(value)
        if not (50 <= h <= 250):
            return None, "Height must be between 50 cm and 250 cm."
        return round(h, 1), None
    except (TypeError, ValueError):
        return None, "Please enter a valid height in centimetres."


def validate_weight(value: Any) -> tuple[Optional[float], Optional[str]]:
    try:
        w = float(value)
        if not (20 <= w <= 300):
            return None, "Weight must be between 20 kg and 300 kg."
        return round(w, 1), None
    except (TypeError, ValueError):
        return None, "Please enter a valid weight in kilograms."


def validate_username(value: str) -> tuple[Optional[str], Optional[str]]:
    v = (value or "").strip()
    if len(v) < 3:
        return None, "Username must be at least 3 characters."
    if len(v) > 30:
        return None, "Username must be 30 characters or fewer."
    if not v.replace("_", "").replace("-", "").isalnum():
        return None, "Username may only contain letters, numbers, hyphens, and underscores."
    return v.lower(), None


def validate_password(value: str) -> tuple[Optional[str], Optional[str]]:
    if len(value) < 6:
        return None, "Password must be at least 6 characters."
    return value, None


def validate_profile(form: dict) -> dict[str, str]:
    """
    Validate all profile fields.
    Returns a dict of field_name → error_message for any failing fields.
    Empty dict means all valid.
    """
    errors: dict[str, str] = {}

    _, e = validate_age(form.get("age"))
    if e:
        errors["age"] = e

    _, e = validate_height(form.get("height_cm"))
    if e:
        errors["height_cm"] = e

    _, e = validate_weight(form.get("weight_kg"))
    if e:
        errors["weight_kg"] = e

    if not (form.get("name") or "").strip():
        errors["name"] = "Name is required."

    if not form.get("goal"):
        errors["goal"] = "Please select a health goal."

    if not form.get("diet_pref"):
        errors["diet_pref"] = "Please select a diet preference."

    if not form.get("activity_level"):
        errors["activity_level"] = "Please select an activity level."

    return errors
