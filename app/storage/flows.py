from __future__ import annotations

import json
from pathlib import Path
from typing import List

from app.models import Flow


def load_flows(path: Path) -> List[Flow]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [Flow.from_dict(item) for item in payload.get("flows", [])]


def save_flows(path: Path, flows: List[Flow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"flows": [flow.to_dict() for flow in flows]}, handle, ensure_ascii=False, indent=2)
