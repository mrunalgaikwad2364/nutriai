"""
utils/nutrition.py
-------------------
Deterministic nutrition calculations (no LLM needed).
Uses the Mifflin-St Jeor equation for BMR / TDEE.
"""

from dataclasses import dataclass
from typing import Literal

ActivityLevel = Literal["sedentary", "low", "moderate", "high", "very_high"]

ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary":  1.2,
    "low":        1.375,
    "moderate":   1.55,
    "high":       1.725,
    "very_high":  1.9,
}

# Map display labels → canonical keys
ACTIVITY_LABELS: dict[str, str] = {
    "Sedentary (desk job, no exercise)": "sedentary",
    "Lightly Active (1–3 days/week)":    "low",
    "Moderately Active (3–5 days/week)": "moderate",
    "Very Active (6–7 days/week)":       "high",
    "Athlete / Physically demanding job":"very_high",
}


@dataclass
class NutritionTargets:
    bmr: float
    tdee: float
    target_calories: int
    target_protein_g: float
    target_carbs_g: float
    target_fat_g: float
    bmi: float
    bmi_category: str


def calculate_bmi(weight_kg: float, height_cm: float) -> tuple[float, str]:
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)
    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal weight"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"
    return round(bmi, 1), category


def calculate_targets(
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    goal: str,
) -> NutritionTargets:
    """
    Compute daily nutrition targets.

    Parameters
    ----------
    activity_level : str
        Canonical key from ACTIVITY_MULTIPLIERS (e.g. "moderate").
    goal : str
        One of "weight_loss", "weight_gain", "balanced".
    """
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender.lower() in ("female", "f"):
        bmr -= 161
    else:
        bmr += 5

    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
    tdee = bmr * multiplier

    goal_lower = goal.lower()
    if "loss" in goal_lower:
        target_calories = tdee - 400
    elif "gain" in goal_lower:
        target_calories = tdee + 300
    else:
        target_calories = tdee

    target_calories = max(1200, round(target_calories))

    protein_factor = 1.6 if goal_lower in ("weight_loss", "weight_gain") else 1.2
    target_protein = round(weight_kg * protein_factor, 1)

    target_fat = round((target_calories * 0.25) / 9, 1)

    protein_cals = target_protein * 4
    fat_cals     = target_fat * 9
    target_carbs = round((target_calories - protein_cals - fat_cals) / 4, 1)
    target_carbs = max(0, target_carbs)

    bmi, bmi_cat = calculate_bmi(weight_kg, height_cm)

    return NutritionTargets(
        bmr=round(bmr),
        tdee=round(tdee),
        target_calories=target_calories,
        target_protein_g=target_protein,
        target_carbs_g=target_carbs,
        target_fat_g=target_fat,
        bmi=bmi,
        bmi_category=bmi_cat,
    )


def classify_goal(goal_text: str) -> str:
    """Map free-text goal to canonical category."""
    g = goal_text.lower()
    if "loss" in g or "lose" in g:
        return "weight_loss"
    if "gain" in g or "bulk" in g or "muscle" in g:
        return "weight_gain"
    return "balanced"
