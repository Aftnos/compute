from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import pyautogui
import pyperclip
import pygetwindow

from app.actions.base import Action, ActionContext
from app.actions.browser import BrowserOptions


@dataclass
class TypeTextAction(Action):
    text: str
    mode: str = "key_in"
    interval_ms: Optional[int] = None

    def execute(self, context: ActionContext) -> None:
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

    def execute(self, context: ActionContext) -> None:
        pyautogui.press(self.key)

    def summary(self) -> Dict[str, Any]:
        return {"key": self.key}


@dataclass
class HotkeyAction(Action):
    keys: Iterable[str]

    def execute(self, context: ActionContext) -> None:
        pyautogui.hotkey(*list(self.keys))

    def summary(self) -> Dict[str, Any]:
        return {"keys": list(self.keys)}


@dataclass
class ClickAction(Action):
    x: int
    y: int
    button: str = "left"
    clicks: int = 1

    def execute(self, context: ActionContext) -> None:
        pyautogui.click(x=self.x, y=self.y, button=self.button, clicks=self.clicks)

    def summary(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "button": self.button, "clicks": self.clicks}


@dataclass
class ScrollAction(Action):
    delta: int
    x: Optional[int] = None
    y: Optional[int] = None

    def execute(self, context: ActionContext) -> None:
        pyautogui.scroll(self.delta, x=self.x, y=self.y)

    def summary(self) -> Dict[str, Any]:
        return {"delta": self.delta, "x": self.x, "y": self.y}


@dataclass
class WaitAction(Action):
    ms: int

    def execute(self, context: ActionContext) -> None:
        time.sleep(self.ms / 1000.0)

    def summary(self) -> Dict[str, Any]:
        return {"ms": self.ms}


@dataclass
class FocusWindowAction(Action):
    title_contains: Optional[str] = None

    def execute(self, context: ActionContext) -> None:
        if not self.title_contains:
            return
        windows = pygetwindow.getWindowsWithTitle(self.title_contains)
        if windows:
            windows[0].activate()

    def summary(self) -> Dict[str, Any]:
        return {"title_contains": self.title_contains}


@dataclass
class MoveMouseAction(Action):
    x: int
    y: int
    duration_ms: Optional[int] = None

    def execute(self, context: ActionContext) -> None:
        duration = (self.duration_ms or 0) / 1000.0
        pyautogui.moveTo(self.x, self.y, duration=duration)

    def summary(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "duration_ms": self.duration_ms}


@dataclass
class DragMouseAction(Action):
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    duration_ms: Optional[int] = None

    def execute(self, context: ActionContext) -> None:
        duration = (self.duration_ms or 0) / 1000.0
        pyautogui.moveTo(self.from_x, self.from_y, duration=duration)
        pyautogui.dragTo(self.to_x, self.to_y, duration=duration)

    def summary(self) -> Dict[str, Any]:
        return {
            "from_x": self.from_x,
            "from_y": self.from_y,
            "to_x": self.to_x,
            "to_y": self.to_y,
            "duration_ms": self.duration_ms,
        }


@dataclass
class BrowserOpenAction(Action):
    url: str
    headless: bool = False
    user_data_dir: Optional[str] = None
    profile_dir: Optional[str] = None

    def execute(self, context: ActionContext) -> None:
        if not context.browser:
            raise RuntimeError("浏览器控制器未初始化。")
        options = BrowserOptions(
            headless=self.headless,
            user_data_dir=self.user_data_dir,
            profile_dir=self.profile_dir,
        )
        context.browser.open_url(self.url, options)

    def summary(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "headless": self.headless,
            "user_data_dir": self.user_data_dir,
            "profile_dir": self.profile_dir,
        }


@dataclass
class BrowserClickAction(Action):
    selector: str
    by: str = "css"

    def execute(self, context: ActionContext) -> None:
        if not context.browser:
            raise RuntimeError("浏览器控制器未初始化。")
        context.browser.click_selector(self.selector, by=self.by)

    def summary(self) -> Dict[str, Any]:
        return {"selector": self.selector, "by": self.by}


@dataclass
class BrowserTypeAction(Action):
    selector: str
    text: str
    by: str = "css"
    clear_first: bool = True

    def execute(self, context: ActionContext) -> None:
        if not context.browser:
            raise RuntimeError("浏览器控制器未初始化。")
        context.browser.type_selector(self.selector, self.text, clear_first=self.clear_first, by=self.by)

    def summary(self) -> Dict[str, Any]:
        return {
            "selector": self.selector,
            "text_length": len(self.text),
            "by": self.by,
            "clear_first": self.clear_first,
        }


@dataclass
class BrowserWaitAction(Action):
    selector: str
    by: str = "css"
    timeout_s: int = 10

    def execute(self, context: ActionContext) -> None:
        if not context.browser:
            raise RuntimeError("浏览器控制器未初始化。")
        context.browser.wait_selector(self.selector, timeout_s=self.timeout_s, by=self.by)

    def summary(self) -> Dict[str, Any]:
        return {"selector": self.selector, "by": self.by, "timeout_s": self.timeout_s}


@dataclass
class BrowserPressAction(Action):
    keys: Iterable[str]

    def execute(self, context: ActionContext) -> None:
        if not context.browser:
            raise RuntimeError("浏览器控制器未初始化。")
        context.browser.press_keys(list(self.keys))

    def summary(self) -> Dict[str, Any]:
        return {"keys": list(self.keys)}


@dataclass
class BrowserCloseAction(Action):
    def execute(self, context: ActionContext) -> None:
        if not context.browser:
            return
        context.browser.close()

    def summary(self) -> Dict[str, Any]:
        return {"closed": True}
