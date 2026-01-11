from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.actions import create_action
from app.loggers import RunLogger
from app.models import Flow


class FlowRunner(QObject):
    step_started = pyqtSignal(int, str)
    step_finished = pyqtSignal(int, str)
    run_finished = pyqtSignal(str)

    def __init__(self, flow: Flow, logger: RunLogger, trigger: str) -> None:
        super().__init__()
        self._flow = flow
        self._logger = logger
        self._trigger = trigger
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        self._logger.start_run(self._flow.flow_id, self._flow.name, self._trigger)
        status = "completed"
        for index, step in enumerate(self._flow.steps):
            if self._stop_requested:
                status = "stopped"
                break
            action = create_action(step)
            self.step_started.emit(index, step.action)
            self._logger.log_step_start(index, step.action, action.summary())
            try:
                action.execute()
                self._logger.log_step_finish(index, "success")
                self.step_finished.emit(index, "success")
            except Exception as exc:  # noqa: BLE001
                status = "failed"
                self._logger.log_step_finish(index, "failed", error=str(exc))
                self.step_finished.emit(index, "failed")
                break
        self._logger.finish_run(status)
        self.run_finished.emit(status)


class RunnerThread(QThread):
    def __init__(self, flow: Flow, logger: RunLogger, trigger: str) -> None:
        super().__init__()
        self._runner = FlowRunner(flow, logger, trigger)

    @property
    def runner(self) -> FlowRunner:
        return self._runner

    def run(self) -> None:
        self._runner.run()
