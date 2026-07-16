from utils.validators import (
    validate_age, validate_height, validate_weight,
    validate_username, validate_password, validate_profile,
)


def test_validate_age_valid():
    val, err = validate_age(25)
    assert val == 25 and err is None


def test_validate_age_out_of_range():
    val, err = validate_age(200)
    assert val is None and err is not None


def test_validate_age_non_numeric():
    val, err = validate_age("abc")
    assert val is None and err is not None


def test_validate_height_valid():
    val, err = validate_height(175.5)
    assert val == 175.5 and err is None


def test_validate_height_too_low():
    val, err = validate_height(10)
    assert val is None and err is not None


def test_validate_weight_valid():
    val, err = validate_weight(70)
    assert val == 70.0 and err is None


def test_validate_username_too_short():
    val, err = validate_username("ab")
    assert val is None and "3 characters" in err


def test_validate_username_invalid_chars():
    val, err = validate_username("bad username!")
    assert val is None and err is not None


def test_validate_username_valid_lowercases():
    val, err = validate_username("Mrunal_99")
    assert val == "mrunal_99" and err is None


def test_validate_password_too_short():
    val, err = validate_password("abc")
    assert val is None and err is not None


def test_validate_password_valid():
    val, err = validate_password("abcdef")
    assert val == "abcdef" and err is None


def test_validate_profile_missing_required_fields():
    errors = validate_profile({})
    assert "name" in errors
    assert "goal" in errors
    assert "diet_pref" in errors
    assert "activity_level" in errors


def test_validate_profile_all_valid():
    form = {
        "name": "Mrunal", "age": 25, "height_cm": 175, "weight_kg": 70,
        "goal": "Weight Loss", "diet_pref": "Vegetarian", "activity_level": "moderate",
    }
    errors = validate_profile(form)
    assert errors == {}
