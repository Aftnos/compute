from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.models.flow import ScheduleTrigger


@dataclass
class StartupTriggerConfig:
    hotkey: List[str]
    flow_ids: List[str]


@dataclass
class AppSettings:
    log_path: str = "data/runs.jsonl"
    close_browser_on_finish: bool = True
    browser_headless: bool = False
    browser_user_data_dir: Optional[str] = None
    browser_profile_dir: Optional[str] = None
    startup_hotkey: List[str] = field(default_factory=list)  # Deprecated
    emergency_hotkey: List[str] = field(default_factory=list)
    startup_schedule: Optional[ScheduleTrigger] = None
    startup_flow_ids: List[str] = field(default_factory=list)  # Deprecated
    startup_triggers: List[StartupTriggerConfig] = field(default_factory=list)
    hotkey_trigger_delay: float = 0.5
    last_flows_file: Optional[str] = None

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "AppSettings":
        schedule = None
        schedule_payload = payload.get("startup_schedule")
        if schedule_payload:
            schedule = ScheduleTrigger(
                schedule_type=schedule_payload["type"],
                expression=schedule_payload["expression"],
            )
        
        # Load new triggers
        startup_triggers_data = payload.get("startup_triggers", [])
        startup_triggers = []
        for item in startup_triggers_data:
            startup_triggers.append(StartupTriggerConfig(
                hotkey=list(item.get("hotkey", [])),
                flow_ids=list(item.get("flow_ids", [])),
            ))

        # Migration logic: if no new triggers but old fields exist, create one
        old_hotkey = list(payload.get("startup_hotkey", []))
        old_flow_ids = list(payload.get("startup_flow_ids", []))
        if not startup_triggers and old_hotkey and old_flow_ids:
            startup_triggers.append(StartupTriggerConfig(
                hotkey=old_hotkey,
                flow_ids=old_flow_ids
            ))

        return AppSettings(
            log_path=payload.get("log_path", "data/runs.jsonl"),
            close_browser_on_finish=bool(payload.get("close_browser_on_finish", True)),
            browser_headless=bool(payload.get("browser_headless", False)),
            browser_user_data_dir=payload.get("browser_user_data_dir"),
            browser_profile_dir=payload.get("browser_profile_dir"),
            startup_hotkey=old_hotkey,
            emergency_hotkey=list(payload.get("emergency_hotkey", [])),
            startup_schedule=schedule,
            startup_flow_ids=old_flow_ids,
            startup_triggers=startup_triggers,
            hotkey_trigger_delay=float(payload.get("hotkey_trigger_delay", 0.5)),
            last_flows_file=payload.get("last_flows_file"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_path": self.log_path,
            "close_browser_on_finish": self.close_browser_on_finish,
            "browser_headless": self.browser_headless,
            "browser_user_data_dir": self.browser_user_data_dir,
            "browser_profile_dir": self.browser_profile_dir,
            "startup_hotkey": self.startup_hotkey,
            "emergency_hotkey": self.emergency_hotkey,
            "startup_schedule": {
                "type": self.startup_schedule.schedule_type,
                "expression": self.startup_schedule.expression,
            }
            if self.startup_schedule
            else None,
            "startup_flow_ids": self.startup_flow_ids,
            "startup_triggers": [
                {"hotkey": t.hotkey, "flow_ids": t.flow_ids}
                for t in self.startup_triggers
            ],
            "hotkey_trigger_delay": self.hotkey_trigger_delay,
            "last_flows_file": self.last_flows_file,
        }
