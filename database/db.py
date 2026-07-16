"""
database/db.py
--------------
All SQLite interactions for NutriAI.
Schema: users, user_profiles, daily_logs, meal_entries
"""

import sqlite3
import os
import bcrypt
from typing import Optional
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "nutriai.db")


# ─── Connection ───────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─── Schema Initialisation ────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    email         TEXT    UNIQUE,
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name           TEXT,
    age            INTEGER,
    gender         TEXT,
    height_cm      REAL,
    weight_kg      REAL,
    activity_level TEXT,
    goal           TEXT,
    diet_pref      TEXT,
    region         TEXT,
    health_issues  TEXT,
    updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date        TEXT    NOT NULL,          -- ISO date YYYY-MM-DD
    target_calories INTEGER,
    target_protein  REAL,
    meal_plan       TEXT,                      -- JSON string from the LLM
    exercise_plan   TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, log_date)
);

CREATE TABLE IF NOT EXISTS meal_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id      INTEGER NOT NULL REFERENCES daily_logs(id) ON DELETE CASCADE,
    meal_type   TEXT    NOT NULL,
    description TEXT,
    calories    INTEGER,
    protein_g   REAL,
    logged_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_logs_user_date ON daily_logs(user_id, log_date);
CREATE INDEX IF NOT EXISTS idx_meals_log     ON meal_entries(log_id);
"""

def init_db() -> None:
    try:
        conn = get_connection()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()
        logger.info("Database initialised at %s", DB_PATH)
    except sqlite3.Error as e:
        logger.error("DB init failed: %s", e)
        raise


# ─── Auth Helpers ─────────────────────────────────────────────────────────────
# Improvement #2: bcrypt instead of manual salt+SHA-256.
# SHA-256 is fast, which is exactly the wrong property for password hashing —
# it makes offline brute-force cheap. bcrypt is deliberately slow and includes
# its own per-hash salt, so we don't manage salts ourselves at all.

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except ValueError:
        # stored_hash isn't a valid bcrypt hash (e.g. legacy SHA-256 row)
        return False


def register_user(username: str, password: str, email: str = "") -> dict:
    """Create a new user. Returns {"ok": True} or {"ok": False, "error": str}."""
    stored = _hash_password(password)
    email_value = email.strip().lower() or None
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username.strip().lower(), stored, email_value)
        )
        conn.commit()
        conn.close()
        return {"ok": True}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "Username or email already exists."}
    except sqlite3.Error as e:
        logger.error("register_user error: %s", e)
        return {"ok": False, "error": "Database error. Please try again."}


def verify_user(username: str, password: str) -> Optional[int]:
    """Return user_id if credentials match, else None."""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username.strip().lower(),)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return row["id"] if _verify_password(password, row["password_hash"]) else None
    except sqlite3.Error as e:
        logger.error("verify_user error: %s", e)
        return None


# ─── User Profile ─────────────────────────────────────────────────────────────

def upsert_profile(user_id: int, profile: dict) -> bool:
    sql = """
        INSERT INTO user_profiles
            (user_id, name, age, gender, height_cm, weight_kg,
             activity_level, goal, diet_pref, region, health_issues, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            name=excluded.name, age=excluded.age, gender=excluded.gender,
            height_cm=excluded.height_cm, weight_kg=excluded.weight_kg,
            activity_level=excluded.activity_level, goal=excluded.goal,
            diet_pref=excluded.diet_pref, region=excluded.region,
            health_issues=excluded.health_issues,
            updated_at=excluded.updated_at
    """
    try:
        conn = get_connection()
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_profile_user ON user_profiles(user_id)"
        )
        conn.execute(sql, (
            user_id, profile.get("name"), profile.get("age"), profile.get("gender"),
            profile.get("height_cm"), profile.get("weight_kg"),
            profile.get("activity_level"), profile.get("goal"),
            profile.get("diet_pref"), profile.get("region"), profile.get("health_issues")
        ))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error("upsert_profile error: %s", e)
        return False


def get_profile(user_id: int) -> Optional[dict]:
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error("get_profile error: %s", e)
        return None


# ─── Daily Logs ───────────────────────────────────────────────────────────────

def save_daily_log(
    user_id: int,
    log_date: str,
    target_calories: int,
    target_protein: float,
    meal_plan: str,
    exercise_plan: str = ""
) -> Optional[int]:
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO daily_logs
               (user_id, log_date, target_calories, target_protein, meal_plan, exercise_plan)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, log_date) DO UPDATE SET
                   target_calories=excluded.target_calories,
                   target_protein=excluded.target_protein,
                   meal_plan=excluded.meal_plan,
                   exercise_plan=excluded.exercise_plan""",
            (user_id, log_date, target_calories, target_protein, meal_plan, exercise_plan)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM daily_logs WHERE user_id=? AND log_date=?",
            (user_id, log_date)
        ).fetchone()
        conn.close()
        return row["id"] if row else None
    except sqlite3.Error as e:
        logger.error("save_daily_log error: %s", e)
        return None


def get_daily_log(user_id: int, log_date: str) -> Optional[dict]:
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM daily_logs WHERE user_id=? AND log_date=?",
            (user_id, log_date)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error("get_daily_log error: %s", e)
        return None


def add_meal_entry(
    log_id: int,
    meal_type: str,
    description: str,
    calories: int,
    protein_g: float
) -> bool:
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO meal_entries (log_id, meal_type, description, calories, protein_g)
               VALUES (?, ?, ?, ?, ?)""",
            (log_id, meal_type, description, calories, protein_g)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error("add_meal_entry error: %s", e)
        return False


def get_meal_entries(log_id: int) -> list[dict]:
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM meal_entries WHERE log_id=? ORDER BY logged_at",
            (log_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("get_meal_entries error: %s", e)
        return []


# ─── Analytics / History ──────────────────────────────────────────────────────

def get_history(user_id: int, days: int = 30) -> list[dict]:
    try:
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT
                dl.log_date,
                dl.target_calories,
                dl.target_protein,
                COALESCE(SUM(me.calories), 0) AS eaten_calories,
                COALESCE(SUM(me.protein_g), 0) AS eaten_protein
            FROM daily_logs dl
            LEFT JOIN meal_entries me ON me.log_id = dl.id
            WHERE dl.user_id = ?
              AND dl.log_date >= date('now', ? || ' days')
            GROUP BY dl.id
            ORDER BY dl.log_date ASC
            """,
            (user_id, f"-{days}")
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("get_history error: %s", e)
        return []
