from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class StepLog:
    index: int
    action: str
    params_summary: Dict[str, Any]
    started_at: str
    finished_at: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RunRecord:
    flow_id: str
    flow_name: str
    trigger: str
    status: str = "运行中"
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: Optional[str] = None
    step_logs: List[StepLog] = field(default_factory=list)


class RunLogger:
    def __init__(self, export_path: Path) -> None:
        self._export_path = export_path
        self._current_run: Optional[RunRecord] = None

    def start_run(self, flow_id: str, flow_name: str, trigger: str) -> RunRecord:
        self._current_run = RunRecord(flow_id=flow_id, flow_name=flow_name, trigger=trigger)
        return self._current_run

    def log_step_start(self, index: int, action: str, params_summary: Dict[str, Any]) -> None:
        if not self._current_run:
            return
        entry = StepLog(
            index=index,
            action=action,
            params_summary=params_summary,
            started_at=datetime.utcnow().isoformat(),
        )
        self._current_run.step_logs.append(entry)

    def log_step_finish(self, index: int, status: str, error: Optional[str] = None) -> None:
        if not self._current_run:
            return
        step = next((item for item in self._current_run.step_logs if item.index == index), None)
        if not step:
            return
        step.finished_at = datetime.utcnow().isoformat()
        step.status = status
        step.error = error

    def finish_run(self, status: str) -> Optional[RunRecord]:
        if not self._current_run:
            return None
        self._current_run.status = status
        self._current_run.finished_at = datetime.utcnow().isoformat()
        self._export_run(self._current_run)
        finished = self._current_run
        self._current_run = None
        return finished

    def _export_run(self, record: RunRecord) -> None:
        self._export_path.parent.mkdir(parents=True, exist_ok=True)
        with self._export_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False))
            handle.write("\n")

    def latest_run(self) -> Optional[RunRecord]:
        return self._current_run
