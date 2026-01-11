from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import pyautogui
import pyperclip
import pygetwindow

from app.actions.base import Action


@dataclass
class TypeTextAction(Action):
    text: str
    mode: str = "key_in"
    interval_ms: Optional[int] = None

    def execute(self) -> None:
        if self.mode == "paste":
            pyperclip.copy(self.text)
            pyautogui.hotkey("ctrl", "v")
            return
        interval = (self.interval_ms or 0) / 1000.0
        pyautogui.write(self.text, interval=interval)

    def summary(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "length": len(self.text),
            "interval_ms": self.interval_ms,
        }


@dataclass
class KeyPressAction(Action):
    key: str

    def execute(self) -> None:
        pyautogui.press(self.key)

    def summary(self) -> Dict[str, Any]:
        return {"key": self.key}


@dataclass
class HotkeyAction(Action):
    keys: Iterable[str]

    def execute(self) -> None:
        pyautogui.hotkey(*list(self.keys))

    def summary(self) -> Dict[str, Any]:
        return {"keys": list(self.keys)}


@dataclass
class ClickAction(Action):
    x: int
    y: int
    button: str = "left"
    clicks: int = 1

    def execute(self) -> None:
        pyautogui.click(x=self.x, y=self.y, button=self.button, clicks=self.clicks)

    def summary(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "button": self.button, "clicks": self.clicks}


@dataclass
class ScrollAction(Action):
    delta: int
    x: Optional[int] = None
    y: Optional[int] = None

    def execute(self) -> None:
        pyautogui.scroll(self.delta, x=self.x, y=self.y)

    def summary(self) -> Dict[str, Any]:
        return {"delta": self.delta, "x": self.x, "y": self.y}


@dataclass
class WaitAction(Action):
    ms: int

    def execute(self) -> None:
        time.sleep(self.ms / 1000.0)

    def summary(self) -> Dict[str, Any]:
        return {"ms": self.ms}


@dataclass
class FocusWindowAction(Action):
    title_contains: Optional[str] = None

    def execute(self) -> None:
        if not self.title_contains:
            return
        windows = pygetwindow.getWindowsWithTitle(self.title_contains)
        if windows:
            windows[0].activate()

    def summary(self) -> Dict[str, Any]:
        return {"title_contains": self.title_contains}
