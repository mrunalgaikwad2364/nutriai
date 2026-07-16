"""
prompts/templates.py
--------------------
All LLM prompt templates for NutriAI.
Prompts request structured JSON so outputs are reliably parseable.
"""


def meal_plan_prompt(profile: dict, goal_type: str) -> str:
    soft_food = "Prefer soft, easy-to-digest foods." if profile.get("age", 0) > 50 else ""
    has_conditions = profile.get("health_issues", "").strip()
    condition_note = (
        f"User has: {has_conditions}. Adjust the plan for these conditions."
        if has_conditions else ""
    )
    return f"""
You are NutriAI, a professional Indian dietician. Create a personalized one-day Indian meal plan.

USER PROFILE:
- Name: {profile.get("name")}
- Age: {profile.get("age")}, Gender: {profile.get("gender")}
- Goal: {profile.get("goal")} ({goal_type})
- Diet Preference: {profile.get("diet_pref")}
- Regional Cuisine: {profile.get("region")}
- Health Conditions: {has_conditions or "None"}
- {soft_food}
- {condition_note}

MEDICAL DISCLAIMER: This is informational only. Advise the user to consult a registered dietitian or doctor, especially for chronic conditions.

Respond ONLY with a valid JSON object — no markdown, no code fences, no extra text:
{{
  "disclaimer": "Consult a doctor or registered dietitian before making dietary changes.",
  "morning_ritual": {{"time": "6:30 AM", "description": "string — e.g. warm water with lemon"}},
  "breakfast": {{"time": "8:00 AM", "items": ["item1", "item2"], "description": "string", "approx_calories": 400, "approx_protein_g": 15}},
  "mid_morning": {{"time": "10:30 AM", "items": ["item1"], "description": "string", "approx_calories": 150, "approx_protein_g": 5}},
  "lunch": {{"time": "1:00 PM", "items": ["item1", "item2", "item3"], "description": "string", "approx_calories": 600, "approx_protein_g": 25}},
  "evening_snack": {{"time": "4:30 PM", "items": ["item1"], "description": "string", "approx_calories": 200, "approx_protein_g": 8}},
  "dinner": {{"time": "7:30 PM", "items": ["item1", "item2"], "description": "string", "approx_calories": 500, "approx_protein_g": 20}},
  "hydration_tip": "string",
  "regional_tip": "string about {profile.get('region')} cuisine"
}}
"""


def meal_analysis_prompt(meal_descriptions: dict[str, str]) -> str:
    meals_text = "\n".join(
        f"- {meal.capitalize()}: {desc}"
        for meal, desc in meal_descriptions.items()
        if desc.strip()
    )
    return f"""
You are a nutrition expert. Estimate calories and protein for these Indian meals:

{meals_text}

Respond ONLY with a valid JSON object — no markdown, no code fences, no extra text:
{{
  "breakdown": {{
    "breakfast": {{"calories": 0, "protein_g": 0.0}},
    "lunch": {{"calories": 0, "protein_g": 0.0}},
    "dinner": {{"calories": 0, "protein_g": 0.0}},
    "snacks": {{"calories": 0, "protein_g": 0.0}}
  }},
  "total_calories": 0,
  "total_protein_g": 0.0,
  "notes": "brief nutritional observation"
}}
"""


def exercise_prompt(profile: dict) -> str:
    return f"""
You are a certified Indian fitness and yoga coach.
Suggest a realistic home workout for:
- Goal: {profile.get("goal")}
- Age: {profile.get("age")}, Gender: {profile.get("gender")}
- Activity Level: {profile.get("activity_level")}
- Health Conditions: {profile.get("health_issues") or "None"}

Include yoga asanas appropriate for the goal. Keep it achievable at home.

Respond ONLY with a valid JSON object — no markdown, no code fences, no extra text:
{{
  "duration_minutes": 30,
  "warm_up": [{{"name": "exercise name", "duration": "5 min", "instructions": "brief instruction"}}],
  "main_workout": [{{"name": "exercise name", "sets_reps": "3x12 or 20 min", "instructions": "brief instruction"}}],
  "yoga": [{{"asana": "asana name", "duration": "hold 30 sec", "benefit": "specific benefit"}}],
  "cool_down": [{{"name": "stretch name", "duration": "2 min"}}],
  "caution": "any condition-specific safety note"
}}
"""


def weekly_insight_prompt(history_summary: str, profile: dict) -> str:
    return f"""
You are NutriAI, a caring Indian dietician reviewing a user's weekly nutrition data.

USER: {profile.get("name")}, Goal: {profile.get("goal")}
WEEK SUMMARY:
{history_summary}

Give a warm, encouraging, actionable 3-point assessment.

Respond ONLY with a valid JSON object — no markdown, no code fences, no extra text:
{{
  "overall_score": 75,
  "highlights": ["positive observation 1", "positive observation 2"],
  "improvements": ["specific actionable tip 1", "specific actionable tip 2"],
  "next_week_focus": "one clear priority for next week",
  "motivational_message": "a warm, culturally resonant message in 1–2 sentences"
}}
"""
