from __future__ import annotations

from typing import Any, Dict

from app.actions.base import Action
from app.actions.definitions import (
    BrowserClickAction,
    BrowserCloseAction,
    BrowserOpenAction,
    BrowserPressAction,
    BrowserTypeAction,
    BrowserWaitAction,
    ClickAction,
    DragMouseAction,
    FocusWindowAction,
    HotkeyAction,
    KeyPressAction,
    MoveMouseAction,
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
    if step.action == "move_mouse":
        return MoveMouseAction(
            x=int(params.get("x", 0)),
            y=int(params.get("y", 0)),
            duration_ms=params.get("duration_ms"),
        )
    if step.action == "drag_mouse":
        return DragMouseAction(
            from_x=int(params.get("from_x", 0)),
            from_y=int(params.get("from_y", 0)),
            to_x=int(params.get("to_x", 0)),
            to_y=int(params.get("to_y", 0)),
            duration_ms=params.get("duration_ms"),
        )
    if step.action == "browser_open":
        return BrowserOpenAction(
            url=str(params.get("url", "")),
            headless=params.get("headless"),
            user_data_dir=params.get("user_data_dir"),
            profile_dir=params.get("profile_dir"),
            use_defaults=bool(params.get("use_defaults", True)),
        )
    if step.action == "browser_click":
        return BrowserClickAction(
            selector=str(params.get("selector", "")),
            by=str(params.get("by", "css")),
        )
    if step.action == "browser_type":
        return BrowserTypeAction(
            selector=str(params.get("selector", "")),
            text=str(params.get("text", "")),
            by=str(params.get("by", "css")),
            clear_first=bool(params.get("clear_first", True)),
        )
    if step.action == "browser_wait":
        return BrowserWaitAction(
            selector=str(params.get("selector", "")),
            by=str(params.get("by", "css")),
            timeout_s=int(params.get("timeout_s", 10)),
        )
    if step.action == "browser_press":
        return BrowserPressAction(keys=list(params.get("keys", [])))
    if step.action == "browser_close":
        return BrowserCloseAction()
    raise ValueError(f"Unsupported action: {step.action}")
