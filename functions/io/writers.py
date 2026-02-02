"""
Intent:
- Write pipeline artifacts deterministically:
  - jsonl (course bundles, skill sets, alignments)
  - csv (metrics)
  - report files (md/html) delegated to core.reporting

External calls:
- pandas.DataFrame.to_csv
- json (json.dumps)
- pathlib
- functions.utils.logging.get_logger

Primary functions:
- write_jsonl(path, records: list[dict]) -> None
- write_csv(path, df) -> None
- ensure_parent_dir(path) -> None
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

import pandas as pd

from functions.utils.logging import get_logger


def ensure_parent_dir(path: str | Path) -> None:
    """
    Ensure parent directory exists for the given file path.
    Idempotent and safe.
    """
    p = Path(path)
    parent = p.parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: str | Path, records: Sequence[Mapping[str, Any]]) -> None:
    """
    Write records to JSONL deterministically:
    - UTF-8
    - One JSON object per line
    - sort_keys=True for stable output
    - ensure_ascii=False to preserve Thai text
    """
    logger = get_logger(__name__)
    ensure_parent_dir(path)

    p = Path(path)
    with p.open("w", encoding="utf-8") as f:
        for rec in records:
            line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
            f.write(line + "\n")

    logger.info("Wrote JSONL: %s (rows=%d)", str(p), len(records))


def write_csv(path: str | Path, df: pd.DataFrame) -> None:
    """
    Write DataFrame to CSV deterministically:
    - UTF-8
    - index=False
    - stable column order as df.columns
    """
    logger = get_logger(__name__)
    ensure_parent_dir(path)

    p = Path(path)
    df.to_csv(p, index=False, encoding="utf-8")

    logger.info("Wrote CSV: %s (rows=%d, cols=%d)", str(p), int(df.shape[0]), int(df.shape[1]))


__all__ = ["ensure_parent_dir", "write_jsonl", "write_csv"]
