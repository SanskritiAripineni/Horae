"""Configuration for the wellbeing pipeline's LLM layer."""
from __future__ import annotations
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"

DEFAULT_MODEL = "claude-sonnet-4-6"
QUALITY_MODEL = "claude-opus-4-7"

MAX_TOKENS = 2048
TEMPERATURE = 0.3
MAX_RETRIES = 1


def get_api_key() -> str:
    key = os.environ.get(ANTHROPIC_API_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"Missing {ANTHROPIC_API_KEY_ENV}. Export it before calling Layer 4."
        )
    return key
