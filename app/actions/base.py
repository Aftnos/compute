from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from app.actions.browser import BrowserController
    from app.actions.browser import BrowserOptions


class Action(Protocol):
    def execute(self, context: "ActionContext") -> None:
        ...

    def summary(self) -> Dict[str, Any]:
        ...


@dataclass
class ActionContext:
    require_window_focus: bool = False
    browser: Optional["BrowserController"] = None
    browser_defaults: Optional["BrowserOptions"] = None
    close_browser_on_finish: bool = True
    should_stop: Callable[[], bool] = field(default_factory=lambda: lambda: False)
