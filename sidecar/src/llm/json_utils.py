import json
import re
from typing import Any


def extract_json(text: str) -> dict[str, Any]:
    """Extracts the first JSON object from an LLM response. Tolerates
    markdown fences, leading/trailing prose, and trailing commas."""

    if not text or not isinstance(text, str):
        raise ValueError("Empty LLM response")

    cleaned = text.replace("```json", "").replace("```", "").strip()

    start = cleaned.find("{")
    if start == -1:
        raise ValueError(f"No JSON found in response:\n{cleaned}")

    depth = 0
    end = None
    in_string = False
    escaped = False

    for i in range(start, len(cleaned)):
        char = cleaned[i]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end is None:
        raise ValueError(f"Incomplete or malformed JSON:\n{cleaned}")

    json_str = cleaned[start : end + 1]
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON extracted from LLM:\n{json_str}") from e
