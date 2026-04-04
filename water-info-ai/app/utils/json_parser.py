"""Extract JSON payloads from mixed model outputs."""

from __future__ import annotations

import json
import re
from json import JSONDecodeError


def extract_json(text: str | None, *, expect_array: bool = False):
    if not text:
        return None

    candidates: list[str] = []

    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    candidates.extend(chunk.strip() for chunk in fenced if chunk.strip())

    stripped = text.strip()
    candidates.append(stripped)

    opening = "[" if expect_array else "{"
    closing = "]" if expect_array else "}"
    start = text.find(opening)
    end = text.rfind(closing)
    if start >= 0 and end > start:
        candidates.append(text[start:end + 1].strip())

    if expect_array:
        obj_start = text.find("{")
        obj_end = text.rfind("}")
        if obj_start >= 0 and obj_end > obj_start:
            candidates.append(text[obj_start:obj_end + 1].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            return json.loads(candidate)
        except JSONDecodeError:
            continue
    return None
