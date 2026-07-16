"""
agents/graph.py
----------------
LangGraph multi-agent workflow for NutriAI.

Graph topology:
  classify_goal
      ├─ weight_loss  ─┐
      ├─ weight_gain  ─┤─► generate_meal_plan ─► suggest_exercise ─► END
      └─ balanced     ─┘
"""

import logging
from typing import TypedDict, Optional, Literal

from langgraph.graph import StateGraph, END

from prompts.templates import meal_plan_prompt, exercise_prompt
from utils.llm_client import call_llm_json
from utils.nutrition import calculate_targets, classify_goal, ACTIVITY_MULTIPLIERS
from utils.schemas import MealPlanResponse, ExercisePlanResponse, validate_llm_output

logger = logging.getLogger(__name__)


class NutriState(TypedDict, total=False):
    profile: dict
    goal_category: str
    targets: dict
    meal_plan: Optional[dict]
    exercise_plan: Optional[dict]
    errors: list[str]


def node_classify_goal(state: NutriState) -> NutriState:
    profile = state.get("profile", {})
    goal_text = profile.get("goal", "")
    category = classify_goal(goal_text)
    logger.info("Goal classified: %s → %s", goal_text, category)
    return {**state, "goal_category": category}


def node_compute_targets(state: NutriState) -> NutriState:
    p = state["profile"]
    errors = list(state.get("errors", []))

    activity = p.get("activity_level", "moderate")
    if activity not in ACTIVITY_MULTIPLIERS:
        from utils.nutrition import ACTIVITY_LABELS
        activity = ACTIVITY_LABELS.get(activity, "moderate")

    try:
        targets = calculate_targets(
            age=int(p["age"]),
            gender=p.get("gender", "male"),
            height_cm=float(p["height_cm"]),
            weight_kg=float(p["weight_kg"]),
            activity_level=activity,
            goal=state.get("goal_category", "balanced"),
        )
        targets_dict = {
            "bmr":              targets.bmr,
            "tdee":             targets.tdee,
            "target_calories":  targets.target_calories,
            "target_protein_g": targets.target_protein_g,
            "target_carbs_g":   targets.target_carbs_g,
            "target_fat_g":     targets.target_fat_g,
            "bmi":              targets.bmi,
            "bmi_category":     targets.bmi_category,
        }
        return {**state, "targets": targets_dict, "errors": errors}
    except Exception as e:
        errors.append(f"Could not compute nutrition targets: {e}")
        return {**state, "errors": errors}


def _make_meal_plan_node(goal_type: str):
    """Factory — returns a node function for the given goal type."""
    def node(state: NutriState) -> NutriState:
        errors = list(state.get("errors", []))
        profile = state["profile"]
        prompt = meal_plan_prompt(profile, goal_type)
        result, error = call_llm_json(prompt)
        if error:
            errors.append(f"Meal plan generation failed: {error}")
            return {**state, "meal_plan": None, "errors": errors}

        validated, verr = validate_llm_output(result, MealPlanResponse)
        if verr:
            logger.warning("Meal plan schema mismatch: %s", verr)
            errors.append("Meal plan came back in an unexpected format.")
            return {**state, "meal_plan": None, "errors": errors}

        return {**state, "meal_plan": validated, "errors": errors}
    node.__name__ = f"node_meal_{goal_type}"
    return node


def node_suggest_exercise(state: NutriState) -> NutriState:
    errors = list(state.get("errors", []))
    profile = state["profile"]
    prompt = exercise_prompt(profile)
    result, error = call_llm_json(prompt)
    if error:
        errors.append(f"Exercise plan generation failed: {error}")
        return {**state, "exercise_plan": None, "errors": errors}

    validated, verr = validate_llm_output(result, ExercisePlanResponse)
    if verr:
        logger.warning("Exercise plan schema mismatch: %s", verr)
        errors.append("Exercise plan came back in an unexpected format.")
        return {**state, "exercise_plan": None, "errors": errors}

    return {**state, "exercise_plan": validated, "errors": errors}


def _goal_router(state: NutriState) -> Literal["loss", "gain", "balanced"]:
    cat = state.get("goal_category", "balanced")
    if "loss" in cat:
        return "loss"
    if "gain" in cat:
        return "gain"
    return "balanced"


def build_graph():
    builder = StateGraph(NutriState)

    builder.add_node("classify",   node_classify_goal)
    builder.add_node("compute_targets", node_compute_targets)
    builder.add_node("loss",       _make_meal_plan_node("Weight Loss"))
    builder.add_node("gain",       _make_meal_plan_node("Weight Gain"))
    builder.add_node("balanced",   _make_meal_plan_node("Balanced Diet"))
    builder.add_node("exercise",   node_suggest_exercise)

    builder.set_entry_point("classify")
    builder.add_edge("classify", "compute_targets")
    builder.add_conditional_edges(
        "compute_targets",
        _goal_router,
        {"loss": "loss", "gain": "gain", "balanced": "balanced"},
    )
    builder.add_edge("loss",    "exercise")
    builder.add_edge("gain",    "exercise")
    builder.add_edge("balanced","exercise")
    builder.add_edge("exercise", END)

    return builder.compile()


_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_pipeline(profile: dict) -> NutriState:
    graph = get_graph()
    initial: NutriState = {"profile": profile, "errors": []}
    return graph.invoke(initial)
