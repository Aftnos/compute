from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.actions.browser import BrowserController, BrowserOptions
from app.engine import RunnerThread
from app.loggers import RunLogger
from app.models import AppSettings, Flow, ScheduleTrigger, Step
from app.storage import load_flows, load_settings, save_flows, save_settings
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
        self._current_flow_id: Optional[str] = None
        self._settings_path = Path("data") / "settings.json"
        self._settings = load_settings(self._settings_path)
        self._logger = RunLogger(Path(self._settings.log_path))
        self._browser_controller = BrowserController()
        self._startup_queue: List[Flow] = []
        self._startup_trigger: Optional[str] = None

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

        self._startup_hotkey_input = QLineEdit()
        self._startup_schedule_type = QComboBox()
        self._startup_schedule_type.addItem("不启用", userData=None)
        self._startup_schedule_type.addItem("每日", userData="daily")
        self._startup_schedule_type.addItem("每周", userData="weekly")
        self._startup_schedule_type.addItem("Cron", userData="cron")
        self._startup_schedule_expression = QLineEdit()
        self._startup_flow_list = QListWidget()
        self._apply_startup_button = QPushButton("应用启动设置")

        self._log_path_input = QLineEdit()
        self._log_path_button = QPushButton("选择日志文件")
        self._close_browser_check = QCheckBox("任务完成后关闭浏览器")
        self._browser_headless_check = QCheckBox("默认无头模式")
        self._browser_user_data_input = QLineEdit()
        self._browser_profile_input = QLineEdit()
        self._emergency_hotkey_input = QLineEdit()
        self._save_settings_button = QPushButton("保存设置")

        self._status_label = QLabel("就绪")

        self._build_layout()
        self._bind_events()
        self._load_settings_into_ui()
        self._register_emergency_hotkey()
        self._apply_startup_triggers()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._hotkeys.stop()
        self._scheduler.shutdown()
        self._browser_controller.shutdown()
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

        startup_panel = QWidget()
        startup_layout = QVBoxLayout()
        startup_form = QFormLayout()
        startup_form.addRow("启动快捷键(逗号分隔)", self._startup_hotkey_input)
        startup_form.addRow("定时启动类型", self._startup_schedule_type)
        startup_form.addRow("定时表达式", self._startup_schedule_expression)
        startup_layout.addLayout(startup_form)
        startup_layout.addWidget(QLabel("启动任务选择"))
        startup_layout.addWidget(self._startup_flow_list)
        startup_layout.addWidget(self._apply_startup_button)
        startup_panel.setLayout(startup_layout)

        settings_panel = QWidget()
        settings_layout = QVBoxLayout()
        log_group = QGroupBox("日志设置")
        log_layout = QFormLayout()
        log_path_row = QHBoxLayout()
        log_path_row.addWidget(self._log_path_input)
        log_path_row.addWidget(self._log_path_button)
        log_path_widget = QWidget()
        log_path_widget.setLayout(log_path_row)
        log_layout.addRow("日志输出路径", log_path_widget)
        log_group.setLayout(log_layout)

        browser_group = QGroupBox("浏览器设置")
        browser_layout = QFormLayout()
        browser_layout.addRow(self._close_browser_check)
        browser_layout.addRow(self._browser_headless_check)
        browser_layout.addRow("用户数据目录", self._browser_user_data_input)
        browser_layout.addRow("Profile 目录", self._browser_profile_input)
        browser_group.setLayout(browser_layout)

        hotkey_group = QGroupBox("紧急停止热键")
        hotkey_layout = QFormLayout()
        hotkey_layout.addRow("热键(逗号分隔)", self._emergency_hotkey_input)
        hotkey_group.setLayout(hotkey_layout)

        settings_layout.addWidget(log_group)
        settings_layout.addWidget(browser_group)
        settings_layout.addWidget(hotkey_group)
        settings_layout.addWidget(self._save_settings_button)
        settings_layout.addStretch()
        settings_panel.setLayout(settings_layout)

        tab_widget = QTabWidget()
        tab_widget.addTab(editor_panel, "流程编辑")
        tab_widget.addTab(startup_panel, "启动设置")
        tab_widget.addTab(settings_panel, "系统设置")

        log_panel = QWidget()
        log_panel_layout = QVBoxLayout()
        log_panel_layout.addWidget(QLabel("运行日志"))
        log_panel_layout.addWidget(self._log_view)
        log_panel.setLayout(log_panel_layout)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Vertical)
        splitter.addWidget(tab_widget)
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
        self._apply_startup_button.clicked.connect(self._apply_startup_settings)
        self._save_settings_button.clicked.connect(self._save_settings)
        self._log_path_button.clicked.connect(self._choose_log_path)

    def _register_emergency_hotkey(self) -> None:
        try:
            self._hotkeys.unregister_hotkey("emergency_stop")
            hotkey = self._settings.emergency_hotkey or DEFAULT_HOTKEY
            self._hotkeys.register_hotkey("emergency_stop", hotkey, self._stop_run)
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
        self._refresh_startup_flow_list()
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
        self._refresh_startup_flow_list()
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
        self._settings.startup_flow_ids = [
            flow_id for flow_id in self._settings.startup_flow_ids if flow_id != flow.flow_id
        ]
        self._refresh_startup_flow_list()
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
        self._startup_queue = []
        self._startup_trigger = None
        self._run_flow(flow, trigger="manual")

    def _run_flow(self, flow: Flow, trigger: str) -> None:
        if self._runner_thread and self._runner_thread.isRunning():
            QMessageBox.warning(self, "流程正在运行", "已有流程正在运行，请先停止")
            return
        browser_defaults = BrowserOptions(
            headless=self._settings.browser_headless,
            user_data_dir=self._settings.browser_user_data_dir,
            profile_dir=self._settings.browser_profile_dir,
        )
        self._runner_thread = RunnerThread(
            flow,
            self._logger,
            trigger,
            self._browser_controller,
            browser_defaults,
            self._settings.close_browser_on_finish,
        )
        self._runner_thread.runner.step_started.connect(self._on_step_started)
        self._runner_thread.runner.step_finished.connect(self._on_step_finished)
        self._runner_thread.runner.run_finished.connect(self._on_run_finished)
        self._runner_thread.start()
        self._status_label.setText(f"正在运行 {flow.name}...")

    def _stop_run(self) -> None:
        if self._runner_thread and self._runner_thread.isRunning():
            self._runner_thread.runner.request_stop()
            self._status_label.setText("已请求停止")
            self._startup_queue = []
            self._startup_trigger = None

    def _on_step_started(self, index: int, action: str) -> None:
        self._log_view.append(f"步骤 {index + 1} 开始：{action}")

    def _on_step_finished(self, index: int, status: str) -> None:
        self._log_view.append(f"步骤 {index + 1} 结束：{status}")

    def _on_run_finished(self, status: str) -> None:
        self._log_view.append(f"运行结束，状态：{status}")
        self._status_label.setText(f"运行状态：{status}")
        if self._startup_queue:
            next_flow = self._startup_queue.pop(0)
            trigger = self._startup_trigger or "startup"
            self._run_flow(next_flow, trigger=trigger)

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

    def _load_settings_into_ui(self) -> None:
        self._log_path_input.setText(self._settings.log_path)
        self._close_browser_check.setChecked(self._settings.close_browser_on_finish)
        self._browser_headless_check.setChecked(self._settings.browser_headless)
        self._browser_user_data_input.setText(self._settings.browser_user_data_dir or "")
        self._browser_profile_input.setText(self._settings.browser_profile_dir or "")
        self._emergency_hotkey_input.setText(",".join(self._settings.emergency_hotkey or DEFAULT_HOTKEY))
        self._startup_hotkey_input.setText(",".join(self._settings.startup_hotkey))
        self._apply_tooltips()
        if self._settings.startup_schedule:
            index = self._startup_schedule_type.findData(
                self._settings.startup_schedule.schedule_type, role=Qt.ItemDataRole.UserRole
            )
            if index != -1:
                self._startup_schedule_type.setCurrentIndex(index)
            self._startup_schedule_expression.setText(self._settings.startup_schedule.expression)
        else:
            self._startup_schedule_type.setCurrentIndex(0)
            self._startup_schedule_expression.clear()
        self._refresh_startup_flow_list()

    def _save_settings(self) -> None:
        self._settings = self._read_settings_from_ui()
        save_settings(self._settings_path, self._settings)
        self._logger = RunLogger(Path(self._settings.log_path))
        self._status_label.setText("设置已保存")
        self._apply_startup_triggers()
        self._register_emergency_hotkey()

    def _read_settings_from_ui(self) -> AppSettings:
        startup_schedule = None
        schedule_type = self._startup_schedule_type.currentData(Qt.ItemDataRole.UserRole)
        schedule_expression = self._startup_schedule_expression.text().strip()
        if schedule_type and schedule_expression:
            startup_schedule = ScheduleTrigger(
                schedule_type=schedule_type,
                expression=schedule_expression,
            )
        settings = AppSettings(
            log_path=self._log_path_input.text().strip() or "data/runs.jsonl",
            close_browser_on_finish=self._close_browser_check.isChecked(),
            browser_headless=self._browser_headless_check.isChecked(),
            browser_user_data_dir=self._browser_user_data_input.text().strip() or None,
            browser_profile_dir=self._browser_profile_input.text().strip() or None,
            startup_hotkey=self._parse_hotkey(self._startup_hotkey_input.text()),
            emergency_hotkey=self._parse_hotkey(self._emergency_hotkey_input.text()),
            startup_schedule=startup_schedule,
            startup_flow_ids=self._collect_startup_flow_ids(),
        )
        return settings

    def _choose_log_path(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "选择日志输出文件", "", "JSONL (*.jsonl);;所有文件 (*)")
        if file_path:
            self._log_path_input.setText(file_path)

    def _apply_startup_settings(self) -> None:
        self._settings = self._read_settings_from_ui()
        self._apply_startup_triggers()
        self._status_label.setText("启动设置已应用")

    def _apply_startup_triggers(self) -> None:
        self._hotkeys.unregister_hotkey("startup_trigger")
        self._scheduler.remove_job("startup_schedule")
        if self._settings.startup_hotkey:
            try:
                self._hotkeys.register_hotkey(
                    "startup_trigger",
                    self._settings.startup_hotkey,
                    lambda: self._run_startup_flows(trigger="startup_hotkey"),
                )
            except ValueError:
                QMessageBox.warning(self, "热键冲突", "启动热键发生冲突")
        if self._settings.startup_schedule:
            schedule_id = "startup_schedule"
            schedule = self._settings.startup_schedule
            if schedule.schedule_type == "daily":
                self._scheduler.schedule_daily(
                    schedule_id,
                    schedule.expression,
                    lambda: self._run_startup_flows(trigger="startup_schedule"),
                )
            if schedule.schedule_type == "weekly":
                self._scheduler.schedule_weekly(
                    schedule_id,
                    schedule.expression,
                    lambda: self._run_startup_flows(trigger="startup_schedule"),
                )
            if schedule.schedule_type == "cron":
                self._scheduler.schedule_cron(
                    schedule_id,
                    schedule.expression,
                    lambda: self._run_startup_flows(trigger="startup_schedule"),
                )

    def _apply_tooltips(self) -> None:
        self._startup_hotkey_input.setToolTip("填写快捷键组合，例如：ctrl,alt,s。")
        self._startup_schedule_type.setToolTip("选择定时触发类型，未选择则不启用定时启动。")
        self._startup_schedule_expression.setToolTip(
            "每日格式：HH:MM；每周格式：mon,tue@HH:MM；Cron：标准 crontab 表达式。"
        )
        self._startup_flow_list.setToolTip("勾选需要在启动热键或定时触发时执行的流程。")
        self._log_path_input.setToolTip("日志输出文件路径，默认为 data/runs.jsonl。")
        self._close_browser_check.setToolTip("取消勾选可在流程结束后保留浏览器实例。")
        self._browser_headless_check.setToolTip("启用后使用无头模式启动浏览器。")
        self._browser_user_data_input.setToolTip("Chrome 用户数据目录，可复用登录态。")
        self._browser_profile_input.setToolTip("Chrome Profile 目录，例如：Default。")
        self._emergency_hotkey_input.setToolTip("紧急停止热键，默认 ctrl,alt,esc。")

    def _run_startup_flows(self, trigger: str) -> None:
        flows = [flow for flow in self._flows if flow.flow_id in self._settings.startup_flow_ids]
        if not flows:
            QMessageBox.information(self, "启动任务为空", "请先在启动设置中选择要运行的任务")
            return
        if self._runner_thread and self._runner_thread.isRunning():
            QMessageBox.warning(self, "流程正在运行", "已有流程正在运行，请稍后重试")
            return
        self._startup_trigger = trigger
        self._startup_queue = flows[1:]
        self._run_flow(flows[0], trigger=trigger)

    def _refresh_startup_flow_list(self) -> None:
        self._startup_flow_list.clear()
        valid_ids = {flow.flow_id for flow in self._flows}
        self._settings.startup_flow_ids = [flow_id for flow_id in self._settings.startup_flow_ids if flow_id in valid_ids]
        selected = set(self._settings.startup_flow_ids)
        for flow in self._flows:
            item = QListWidgetItem(flow.name)
            item.setData(Qt.ItemDataRole.UserRole, flow.flow_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if flow.flow_id in selected else Qt.CheckState.Unchecked
            )
            self._startup_flow_list.addItem(item)

    def _collect_startup_flow_ids(self) -> List[str]:
        flow_ids: List[str] = []
        for index in range(self._startup_flow_list.count()):
            item = self._startup_flow_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                flow_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(flow_id, str):
                    flow_ids.append(flow_id)
        return flow_ids

    def _parse_hotkey(self, value: str) -> List[str]:
        return [item.strip() for item in value.split(",") if item.strip()]


def run_app() -> None:
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
