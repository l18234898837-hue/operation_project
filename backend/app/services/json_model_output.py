from __future__ import annotations

import json
import re
from typing import Any


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)


def load_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group("body").strip()

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("model output must be a JSON object")
    return data
