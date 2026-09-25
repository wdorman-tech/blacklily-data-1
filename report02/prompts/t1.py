"""T1 fund term extraction. Carried forward from Report No. 01 without change.

The system prompt, user template and field list are imported from No. 01's schema.py so
the continuity comparison uses the identical prompt. Its hash is recorded at freeze time;
if No. 01's file ever changes, the hash check fails.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "no1_schema", Path(__file__).resolve().parents[2] / "src" / "schema.py"
)
_no1 = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_no1)  # type: ignore[union-attr]

FIELDS = _no1.FIELDS
FIELD_NAMES = _no1.FIELD_NAMES
SYSTEM = _no1.SYSTEM_PROMPT
NAIVE_SYSTEM = _no1.NAIVE_SYSTEM_PROMPT
JSON_MODE = True
NUM_PREDICT = 4096


def build_user(document: str) -> str:
    return _no1.build_user_prompt(document)


def build_naive_user(document: str) -> str:
    return _no1.build_naive_user_prompt(document)
