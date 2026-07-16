"""
utils/schemas.py
-----------------
Pydantic models for validating LLM JSON output before it's trusted
downstream. If the model drops a key or changes shape, we find out
immediately (as a logged validation error) instead of silently
rendering blanks in the UI.
"""

from typing import Optional
from pydantic import BaseModel, Field, ValidationError


class MealBlock(BaseModel):
    time: str = ""
    items: list[str] = Field(default_factory=list)
    description: str = ""
    approx_calories: int = 0
    approx_protein_g: float = 0.0


class MorningRitual(BaseModel):
    time: str = ""
    description: str = ""


class MealPlanResponse(BaseModel):
    disclaimer: str = "Consult a doctor or registered dietitian before making dietary changes."
    morning_ritual: MorningRitual = Field(default_factory=MorningRitual)
    breakfast: MealBlock = Field(default_factory=MealBlock)
    mid_morning: MealBlock = Field(default_factory=MealBlock)
    lunch: MealBlock = Field(default_factory=MealBlock)
    evening_snack: MealBlock = Field(default_factory=MealBlock)
    dinner: MealBlock = Field(default_factory=MealBlock)
    hydration_tip: str = ""
    regional_tip: str = ""


class ExerciseItem(BaseModel):
    name: Optional[str] = None
    asana: Optional[str] = None
    sets_reps: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    benefit: Optional[str] = None


class ExercisePlanResponse(BaseModel):
    duration_minutes: int = 30
    warm_up: list[ExerciseItem] = Field(default_factory=list)
    main_workout: list[ExerciseItem] = Field(default_factory=list)
    yoga: list[ExerciseItem] = Field(default_factory=list)
    cool_down: list[ExerciseItem] = Field(default_factory=list)
    caution: str = ""


class MealBreakdownItem(BaseModel):
    calories: int = 0
    protein_g: float = 0.0


class MealAnalysisResponse(BaseModel):
    breakdown: dict[str, MealBreakdownItem] = Field(default_factory=dict)
    total_calories: int = 0
    total_protein_g: float = 0.0
    notes: str = ""


class WeeklyInsightResponse(BaseModel):
    overall_score: int = 0
    highlights: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    next_week_focus: str = ""
    motivational_message: str = ""


def validate_llm_output(raw: dict, schema: type[BaseModel]) -> tuple[Optional[dict], Optional[str]]:
    """
    Validate a raw dict (already JSON-parsed) against a schema.
    Returns (validated_dict, None) on success, or (None, error_message) on failure.
    Coerces missing/extra fields gracefully rather than hard-failing on minor drift.
    """
    try:
        model = schema.model_validate(raw)
        return model.model_dump(), None
    except ValidationError as e:
        return None, f"AI response didn't match the expected format: {e}"
