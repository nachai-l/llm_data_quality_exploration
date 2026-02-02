# functions/utils/config.py
"""
Intent (Job Posting DQ project):
- Load and validate YAML configuration files:
  - configs/parameters.yaml
  - configs/prompt.yaml (single system prompt string) OR configs/prompts.yaml (optional legacy)
  - configs/credentials.yaml
- Provide typed config objects (Pydantic) that match THIS repo (job posting DQ), not the old CLO project.
- Keep compatibility helpers:
  - Accept llm.max_rows_per_run as int or "all"
  - Keep silence_client_lv_logs, max_workers, json_only, max_retries
  - Ensure output/cache dirs exist

Primary functions:
- load_parameters(path: str) -> ParametersConfig
- load_prompt(path: str) -> str
- load_prompts(path: str) -> dict[str, str]        (optional legacy support)
- load_credentials(path: str) -> CredentialsConfig
- ensure_dirs(params: ParametersConfig) -> None
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from functions.utils.logging import get_logger


# -----------------------------
# Parameter models (THIS project)
# -----------------------------
class ProjectConfig(BaseModel):
    name: str = "job_posting_dq"
    timezone: str = "Asia/Bangkok"


class InputsConfig(BaseModel):
    # raw sources
    raw_postings_csv: str = "raw_data/Thailand_global_postings.csv"
    raw_jds_csv: str = "raw_data/Thailand_global_raw.csv"
    raw_skills_csv: str = "raw_data/Thailand_global_skills.csv"

    # processed outputs (psv)
    processed_postings_psv: str = "process_data/Thailand_global_postings.psv"
    processed_raw_psv: str = "process_data/Thailand_global_raw.psv"
    processed_skills_psv: str = "process_data/Thailand_global_skills.psv"


class LLMConfig(BaseModel):
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.3

    # progress logging control
    progress_log_every: int = 100

    # Concurrency
    max_workers: int = 4

    # silence Gemini SDK logs
    silence_client_lv_logs: bool = False

    # Strict JSON-only requirement
    json_only: bool = True
    max_retries: int = 3

    # Optional: row limit (None means "all")
    max_rows_per_run: Optional[int] = None

    # Optional: pipeline default force (can still be overridden by pipeline arg)
    force: bool = False

    @field_validator("temperature")
    @classmethod
    def _validate_temperature(cls, v: float) -> float:
        if v < 0.0 or v > 2.0:
            raise ValueError("llm.temperature must be within [0.0, 2.0]")
        return v

    @field_validator("max_workers", "max_retries")
    @classmethod
    def _validate_positive_int(cls, v: int, info) -> int:
        if v <= 0:
            raise ValueError(f"llm.{info.field_name} must be > 0")
        return v

    @field_validator("progress_log_every", mode="before")
    @classmethod
    def _validate_progress_log_every(cls, v: Any) -> int:
        if v is None:
            return 100
        try:
            iv = int(v)
        except Exception as e:
            raise ValueError("llm.progress_log_every must be an integer") from e
        if iv <= 0:
            raise ValueError("llm.progress_log_every must be > 0")
        return iv

    @field_validator("max_rows_per_run", mode="before")
    @classmethod
    def _validate_max_rows_per_run(cls, v: Any) -> Optional[int]:
        """
        Accept:
        - null / None -> None (meaning: run all)
        - "all" -> None
        - int -> int (<=0 treated as all)
        - "10" -> 10 (<=0 treated as all)
        """
        if v is None:
            return None

        if isinstance(v, str):
            s = v.strip().lower()
            if s == "all":
                return None
            try:
                iv = int(s)
            except Exception as e:
                raise ValueError('llm.max_rows_per_run must be "all", null, or an integer') from e
            return None if iv <= 0 else iv

        if isinstance(v, int):
            return None if v <= 0 else v

        raise ValueError('llm.max_rows_per_run must be "all", null, or an integer')


class OutputsConfig(BaseModel):
    artifacts_dir: str = "artifacts"
    cache_dir: str = "artifacts/cache"
    reports_dir: str = "artifacts/reports"

    # pipeline outputs
    job_postings_dq_eval_jsonl: str = "artifacts/job_postings_dq_eval.jsonl"
    job_postings_dq_eval_csv: str = "artifacts/job_postings_dq_eval.csv"


class ParametersConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    inputs: InputsConfig = Field(default_factory=InputsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    outputs: OutputsConfig = Field(default_factory=OutputsConfig)

    # Optional: prompt key name for runner
    prompt_key: str = "job_posting_dq_eval_v1"

    @model_validator(mode="before")
    @classmethod
    def _backward_compat_keys(cls, data: Any) -> Any:
        """
        Backward compatibility:
        - allow older config to use top-level 'input' (singular) instead of 'inputs'
        - allow older config to set outputs under 'artifact_folder' or 'artifact_dir' (best-effort)
        """
        if not isinstance(data, dict):
            return data

        if "inputs" not in data and "input" in data and isinstance(data["input"], dict):
            data["inputs"] = data.pop("input")

        # Try mapping legacy artifact_folder if present
        llm = data.get("llm")
        if isinstance(llm, dict):
            # ignore unknown keys safely; we don't validate artifact_folder in llm
            pass

        return data


# -----------------------------
# Credentials models (same as before)
# -----------------------------
class CredentialsGeminiRequest(BaseModel):
    timeout_seconds: int = 60
    retry_backoff_seconds: int = 2
    max_retry_backoff_seconds: int = 20


class CredentialsGemini(BaseModel):
    api_key_env: str = "GEMINI_API_KEY"
    gcp_project_id: Optional[str] = None
    gcp_location: Optional[str] = None
    request: CredentialsGeminiRequest = Field(default_factory=CredentialsGeminiRequest)


class CredentialsConfig(BaseModel):
    gemini: CredentialsGemini = Field(default_factory=CredentialsGemini)


# -----------------------------
# YAML helpers
# -----------------------------
def _load_yaml(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    with p.open("r", encoding="utf-8") as f:
        text = f.read()

    # sanitize BEFORE YAML parse (fix NBSP / BOM / narrow NBSP)
    for ch in ["\u00A0", "\u2007", "\u202F", "\uFEFF"]:
        text = text.replace(ch, " ")

    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping/object: {path}")
    return data



def load_parameters(path: str = "configs/parameters.yaml") -> ParametersConfig:
    """
    Load and validate parameters.yaml into a typed ParametersConfig (job posting DQ).
    """
    logger = get_logger(__name__)
    raw = _load_yaml(path)
    try:
        params = ParametersConfig.model_validate(raw)
    except ValidationError as e:
        logger.error("Invalid parameters.yaml: %s", e)
        raise
    return params


def load_prompt(path: str = "configs/prompt.yaml") -> str:
    """
    Load single prompt file (your current file is configs/prmpt.yaml - typo).
    Expected YAML:
      System Prompt: |
        ...
    Returns the system prompt string.
    """
    raw = _load_yaml(path)
    # Support either "System Prompt" or "system_prompt" keys
    v = raw.get("System Prompt", None)
    if v is None:
        v = raw.get("system_prompt", None)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{path} must contain a non-empty 'System Prompt' string")
    return v


def load_prompts(path: str = "configs/prompts.yaml") -> Dict[str, str]:
    """
    Optional legacy support: prompts.yaml with meta + prompts mapping.
    (Kept for compatibility with runner patterns that expect a prompt_key -> template map.)
    """
    raw = _load_yaml(path)

    meta = raw.get("meta")
    prompts = raw.get("prompts")

    if meta is None or not isinstance(meta, dict):
        raise ValueError("prompts.yaml missing required 'meta' mapping")
    if prompts is None or not isinstance(prompts, dict):
        raise ValueError("prompts.yaml missing required 'prompts' mapping")

    out: Dict[str, str] = {}
    for k, v in prompts.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError(f"prompts.yaml prompts must be string->string; got {type(k)}->{type(v)} for key={k}")
        out[k] = v

    return out


def load_credentials(path: str = "configs/credentials.yaml") -> CredentialsConfig:
    """
    Load and validate credentials.yaml into a typed CredentialsConfig.
    """
    logger = get_logger(__name__)
    raw = _load_yaml(path)
    try:
        creds = CredentialsConfig.model_validate(raw)
    except ValidationError as e:
        logger.error("Invalid credentials.yaml: %s", e)
        raise
    return creds


def ensure_dirs(params: ParametersConfig) -> None:
    """
    Ensure configured output directories exist.
    """
    dirs = [
        params.outputs.artifacts_dir,
        params.outputs.cache_dir,
        params.outputs.reports_dir,
        "process_data",
        "raw_data",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


__all__ = [
    "ParametersConfig",
    "CredentialsConfig",
    "load_parameters",
    "load_prompt",
    "load_prompts",
    "load_credentials",
    "ensure_dirs",
]
