from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from app.actions.browser import BrowserController


class Action(Protocol):
    def execute(self, context: "ActionContext") -> None:
        ...

    def summary(self) -> Dict[str, Any]:
        ...


@dataclass
class ActionContext:
    require_window_focus: bool = False
    browser: Optional["BrowserController"] = None
