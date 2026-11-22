from __future__ import annotations

import json
import re
from typing import Any


def strip_fences(raw: str) -> str:
    """Strips markdown code fences (```json ... ```) from LLM output."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def parse_json_object(raw: str) -> Any:
    """Parse the first JSON object in `raw`. Raises ValueError if none can be parsed."""
    text = strip_fences(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object found in model output") from None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in model output: {exc}") from exc
