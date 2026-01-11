from __future__ import annotations

import json
from pathlib import Path

from app.models import AppSettings


def load_settings(path: Path) -> AppSettings:
    if not path.exists():
        return AppSettings()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return AppSettings.from_dict(payload)


def save_settings(path: Path, settings: AppSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(settings.to_dict(), handle, ensure_ascii=False, indent=2)
