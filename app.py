"""
app.py
------
NutriAI — FastAPI + Jinja2 + HTMX version
Entry point: uvicorn app:app --reload
"""

import json
import logging
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from database.db import (
    init_db, register_user, verify_user,
    upsert_profile, get_profile,
    save_daily_log, get_daily_log,
    add_meal_entry, get_meal_entries,
    get_history,
)
from utils.nutrition import calculate_targets, classify_goal, ACTIVITY_LABELS
from utils.validators import validate_profile, validate_username, validate_password
from utils.llm_client import call_llm_json
from utils.schemas import MealAnalysisResponse, WeeklyInsightResponse, validate_llm_output
from prompts.templates import meal_analysis_prompt, weekly_insight_prompt
from agents.graph import run_pipeline
from utils.pdf_report import generate_report

init_db()

app = FastAPI(title="NutriAI")

# SESSION_SECRET must be set in .env for real deployments — this default is
# only for local dev so the app doesn't crash on first run.
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "dev-secret-change-me"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── Auth helpers ──────────────────────────────────────────────────────────────

def get_current_user(request: Request) -> dict | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return {"user_id": user_id, "username": request.session.get("username")}


def require_login(request: Request):
    user = get_current_user(request)
    if not user:
        return None
    return user


# ── Routes: Home / Auth ───────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {
        "request": request, "user": get_current_user(request)
    })


@app.get("/auth", response_class=HTMLResponse)
def auth_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("auth.html", {"request": request, "error": None, "tab": "login"})


@app.post("/auth/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not username or not password:
        return templates.TemplateResponse("auth.html", {
            "request": request, "error": "Please enter both username and password.", "tab": "login"
        })
    user_id = verify_user(username, password)
    if not user_id:
        return templates.TemplateResponse("auth.html", {
            "request": request, "error": "Invalid username or password.", "tab": "login"
        })
    request.session["user_id"] = user_id
    request.session["username"] = username.lower()
    return RedirectResponse("/", status_code=303)


@app.post("/auth/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    password2: str = Form(...),
):
    u, eu = validate_username(username)
    p, ep = validate_password(password)
    if eu:
        err = eu
    elif ep:
        err = ep
    elif password != password2:
        err = "Passwords do not match."
    else:
        result = register_user(u, p, email)
        if result["ok"]:
            return templates.TemplateResponse("auth.html", {
                "request": request, "error": None,
                "success": "Account created! Please log in.", "tab": "login"
            })
        err = result["error"]

    return templates.TemplateResponse("auth.html", {"request": request, "error": err, "tab": "register"})


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ── Routes: Profile + Plan generation ─────────────────────────────────────────

@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)
    existing = get_profile(user["user_id"]) or {}
    return templates.TemplateResponse("profile.html", {
        "request": request, "user": user, "profile": existing,
        "activity_labels": list(ACTIVITY_LABELS.keys()), "errors": {}
    })


@app.post("/profile", response_class=HTMLResponse)
def save_profile(
    request: Request,
    name: str = Form(...), age: int = Form(...), gender: str = Form(...),
    height_cm: float = Form(...), weight_kg: float = Form(...),
    goal: str = Form(...), diet_pref: str = Form(...), region: str = Form(...),
    activity_level: str = Form(...), health_issues: str = Form(""),
):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)

    form_data = {
        "name": name, "age": age, "gender": gender.lower(),
        "height_cm": height_cm, "weight_kg": weight_kg,
        "goal": goal, "diet_pref": diet_pref, "region": region,
        "activity_level": activity_level, "health_issues": health_issues,
    }
    errors = validate_profile(form_data)
    if errors:
        return templates.TemplateResponse("profile.html", {
            "request": request, "user": user, "profile": form_data,
            "activity_labels": list(ACTIVITY_LABELS.keys()), "errors": errors
        })

    upsert_profile(user["user_id"], form_data)

    # Run the LangGraph pipeline synchronously — same behaviour as before.
    result = run_pipeline(form_data)
    targets = result.get("targets", {})
    meal_plan = result.get("meal_plan")
    exercise = result.get("exercise_plan")

    save_daily_log(
        user_id=user["user_id"],
        log_date=date.today().isoformat(),
        target_calories=targets.get("target_calories", 0),
        target_protein=targets.get("target_protein_g", 0),
        meal_plan=json.dumps(meal_plan),
        exercise_plan=json.dumps(exercise),
    )

    return RedirectResponse("/plan", status_code=303)


@app.get("/plan", response_class=HTMLResponse)
def plan_page(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)

    today_log = get_daily_log(user["user_id"], date.today().isoformat())
    if not today_log:
        return RedirectResponse("/profile", status_code=303)

    meal_plan = json.loads(today_log.get("meal_plan") or "{}")
    exercise_plan = json.loads(today_log.get("exercise_plan") or "{}")
    targets_dict = {
        "target_calories":  today_log.get("target_calories"),
        "target_protein_g": today_log.get("target_protein"),
    }

    return templates.TemplateResponse("plan.html", {
        "request": request, "user": user,
        "meal_plan": meal_plan, "exercise_plan": exercise_plan,
        "targets": targets_dict,
    })


@app.get("/plan/pdf")
def download_pdf(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)

    profile = get_profile(user["user_id"]) or {}
    today_log = get_daily_log(user["user_id"], date.today().isoformat()) or {}
    meal_plan = json.loads(today_log.get("meal_plan") or "{}")
    exercise_plan = json.loads(today_log.get("exercise_plan") or "{}")
    history = get_history(user["user_id"], days=30)

    activity_key = ACTIVITY_LABELS.get(profile.get("activity_level", ""), "moderate")
    targets_obj = calculate_targets(
        age=int(profile.get("age", 25)),
        gender=profile.get("gender", "male"),
        height_cm=float(profile.get("height_cm", 165)),
        weight_kg=float(profile.get("weight_kg", 65)),
        activity_level=activity_key,
        goal=classify_goal(profile.get("goal", "")),
    )
    pdf_bytes = generate_report(
        profile=profile, targets=targets_obj,
        meal_plan=meal_plan, exercise_plan=exercise_plan, history=history,
    )
    from fastapi.responses import Response
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=NutriAI_Report_{date.today()}.pdf"}
    )


# ── Routes: Meal tracker ──────────────────────────────────────────────────────

@app.get("/tracker", response_class=HTMLResponse)
def tracker_page(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)

    today_log = get_daily_log(user["user_id"], date.today().isoformat())
    if not today_log:
        return templates.TemplateResponse("tracker.html", {
            "request": request, "user": user, "no_plan": True
        })

    entries = get_meal_entries(today_log["id"])
    total_cal = sum(e["calories"] for e in entries)
    total_prot = sum(e["protein_g"] for e in entries)

    return templates.TemplateResponse("tracker.html", {
        "request": request, "user": user, "no_plan": False,
        "entries": entries, "today_log": today_log,
        "total_cal": total_cal, "total_prot": total_prot,
    })


@app.post("/tracker/log")
def log_meals(
    request: Request,
    breakfast: str = Form(""), lunch: str = Form(""),
    dinner: str = Form(""), snacks: str = Form(""),
):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)

    today_log = get_daily_log(user["user_id"], date.today().isoformat())
    if not today_log:
        return RedirectResponse("/profile", status_code=303)

    meals = {"breakfast": breakfast, "lunch": lunch, "dinner": dinner, "snacks": snacks}
    meals = {k: v for k, v in meals.items() if v.strip()}

    if meals:
        prompt = meal_analysis_prompt(meals)
        result, error = call_llm_json(prompt)
        if not error:
            validated, verr = validate_llm_output(result, MealAnalysisResponse)
            if not verr:
                breakdown = validated.get("breakdown", {})
                for meal_type, desc in meals.items():
                    mb = breakdown.get(meal_type, {})
                    add_meal_entry(
                        log_id=today_log["id"], meal_type=meal_type, description=desc,
                        calories=mb.get("calories", 0), protein_g=mb.get("protein_g", 0.0),
                    )

    return RedirectResponse("/tracker", status_code=303)


# ── Routes: Progress ──────────────────────────────────────────────────────────

@app.get("/progress", response_class=HTMLResponse)
def progress_page(request: Request, days: int = 30):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)

    history = get_history(user["user_id"], days=days)
    return templates.TemplateResponse("progress.html", {
        "request": request, "user": user, "history": history, "days": days,
        "history_json": json.dumps(history),
    })


@app.post("/progress/insight", response_class=HTMLResponse)
def weekly_insight(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)

    profile = get_profile(user["user_id"]) or {}
    history = get_history(user["user_id"], days=30)
    history_text = "\n".join(
        f"  {r['log_date']}: eaten {r['eaten_calories']} kcal (target {r['target_calories']}), "
        f"protein {r['eaten_protein']:.1f} g"
        for r in history
    )
    prompt = weekly_insight_prompt(history_text, profile)
    result, error = call_llm_json(prompt)
    insight = None
    if not error:
        insight, verr = validate_llm_output(result, WeeklyInsightResponse)

    return templates.TemplateResponse("_insight_fragment.html", {
        "request": request, "insight": insight, "error": error,
    })


# ── Routes: Settings ──────────────────────────────────────────────────────────

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    user = require_login(request)
    if not user:
        return RedirectResponse("/auth", status_code=303)
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})
