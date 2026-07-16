"""
utils/llm_client.py
--------------------
Groq LLM wrapper with:
  - Retry logic (tenacity)
  - Structured JSON output parsing
  - Graceful error handling
  - Logging
Uses the official groq SDK.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_not_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

AUTH_ERROR_MESSAGE = (
    "Groq authentication failed. Your GROQ_API_KEY does not look like a "
    "valid Groq API key. Create one at https://console.groq.com/keys and "
    "put it in your .env file as GROQ_API_KEY=your_key."
)

_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

_client = None


def _get_client():
    global _client
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set. Add it to your .env file.")
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=api_key)
    return _client


def _clean_json_response(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    return text.strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_not_exception_type(EnvironmentError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _invoke_llm(prompt: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def call_llm_json(prompt: str) -> tuple[Optional[dict], Optional[str]]:
    raw = ""
    try:
        raw = _invoke_llm(prompt)
        cleaned = _clean_json_response(raw)
        parsed = json.loads(cleaned)
        return parsed, None
    except json.JSONDecodeError as e:
        logger.error("JSON parse error: %s\nRaw response: %s", e, raw[:500])
        return None, "The AI returned an unexpected format. Please try again."
    except EnvironmentError as e:
        return None, str(e)
    except Exception as e:
        logger.error("LLM call failed after retries: %s", e)
        err = str(e).lower()
        if (
            "401" in err
            or "unauthenticated" in err
            or "permission" in err
            or "invalid authentication" in err
        ):
            return None, AUTH_ERROR_MESSAGE
        return None, (
            "Could not reach the AI service. Please check your internet "
            "connection and API key, then try again."
        )


def call_llm_text(prompt: str) -> tuple[Optional[str], Optional[str]]:
    try:
        raw = _invoke_llm(prompt)
        return raw, None
    except EnvironmentError as e:
        return None, str(e)
    except Exception as e:
        logger.error("LLM text call failed: %s", e)
        err = str(e).lower()
        if (
            "401" in err
            or "unauthenticated" in err
            or "permission" in err
            or "invalid authentication" in err
        ):
            return None, AUTH_ERROR_MESSAGE
        return None, "Could not reach the AI service. Please try again."
