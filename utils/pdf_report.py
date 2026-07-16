"""
utils/pdf_report.py
--------------------
Generate a downloadable nutrition PDF report for the user.
Uses fpdf2 (no LaTeX dependency).
"""

import logging
from datetime import date
from typing import Optional
from fpdf import FPDF

_UNICODE_REPLACEMENTS = {
    "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2022": "-", "\u2713": "v",
}

def _sanitize(text) -> str:
    if not isinstance(text, str):
        text = str(text)
    for bad, good in _UNICODE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


class SafeFPDF(FPDF):
    def cell(self, *args, **kwargs):
        if "txt" in kwargs:
            kwargs["txt"] = _sanitize(kwargs["txt"])
        elif len(args) >= 3:
            args = list(args)
            args[2] = _sanitize(args[2])
        return super().cell(*args, **kwargs)

    def multi_cell(self, *args, **kwargs):
        if "txt" in kwargs:
            kwargs["txt"] = _sanitize(kwargs["txt"])
        elif len(args) >= 3:
            args = list(args)
            args[2] = _sanitize(args[2])
        return super().multi_cell(*args, **kwargs)

logger = logging.getLogger(__name__)


def generate_report(
    profile: dict, targets, meal_plan: Optional[dict],
    exercise_plan: Optional[dict], history: list[dict],
) -> bytes:
    pdf = SafeFPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_fill_color(34, 139, 87)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 14, "NutriAI — Personalized Nutrition Report", ln=True, fill=True, align="C")
    pdf.ln(4)

    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Your Profile", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_fill_color(240, 248, 240)

    rows = [
        ("Name", profile.get("name", "—")),
        ("Age / Gender", f"{profile.get('age', '—')} / {str(profile.get('gender', '—')).title()}"),
        ("Height / Weight", f"{profile.get('height_cm', '—')} cm / {profile.get('weight_kg', '—')} kg"),
        ("Goal", profile.get("goal", "—")),
        ("Diet Preference", profile.get("diet_pref", "—")),
        ("Region", profile.get("region", "—")),
        ("Health Conditions", profile.get("health_issues") or "None"),
        ("Activity Level", str(profile.get("activity_level", "—")).replace("_", " ").title()),
        ("Report Date", date.today().strftime("%d %b %Y")),
    ]
    for label, value in rows:
        pdf.cell(55, 7, label + ":", border=0, fill=True)
        pdf.cell(0, 7, str(value), border=0, ln=True, fill=True)

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Daily Nutrition Targets", ln=True)
    pdf.set_font("Helvetica", "", 11)

    target_rows = [
        ("BMR", f"{targets.bmr} kcal"), ("TDEE", f"{targets.tdee} kcal"),
        ("Target Calories", f"{targets.target_calories} kcal"),
        ("Target Protein", f"{targets.target_protein_g} g"),
        ("Target Carbs", f"{targets.target_carbs_g} g"),
        ("Target Fat", f"{targets.target_fat_g} g"),
        ("BMI", f"{targets.bmi} ({targets.bmi_category})"),
    ]
    for label, value in target_rows:
        pdf.cell(55, 7, label + ":", border=0, fill=True)
        pdf.cell(0, 7, value, border=0, ln=True, fill=True)

    pdf.ln(5)

    if meal_plan:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Today's Meal Plan", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for meal in ["breakfast", "mid_morning", "lunch", "evening_snack", "dinner"]:
            m = meal_plan.get(meal, {})
            if not m:
                continue
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, f"{meal.replace('_',' ').title()}  ({m.get('time', '')})", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, f"  Items: {', '.join(m.get('items', []))}")
            pdf.cell(0, 6, f"  ~{m.get('approx_calories','—')} kcal | ~{m.get('approx_protein_g','—')} g protein", ln=True)
            pdf.ln(2)

    if exercise_plan:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Exercise & Yoga Plan", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Duration: {exercise_plan.get('duration_minutes', '—')} minutes", ln=True)

        for section_key, section_label in [("warm_up","Warm-Up"), ("main_workout","Main Workout"), ("yoga","Yoga / Asanas"), ("cool_down","Cool-Down")]:
            items = exercise_plan.get(section_key, [])
            if not items:
                continue
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, section_label, ln=True)
            pdf.set_font("Helvetica", "", 10)
            for item in items:
                name = item.get("name") or item.get("asana", "")
                detail = item.get("instructions") or item.get("benefit") or item.get("duration", "")
                pdf.multi_cell(0, 6, f"  - {name}: {detail}")
            pdf.ln(2)

        caution = exercise_plan.get("caution")
        if caution:
            pdf.set_font("Helvetica", "I", 10)
            pdf.multi_cell(0, 6, f"Caution: {caution}")

    if history:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, f"Progress (last {len(history)} days)", ln=True)
        pdf.set_font("Helvetica", "B", 9)
        headers = ["Date", "Target Cal", "Eaten Cal", "Target Prot (g)", "Eaten Prot (g)"]
        col_w = [35, 30, 28, 38, 38]
        for h, w in zip(headers, col_w):
            pdf.cell(w, 7, h, border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_font("Helvetica", "", 9)
        for row in history:
            values = [row.get("log_date",""), str(row.get("target_calories","")), str(row.get("eaten_calories","")),
                      str(row.get("target_protein","")), str(row.get("eaten_protein",""))]
            for val, w in zip(values, col_w):
                pdf.cell(w, 6, val, border=1, align="C")
            pdf.ln()

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5,
        "DISCLAIMER: This report is for informational purposes only and does not "
        "constitute medical advice. Please consult a registered dietitian, "
        "nutritionist, or your physician before making any significant dietary or "
        "exercise changes — especially if you have a chronic health condition.")

    return bytes(pdf.output())
