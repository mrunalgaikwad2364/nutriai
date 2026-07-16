import pytest
from utils.nutrition import calculate_bmi, calculate_targets, classify_goal


def test_bmi_categories():
    bmi, cat = calculate_bmi(weight_kg=50, height_cm=170)
    assert cat == "Underweight"

    bmi, cat = calculate_bmi(weight_kg=65, height_cm=170)
    assert cat == "Normal weight"

    bmi, cat = calculate_bmi(weight_kg=80, height_cm=170)
    assert cat == "Overweight"

    bmi, cat = calculate_bmi(weight_kg=100, height_cm=170)
    assert cat == "Obese"


def test_classify_goal():
    assert classify_goal("I want weight loss") == "weight_loss"
    assert classify_goal("trying to lose fat") == "weight_loss"
    assert classify_goal("weight gain please") == "weight_gain"
    assert classify_goal("build muscle") == "weight_gain"
    assert classify_goal("just balanced diet") == "balanced"


def test_calculate_targets_male_weight_loss():
    t = calculate_targets(
        age=25, gender="male", height_cm=175, weight_kg=75,
        activity_level="moderate", goal="weight_loss"
    )
    # BMR (Mifflin-St Jeor, male): 10*75 + 6.25*175 - 5*25 + 5 = 1723.75 -> 1724
    assert t.bmr == 1724
    assert t.tdee == round(1724 * 1.55)
    # Deficit goal subtracts 400 from TDEE
    assert t.target_calories == max(1200, round(t.tdee - 400))
    assert t.target_protein_g == round(75 * 1.6, 1)


def test_calculate_targets_female_maintenance():
    t = calculate_targets(
        age=30, gender="female", height_cm=160, weight_kg=60,
        activity_level="sedentary", goal="balanced"
    )
    assert t.target_calories == t.tdee
    assert t.target_protein_g == round(60 * 1.2, 1)


def test_calculate_targets_never_below_safety_floor():
    # Very low weight/short height + weight_loss goal should still floor at 1200
    t = calculate_targets(
        age=20, gender="female", height_cm=150, weight_kg=40,
        activity_level="sedentary", goal="weight_loss"
    )
    assert t.target_calories >= 1200


def test_calculate_targets_macros_sum_reasonably():
    t = calculate_targets(
        age=28, gender="male", height_cm=180, weight_kg=80,
        activity_level="high", goal="weight_gain"
    )
    # carbs should never go negative
    assert t.target_carbs_g >= 0
    # fat should be roughly 25% of calories (9 kcal/g)
    assert abs((t.target_fat_g * 9) - (t.target_calories * 0.25)) < 1
