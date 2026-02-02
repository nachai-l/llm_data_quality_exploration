# functions/llm/client.py
"""
Intent:
- Initialize and configure Gemini client using the supported `google.genai` package.
- Central place for:
  - model selection
  - auth via environment variables (.env)
  - client construction (no network calls)

External calls:
- from google import genai
- os.environ for API keys
- functions.utils.logging.get_logger

Primary functions:
- build_gemini_client(credentials_config, model_name_override=None) -> dict
- get_model_name(credentials_config, model_name_override=None) -> str
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from google import genai

from functions.utils.logging import get_logger


def _get(obj: Any, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _resolve_gemini_config(credentials_config: Any) -> Any:
    """
    Accept:
    - full creds object that has `.gemini`
    - already gemini section object
    - dict with {"gemini": {...}} or direct {...}
    """
    if isinstance(credentials_config, dict):
        if isinstance(credentials_config.get("gemini"), dict):
            return credentials_config["gemini"]
        return credentials_config

    gemini_section = getattr(credentials_config, "gemini", None)
    return gemini_section if gemini_section is not None else credentials_config


def get_model_name(credentials_config: Any, *, model_name_override: Optional[str] = None) -> str:
    """
    Resolve model name.

    Priority:
    1) model_name_override (passed by pipeline from parameters.yaml)
    2) credentials_config.model_name (if present)
    3) env var GEMINI_MODEL
    """
    if model_name_override:
        return str(model_name_override)

    cfg = _resolve_gemini_config(credentials_config)

    cfg_model = _get(cfg, "model_name", None)
    if cfg_model:
        return str(cfg_model)

    env_model = os.environ.get("GEMINI_MODEL")
    if env_model:
        return env_model

    raise ValueError("Gemini model name not found (override/credentials/env)")


def build_gemini_client(
    credentials_config: Any,
    *,
    model_name_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build Gemini client context.

    No network calls are made here.
    """
    logger = get_logger(__name__)

    cfg = _resolve_gemini_config(credentials_config)

    api_key_env = _get(cfg, "api_key_env", None)
    if not api_key_env:
        raise ValueError("credentials_config.api_key_env is required")

    api_key = os.environ.get(str(api_key_env))
    if not api_key:
        raise EnvironmentError(f"Environment variable '{api_key_env}' not set for Gemini API key")

    model_name = get_model_name(credentials_config, model_name_override=model_name_override)

    # logger.info("Initializing Gemini client (model=%s)", model_name)

    client = genai.Client(api_key=api_key)

    return {
        "client": client,
        "model_name": model_name,
    }


__all__ = ["build_gemini_client", "get_model_name"]
