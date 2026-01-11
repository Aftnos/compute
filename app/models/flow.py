from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

StepType = Literal[
    "type_text",
    "key_press",
    "hotkey",
    "click",
    "scroll",
    "wait",
    "focus_window",
    "move_mouse",
    "drag_mouse",
    "browser_open",
    "browser_click",
    "browser_type",
    "browser_wait",
    "browser_press",
    "browser_close",
]


@dataclass
class Step:
    action: StepType
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HotkeyTrigger:
    keys: List[str]


@dataclass
class ScheduleTrigger:
    schedule_type: Literal["daily", "weekly", "cron"]
    expression: str


@dataclass
class Flow:
    flow_id: str
    name: str
    steps: List[Step]
    hotkey: Optional[HotkeyTrigger] = None
    schedule: Optional[ScheduleTrigger] = None
    require_window_focus: bool = False

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "Flow":
        steps = [Step(action=item["action"], params=item.get("params", {})) for item in payload["steps"]]
        hotkey = None
        schedule = None
        if payload.get("hotkey"):
            hotkey = HotkeyTrigger(keys=list(payload["hotkey"]["keys"]))
        if payload.get("schedule"):
            schedule = ScheduleTrigger(
                schedule_type=payload["schedule"]["type"],
                expression=payload["schedule"]["expression"],
            )
        return Flow(
            flow_id=payload["id"],
            name=payload["name"],
            steps=steps,
            hotkey=hotkey,
            schedule=schedule,
            require_window_focus=bool(payload.get("require_window_focus", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.flow_id,
            "name": self.name,
            "steps": [{"action": step.action, "params": step.params} for step in self.steps],
            "hotkey": {"keys": self.hotkey.keys} if self.hotkey else None,
            "schedule": {
                "type": self.schedule.schedule_type,
                "expression": self.schedule.expression,
            }
            if self.schedule
            else None,
            "require_window_focus": self.require_window_focus,
        }
