from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.engine import RunnerThread
from app.loggers import RunLogger
from app.models import Flow, Step
from app.storage import load_flows, save_flows
from app.triggers import HotkeyManager, SchedulerManager
from app.ui.step_editor import StepEditorDialog

DEFAULT_HOTKEY = ["ctrl", "alt", "esc"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Windows 自动化工具")
        self.resize(900, 600)

        self._flows: List[Flow] = []
        self._runner_thread: Optional[RunnerThread] = None
        self._log_path = Path("data") / "runs.jsonl"
        self._logger = RunLogger(self._log_path)
        self._current_flow_id: Optional[str] = None

        self._hotkeys = HotkeyManager()
        self._scheduler = SchedulerManager()

        self._flows_list = QListWidget()
        self._flows_list.itemSelectionChanged.connect(self._on_flow_selected)

        self._flow_name_input = QLineEdit()
        self._flow_name_input.setPlaceholderText("请输入流程名称")
        self._steps_list = QListWidget()
        self._steps_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)

        self._load_button = QPushButton("加载流程")
        self._save_button = QPushButton("保存流程")
        self._new_flow_button = QPushButton("新建流程")
        self._delete_flow_button = QPushButton("删除流程")
        self._add_step_button = QPushButton("添加步骤")
        self._edit_step_button = QPushButton("编辑步骤")
        self._remove_step_button = QPushButton("移除步骤")
        self._run_button = QPushButton("运行所选流程")
        self._stop_button = QPushButton("停止")

        self._status_label = QLabel("就绪")

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
        left_panel.addWidget(QLabel("流程列表"))
        left_panel.addWidget(self._flows_list)
        left_panel.addWidget(self._load_button)
        left_panel.addWidget(self._save_button)
        left_panel.addWidget(self._new_flow_button)
        left_panel.addWidget(self._delete_flow_button)
        left_panel.addWidget(self._run_button)
        left_panel.addWidget(self._stop_button)
        left_panel.addStretch()
        left_panel.addWidget(self._status_label)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout()
        editor_layout.addWidget(QLabel("流程名称"))
        editor_layout.addWidget(self._flow_name_input)
        editor_layout.addWidget(QLabel("步骤列表（支持拖拽排序）"))
        editor_layout.addWidget(self._steps_list)
        step_buttons = QHBoxLayout()
        step_buttons.addWidget(self._add_step_button)
        step_buttons.addWidget(self._edit_step_button)
        step_buttons.addWidget(self._remove_step_button)
        editor_layout.addLayout(step_buttons)
        editor_panel.setLayout(editor_layout)

        log_panel = QWidget()
        log_layout = QVBoxLayout()
        log_layout.addWidget(QLabel("运行日志"))
        log_layout.addWidget(self._log_view)
        log_panel.setLayout(log_layout)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Vertical)
        splitter.addWidget(editor_panel)
        splitter.addWidget(log_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout.addLayout(left_panel, 1)
        layout.addWidget(splitter, 2)
        wrapper.setLayout(layout)
        self.setCentralWidget(wrapper)

    def _bind_events(self) -> None:
        self._load_button.clicked.connect(self._load_flows)
        self._save_button.clicked.connect(self._save_flows)
        self._new_flow_button.clicked.connect(self._create_flow)
        self._delete_flow_button.clicked.connect(self._delete_flow)
        self._run_button.clicked.connect(self._run_selected_flow)
        self._stop_button.clicked.connect(self._stop_run)
        self._add_step_button.clicked.connect(self._add_step)
        self._edit_step_button.clicked.connect(self._edit_step)
        self._remove_step_button.clicked.connect(self._remove_step)
        self._flow_name_input.editingFinished.connect(self._update_flow_name)

    def _register_emergency_hotkey(self) -> None:
        try:
            self._hotkeys.register_hotkey("emergency_stop", DEFAULT_HOTKEY, self._stop_run)
        except ValueError:
            QMessageBox.warning(self, "热键冲突", "紧急停止热键发生冲突")

    def _load_flows(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "打开流程文件", "", "JSON (*.json)")
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
        self._status_label.setText(f"已加载 {len(self._flows)} 个流程")
        if self._flows:
            self._flows_list.setCurrentRow(0)

    def _save_flows(self) -> None:
        self._persist_current_flow()
        file_path, _ = QFileDialog.getSaveFileName(self, "保存流程文件", "", "JSON (*.json)")
        if not file_path:
            return
        save_flows(Path(file_path), self._flows)
        self._status_label.setText("流程已保存")

    def _create_flow(self) -> None:
        name, ok = QInputDialog.getText(self, "新建流程", "请输入流程名称")
        if not ok or not name:
            return
        flow = Flow(flow_id=str(uuid4()), name=name, steps=[])
        self._flows.append(flow)
        item = QListWidgetItem(flow.name)
        item.setData(Qt.ItemDataRole.UserRole, flow.flow_id)
        self._flows_list.addItem(item)
        self._flows_list.setCurrentItem(item)
        self._status_label.setText("已创建新流程")

    def _delete_flow(self) -> None:
        flow = self._selected_flow()
        if not flow:
            return
        reply = QMessageBox.question(self, "删除流程", f"确定删除流程 {flow.name} 吗？")
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._flows = [item for item in self._flows if item.flow_id != flow.flow_id]
        current_row = self._flows_list.currentRow()
        self._flows_list.takeItem(current_row)
        if self._current_flow_id == flow.flow_id:
            self._current_flow_id = None
        self._clear_editor()
        self._status_label.setText("已删除流程")

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
                    QMessageBox.warning(self, "热键冲突", f"流程 {flow.name} 的热键发生冲突")
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
            QMessageBox.information(self, "未选择流程", "请先选择要运行的流程")
            return
        self._persist_current_flow()
        self._run_flow(flow, trigger="manual")

    def _run_flow(self, flow: Flow, trigger: str) -> None:
        if self._runner_thread and self._runner_thread.isRunning():
            QMessageBox.warning(self, "流程正在运行", "已有流程正在运行，请先停止")
            return
        self._runner_thread = RunnerThread(flow, self._logger, trigger)
        self._runner_thread.runner.step_started.connect(self._on_step_started)
        self._runner_thread.runner.step_finished.connect(self._on_step_finished)
        self._runner_thread.runner.run_finished.connect(self._on_run_finished)
        self._runner_thread.start()
        self._status_label.setText(f"正在运行 {flow.name}...")

    def _stop_run(self) -> None:
        if self._runner_thread and self._runner_thread.isRunning():
            self._runner_thread.runner.request_stop()
            self._status_label.setText("已请求停止")

    def _on_step_started(self, index: int, action: str) -> None:
        self._log_view.append(f"步骤 {index + 1} 开始：{action}")

    def _on_step_finished(self, index: int, status: str) -> None:
        self._log_view.append(f"步骤 {index + 1} 结束：{status}")

    def _on_run_finished(self, status: str) -> None:
        self._log_view.append(f"运行结束，状态：{status}")
        self._status_label.setText(f"运行状态：{status}")

    def _on_flow_selected(self) -> None:
        self._persist_current_flow()
        flow = self._selected_flow()
        if not flow:
            self._clear_editor()
            return
        self._flow_name_input.setText(flow.name)
        self._steps_list.clear()
        for step in flow.steps:
            item = QListWidgetItem(self._format_step(step))
            item.setData(Qt.ItemDataRole.UserRole, step)
            self._steps_list.addItem(item)
        self._current_flow_id = flow.flow_id

    def _format_step(self, step: Step) -> str:
        labels = {
            "type_text": "输入文本",
            "key_press": "按键",
            "hotkey": "组合键",
            "click": "鼠标点击",
            "scroll": "鼠标滚动",
            "wait": "等待",
            "focus_window": "聚焦窗口",
            "move_mouse": "鼠标移动",
            "drag_mouse": "鼠标拖拽",
            "browser_open": "浏览器打开",
            "browser_click": "浏览器点击",
            "browser_type": "浏览器输入",
            "browser_wait": "浏览器等待",
            "browser_press": "浏览器按键",
            "browser_close": "浏览器关闭",
        }
        label = labels.get(step.action, step.action)
        return f"{label} - {step.params}"

    def _clear_editor(self) -> None:
        self._flow_name_input.clear()
        self._steps_list.clear()

    def _persist_current_flow(self) -> None:
        if not self._current_flow_id:
            return
        flow = next((item for item in self._flows if item.flow_id == self._current_flow_id), None)
        if not flow:
            return
        steps: List[Step] = []
        for index in range(self._steps_list.count()):
            item = self._steps_list.item(index)
            step = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(step, Step):
                steps.append(step)
        flow.steps = steps

    def _update_flow_name(self) -> None:
        flow = self._selected_flow()
        if not flow:
            return
        flow.name = self._flow_name_input.text().strip() or flow.name
        item = self._flows_list.currentItem()
        if item:
            item.setText(flow.name)

    def _add_step(self) -> None:
        flow = self._selected_flow()
        if not flow:
            QMessageBox.information(self, "未选择流程", "请先选择要编辑的流程")
            return
        dialog = StepEditorDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            step = dialog.build_step()
            flow.steps.append(step)
            item = QListWidgetItem(self._format_step(step))
            item.setData(Qt.ItemDataRole.UserRole, step)
            self._steps_list.addItem(item)

    def _edit_step(self) -> None:
        item = self._steps_list.currentItem()
        if not item:
            QMessageBox.information(self, "未选择步骤", "请先选择要编辑的步骤")
            return
        step = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(step, Step):
            return
        dialog = StepEditorDialog(step=step, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_step = dialog.build_step()
            item.setData(Qt.ItemDataRole.UserRole, new_step)
            item.setText(self._format_step(new_step))
            self._persist_current_flow()

    def _remove_step(self) -> None:
        item = self._steps_list.currentItem()
        if not item:
            QMessageBox.information(self, "未选择步骤", "请先选择要移除的步骤")
            return
        row = self._steps_list.row(item)
        self._steps_list.takeItem(row)
        self._persist_current_flow()


def run_app() -> None:
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
