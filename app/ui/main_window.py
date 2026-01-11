from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.engine import RunnerThread
from app.logging import RunLogger
from app.models import Flow
from app.storage import load_flows
from app.triggers import HotkeyManager, SchedulerManager

DEFAULT_HOTKEY = ["ctrl", "alt", "esc"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Windows Automation Tool")
        self.resize(900, 600)

        self._flows: List[Flow] = []
        self._runner_thread: Optional[RunnerThread] = None
        self._log_path = Path("data") / "runs.jsonl"
        self._logger = RunLogger(self._log_path)

        self._hotkeys = HotkeyManager()
        self._scheduler = SchedulerManager()

        self._flows_list = QListWidget()
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)

        self._load_button = QPushButton("Load Flows")
        self._run_button = QPushButton("Run Selected")
        self._stop_button = QPushButton("Stop")

        self._status_label = QLabel("Ready")

        self._build_layout()
        self._bind_events()
        self._register_emergency_hotkey()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._hotkeys.stop()
        self._scheduler.shutdown()
        if self._runner_thread and self._runner_thread.isRunning():
            self._runner_thread.runner.request_stop()
            self._runner_thread.quit()
            self._runner_thread.wait(2000)
        super().closeEvent(event)

    def _build_layout(self) -> None:
        wrapper = QWidget()
        layout = QHBoxLayout()

        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Flows"))
        left_panel.addWidget(self._flows_list)
        left_panel.addWidget(self._load_button)
        left_panel.addWidget(self._run_button)
        left_panel.addWidget(self._stop_button)
        left_panel.addStretch()
        left_panel.addWidget(self._status_label)

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Run Log"))
        right_panel.addWidget(self._log_view)

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 2)
        wrapper.setLayout(layout)
        self.setCentralWidget(wrapper)

    def _bind_events(self) -> None:
        self._load_button.clicked.connect(self._load_flows)
        self._run_button.clicked.connect(self._run_selected_flow)
        self._stop_button.clicked.connect(self._stop_run)

    def _register_emergency_hotkey(self) -> None:
        try:
            self._hotkeys.register_hotkey("emergency_stop", DEFAULT_HOTKEY, self._stop_run)
        except ValueError:
            QMessageBox.warning(self, "Hotkey Conflict", "Emergency stop hotkey conflict detected")

    def _load_flows(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Flow File", "", "JSON (*.json)")
        if not file_path:
            return
        self._hotkeys.stop()
        self._scheduler.shutdown()
        self._hotkeys = HotkeyManager()
        self._scheduler = SchedulerManager()
        self._register_emergency_hotkey()
        self._flows = load_flows(Path(file_path))
        self._flows_list.clear()
        for flow in self._flows:
            item = QListWidgetItem(flow.name)
            item.setData(Qt.ItemDataRole.UserRole, flow.flow_id)
            self._flows_list.addItem(item)
        self._register_flow_triggers()
        self._status_label.setText(f"Loaded {len(self._flows)} flows")

    def _register_flow_triggers(self) -> None:
        for flow in self._flows:
            if flow.hotkey:
                try:
                    self._hotkeys.register_hotkey(
                        f"flow:{flow.flow_id}",
                        flow.hotkey.keys,
                        lambda flow=flow: self._run_flow(flow, trigger="hotkey"),
                    )
                except ValueError:
                    QMessageBox.warning(self, "Hotkey Conflict", f"Hotkey conflict for flow {flow.name}")
            if flow.schedule:
                schedule_id = f"schedule:{flow.flow_id}"
                if flow.schedule.schedule_type == "daily":
                    self._scheduler.schedule_daily(
                        schedule_id,
                        flow.schedule.expression,
                        lambda flow=flow: self._run_flow(flow, trigger="schedule"),
                    )
                if flow.schedule.schedule_type == "weekly":
                    self._scheduler.schedule_weekly(
                        schedule_id,
                        flow.schedule.expression,
                        lambda flow=flow: self._run_flow(flow, trigger="schedule"),
                    )
                if flow.schedule.schedule_type == "cron":
                    self._scheduler.schedule_cron(
                        schedule_id,
                        flow.schedule.expression,
                        lambda flow=flow: self._run_flow(flow, trigger="schedule"),
                    )

    def _selected_flow(self) -> Optional[Flow]:
        item = self._flows_list.currentItem()
        if not item:
            return None
        flow_id = item.data(Qt.ItemDataRole.UserRole)
        return next((flow for flow in self._flows if flow.flow_id == flow_id), None)

    def _run_selected_flow(self) -> None:
        flow = self._selected_flow()
        if not flow:
            QMessageBox.information(self, "No Flow", "Please select a flow to run")
            return
        self._run_flow(flow, trigger="manual")

    def _run_flow(self, flow: Flow, trigger: str) -> None:
        if self._runner_thread and self._runner_thread.isRunning():
            QMessageBox.warning(self, "Flow Running", "A flow is already running")
            return
        self._runner_thread = RunnerThread(flow, self._logger, trigger)
        self._runner_thread.runner.step_started.connect(self._on_step_started)
        self._runner_thread.runner.step_finished.connect(self._on_step_finished)
        self._runner_thread.runner.run_finished.connect(self._on_run_finished)
        self._runner_thread.start()
        self._status_label.setText(f"Running {flow.name}...")

    def _stop_run(self) -> None:
        if self._runner_thread and self._runner_thread.isRunning():
            self._runner_thread.runner.request_stop()
            self._status_label.setText("Stop requested")

    def _on_step_started(self, index: int, action: str) -> None:
        self._log_view.append(f"Step {index + 1} started: {action}")

    def _on_step_finished(self, index: int, status: str) -> None:
        self._log_view.append(f"Step {index + 1} finished: {status}")

    def _on_run_finished(self, status: str) -> None:
        self._log_view.append(f"Run finished with status: {status}")
        self._status_label.setText(f"Run {status}")


def run_app() -> None:
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
