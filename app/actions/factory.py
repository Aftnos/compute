from __future__ import annotations

from typing import Any, Dict

from app.actions.base import Action
from app.actions.definitions import (
    ClickAction,
    FocusWindowAction,
    HotkeyAction,
    KeyPressAction,
    ScrollAction,
    TypeTextAction,
    WaitAction,
)
from app.models import Step


def create_action(step: Step) -> Action:
    params: Dict[str, Any] = step.params
    if step.action == "type_text":
        return TypeTextAction(
            text=str(params.get("text", "")),
            mode=str(params.get("mode", "key_in")),
            interval_ms=params.get("interval_ms"),
        )
    if step.action == "key_press":
        return KeyPressAction(key=str(params.get("key", "")))
    if step.action == "hotkey":
        return HotkeyAction(keys=list(params.get("keys", [])))
    if step.action == "click":
        return ClickAction(
            x=int(params.get("x", 0)),
            y=int(params.get("y", 0)),
            button=str(params.get("button", "left")),
            clicks=int(params.get("clicks", 1)),
        )
    if step.action == "scroll":
        return ScrollAction(
            delta=int(params.get("delta", 0)),
            x=params.get("x"),
            y=params.get("y"),
        )
    if step.action == "wait":
        return WaitAction(ms=int(params.get("ms", 0)))
    if step.action == "focus_window":
        return FocusWindowAction(title_contains=params.get("title_contains"))
    raise ValueError(f"Unsupported action: {step.action}")
