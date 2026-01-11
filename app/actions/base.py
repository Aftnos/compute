from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol


class Action(Protocol):
    def execute(self) -> None:
        ...

    def summary(self) -> Dict[str, Any]:
        ...


@dataclass
class ActionContext:
    require_window_focus: bool = False

