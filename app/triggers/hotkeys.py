from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from pynput import keyboard


@dataclass
class HotkeyBinding:
    name: str
    keys: Tuple[str, ...]
    callback: Callable[[], None]


class HotkeyManager:
    def __init__(self) -> None:
        self._bindings: Dict[str, HotkeyBinding] = {}
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def register_hotkey(self, name: str, keys: List[str], callback: Callable[[], None]) -> None:
        if self._is_conflict(keys):
            raise ValueError("检测到热键冲突")
        self._bindings[name] = HotkeyBinding(name=name, keys=tuple(keys), callback=callback)
        self._refresh_listener()

    def unregister_hotkey(self, name: str) -> None:
        if name in self._bindings:
            self._bindings.pop(name)
            self._refresh_listener()

    def _is_conflict(self, keys: List[str]) -> bool:
        keys_tuple = tuple(keys)
        return any(binding.keys == keys_tuple for binding in self._bindings.values())

    def _refresh_listener(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
        if not self._bindings:
            return
        
        hotkeys = {}
        for binding in self._bindings.values():
            pynput_keys = "+".join(self._format_key(k) for k in binding.keys)
            hotkeys[pynput_keys] = binding.callback
            
        self._listener = keyboard.GlobalHotKeys(hotkeys)
        self._listener.start()

    def _format_key(self, key: str) -> str:
        key = key.lower()
        if key == "win":
            return "<cmd>"
        if len(key) > 1:
            return f"<{key}>"
        return key

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._bindings.clear()
