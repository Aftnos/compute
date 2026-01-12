from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
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
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
    QSizePolicy,
)

from app.actions.browser import BrowserController, BrowserOptions
from app.engine import RunnerThread
from app.loggers import RunLogger
from app.models import AppSettings, Flow, ScheduleTrigger, Step
from app.storage import load_flows, load_settings, save_flows, save_settings
from app.triggers import HotkeyManager, SchedulerManager
from app.ui.step_editor import StepEditorDialog
from app.ui.tray_icon import SystemTrayIcon
from app.ui.floating_window import FloatingWindow

DEFAULT_HOTKEY = ["ctrl", "alt", "esc"]


class StartupTriggerDialog(QDialog):
    def __init__(
        self,
        flows: List[Flow],
        initial_hotkey: List[str] = None,
        initial_flow_ids: List[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑启动触发器")
        self.resize(500, 400)
        
        self._flows = flows
        self._hotkey_keys = initial_hotkey or []
        self._selected_flow_ids = set(initial_flow_ids or [])
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Hotkey Section
        hotkey_group = QGroupBox("触发热键")
        hotkey_layout = QHBoxLayout()
        self._hotkey_input = QLineEdit()
        self._hotkey_input.setReadOnly(True)
        self._hotkey_input.setText("+".join(self._hotkey_keys))
        self._set_hotkey_btn = QPushButton("设置热键")
        self._set_hotkey_btn.clicked.connect(self._capture_hotkey)
        hotkey_layout.addWidget(self._hotkey_input)
        hotkey_layout.addWidget(self._set_hotkey_btn)
        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)
        
        # Flows Section
        flow_group = QGroupBox("执行任务 (按顺序执行)")
        flow_layout = QVBoxLayout()
        self._flow_list = QListWidget()
        self._populate_flows()
        flow_layout.addWidget(self._flow_list)
        flow_group.setLayout(flow_layout)
        layout.addWidget(flow_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._save_btn = QPushButton("保存")
        self._cancel_btn = QPushButton("取消")
        self._save_btn.clicked.connect(self.accept)
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def _populate_flows(self) -> None:
        self._flow_list.clear()
        for flow in self._flows:
            item = QListWidgetItem(flow.name)
            item.setData(Qt.ItemDataRole.UserRole, flow.flow_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if flow.flow_id in self._selected_flow_ids
                else Qt.CheckState.Unchecked
            )
            self._flow_list.addItem(item)

    def _capture_hotkey(self) -> None:
        dialog = HotkeyCaptureDialog(self._hotkey_keys, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._hotkey_keys = dialog.keys
            self._hotkey_input.setText("+".join(self._hotkey_keys))

    @property
    def trigger_config(self) -> StartupTriggerConfig:
        selected_ids = []
        for index in range(self._flow_list.count()):
            item = self._flow_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected_ids.append(item.data(Qt.ItemDataRole.UserRole))
        return StartupTriggerConfig(
            hotkey=self._hotkey_keys,
            flow_ids=selected_ids
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Af自动化")
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
        # self._startup_hotkey_keys: List[str] = [] # Removed
        self._emergency_hotkey_keys: List[str] = []

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

        # Startup Triggers UI
        self._startup_triggers_list = QListWidget()
        self._add_trigger_btn = QPushButton("添加热键启动")
        self._edit_trigger_btn = QPushButton("编辑")
        self._del_trigger_btn = QPushButton("删除")
        
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
        self._emergency_hotkey_input.setReadOnly(True)
        self._emergency_hotkey_set_button = QPushButton("设置热键")
        self._emergency_hotkey_add_button = QPushButton("重新录入")
        self._save_settings_button = QPushButton("保存设置")

        self._status_label = QLabel("就绪")
        
        self._tray_icon = SystemTrayIcon(self)
        self._floating_window = FloatingWindow()

        self._build_layout()
        self._bind_events()
        self._bind_tray_events()
        self._load_settings_into_ui()
        self._register_emergency_hotkey()
        self._apply_startup_triggers()
        self._load_last_flows()

    def _bind_tray_events(self) -> None:
        self._tray_icon.show_window_requested.connect(self._show_main_window)
        self._tray_icon.toggle_floating_window_requested.connect(self._toggle_floating_window)
        self._floating_window.stop_requested.connect(self._stop_run)
        self._floating_window.restore_requested.connect(self._show_main_window)

    def _show_main_window(self) -> None:
        self.showNormal()
        self.activateWindow()
        # 恢复主窗口时，隐藏悬浮窗（可选策略，根据用户习惯调整）
        self._toggle_floating_window(False)

    def _toggle_floating_window(self, visible: bool) -> None:
        if visible:
            self._floating_window.show()
        else:
            self._floating_window.hide()
        self._tray_icon.set_floating_checked(visible)

    def shutdown(self) -> None:
        self._hotkeys.stop()
        self._scheduler.shutdown()
        self._browser_controller.shutdown()
        if self._runner_thread and self._runner_thread.isRunning():
            self._runner_thread.runner.request_stop()
            self._runner_thread.quit()
            self._runner_thread.wait(2000)

    def closeEvent(self, event) -> None:
        reply = QMessageBox(self)
        reply.setWindowTitle("关闭确认")
        reply.setText("您想要执行什么操作？")
        minimize_btn = reply.addButton("最小化到托盘", QMessageBox.ButtonRole.ActionRole)
        exit_btn = reply.addButton("退出程序", QMessageBox.ButtonRole.DestructiveRole)
        reply.addButton("取消", QMessageBox.ButtonRole.RejectRole)

        reply.exec()

        if reply.clickedButton() == minimize_btn:
            event.ignore()
            self.hide()
            self._tray_icon.showMessage(
                "Windows 自动化工具",
                "程序已最小化到系统托盘运行",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            # 最小化到托盘时，自动显示悬浮窗
            self._toggle_floating_window(True)
        elif reply.clickedButton() == exit_btn:
            event.accept()
            QApplication.instance().quit()
        else:
            event.ignore()

    def _build_layout(self) -> None:
        wrapper = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 左侧面板：流程列表与操作
        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)
        
        # 顶部工具栏区域（新建/加载/保存）
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)
        self._new_flow_button.setToolTip("新建流程")
        self._load_button.setToolTip("加载流程文件")
        self._save_button.setToolTip("保存当前流程")
        # 可以用图标替代，这里暂时简化按钮文字
        self._new_flow_button.setText("新建")
        self._load_button.setText("加载")
        self._save_button.setText("保存")
        
        toolbar.addWidget(self._new_flow_button)
        toolbar.addWidget(self._load_button)
        toolbar.addWidget(self._save_button)
        left_panel.addLayout(toolbar)

        # 流程列表
        list_label = QLabel("流程列表")
        list_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        left_panel.addWidget(list_label)
        left_panel.addWidget(self._flows_list)

        # 底部操作区（删除、运行、停止）
        bottom_actions = QVBoxLayout()
        bottom_actions.setSpacing(8)
        
        self._delete_flow_button.setText("删除选定流程")
        
        self._run_button.setObjectName("RunButton")
        self._run_button.setText("▶ 运行流程")
        self._run_button.setFixedHeight(40)
        
        self._stop_button.setObjectName("StopButton")
        self._stop_button.setText("■ 停止运行")
        self._stop_button.setFixedHeight(40)
        self._stop_button.setEnabled(False)  # 初始禁用停止按钮

        bottom_actions.addWidget(self._delete_flow_button)
        bottom_actions.addWidget(self._run_button)
        bottom_actions.addWidget(self._stop_button)
        
        left_panel.addLayout(bottom_actions)
        left_panel.addStretch()
        left_panel.addWidget(self._status_label)

        left_widget = QWidget()
        left_widget.setLayout(left_panel)

        # 右侧内容区
        right_panel = QVBoxLayout()
        right_panel.setSpacing(0)
        right_panel.setContentsMargins(0, 0, 0, 0)

        # 1. 流程编辑器优化
        editor_panel = QWidget()
        editor_layout = QVBoxLayout()
        editor_layout.setContentsMargins(15, 15, 15, 15)
        editor_layout.setSpacing(12)
        
        name_layout = QVBoxLayout()
        name_layout.setSpacing(5)
        name_layout.addWidget(QLabel("流程名称"))
        self._flow_name_input.setFixedHeight(32)
        name_layout.addWidget(self._flow_name_input)
        editor_layout.addLayout(name_layout)
        
        editor_layout.addWidget(QLabel("步骤列表（支持拖拽排序）"))
        editor_layout.addWidget(self._steps_list)
        
        step_buttons = QHBoxLayout()
        step_buttons.setSpacing(10)
        self._add_step_button.setFixedHeight(32)
        self._edit_step_button.setFixedHeight(32)
        self._remove_step_button.setFixedHeight(32)
        step_buttons.addWidget(self._add_step_button)
        step_buttons.addWidget(self._edit_step_button)
        step_buttons.addWidget(self._remove_step_button)
        editor_layout.addLayout(step_buttons)
        editor_panel.setLayout(editor_layout)

        # 2. 启动设置优化
        startup_panel = QWidget()
        startup_layout = QVBoxLayout()
        startup_layout.setContentsMargins(15, 15, 15, 15)
        startup_layout.setSpacing(15)
        
        # Trigger List Group
        trigger_group = QGroupBox("热键启动配置")
        trigger_layout = QVBoxLayout()
        trigger_layout.addWidget(QLabel("已配置的热键列表:"))
        trigger_layout.addWidget(self._startup_triggers_list)
        
        trigger_btns = QHBoxLayout()
        self._add_trigger_btn.setFixedHeight(30)
        self._edit_trigger_btn.setFixedHeight(30)
        self._del_trigger_btn.setFixedHeight(30)
        trigger_btns.addWidget(self._add_trigger_btn)
        trigger_btns.addWidget(self._edit_trigger_btn)
        trigger_btns.addWidget(self._del_trigger_btn)
        trigger_layout.addLayout(trigger_btns)
        trigger_group.setLayout(trigger_layout)
        
        startup_layout.addWidget(trigger_group)
        
        # Schedule Group
        schedule_group = QGroupBox("定时启动配置")
        schedule_form = QFormLayout()
        schedule_form.setSpacing(10)
        schedule_form.addRow("定时类型:", self._startup_schedule_type)
        schedule_form.addRow("表达式:", self._startup_schedule_expression)
        schedule_group.setLayout(schedule_form)
        
        startup_layout.addWidget(schedule_group)
        
        self._apply_startup_button.setFixedHeight(36)
        startup_layout.addWidget(self._apply_startup_button)
        startup_panel.setLayout(startup_layout)

        # 3. 系统设置优化
        settings_panel = QWidget()
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(15)
        
        # 日志组
        log_group = QGroupBox("日志设置")
        log_layout = QFormLayout()
        log_layout.setSpacing(10)
        log_path_row = QHBoxLayout()
        log_path_row.addWidget(self._log_path_input)
        log_path_row.addWidget(self._log_path_button)
        log_layout.addRow("日志输出路径:", log_path_row)
        log_group.setLayout(log_layout)
        
        # 浏览器组
        browser_group = QGroupBox("浏览器设置")
        browser_layout = QFormLayout()
        browser_layout.setSpacing(10)
        
        # 使用水平布局放两个 CheckBox
        checks_layout = QHBoxLayout()
        checks_layout.addWidget(self._close_browser_check)
        checks_layout.addWidget(self._browser_headless_check)
        checks_layout.addStretch()
        
        browser_layout.addRow(checks_layout)
        browser_layout.addRow("用户数据目录:", self._browser_user_data_input)
        browser_layout.addRow("Profile 目录:", self._browser_profile_input)
        browser_group.setLayout(browser_layout)
        
        # 热键组
        hotkey_group = QGroupBox("紧急停止热键")
        hotkey_layout = QFormLayout()
        emergency_hotkey_row = QHBoxLayout()
        self._emergency_hotkey_input.setFixedHeight(30)
        self._emergency_hotkey_set_button.setFixedHeight(30)
        self._emergency_hotkey_add_button.setFixedHeight(30)
        emergency_hotkey_row.addWidget(self._emergency_hotkey_input)
        emergency_hotkey_row.addWidget(self._emergency_hotkey_set_button)
        emergency_hotkey_row.addWidget(self._emergency_hotkey_add_button)
        hotkey_layout.addRow("热键设置:", emergency_hotkey_row)
        hotkey_group.setLayout(hotkey_layout)
        
        settings_layout.addWidget(log_group)
        settings_layout.addWidget(browser_group)
        settings_layout.addWidget(hotkey_group)
        
        self._save_settings_button.setFixedHeight(36)
        settings_layout.addWidget(self._save_settings_button)
        settings_layout.addStretch()
        settings_panel.setLayout(settings_layout)

        # Tab Widget
        tab_widget = QTabWidget()
        tab_widget.addTab(editor_panel, "流程编辑")
        tab_widget.addTab(startup_panel, "启动设置")
        tab_widget.addTab(settings_panel, "系统设置")

        # 日志面板
        log_panel = QWidget()
        log_panel_layout = QVBoxLayout()
        log_panel_layout.setContentsMargins(0, 10, 0, 0)
        log_label = QLabel("运行日志")
        log_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        log_panel_layout.addWidget(log_label)
        log_panel_layout.addWidget(self._log_view)
        log_panel.setLayout(log_panel_layout)

        # 右侧分割器（Tab + Log）
        right_splitter = QSplitter()
        right_splitter.setOrientation(Qt.Orientation.Vertical)
        right_splitter.addWidget(tab_widget)
        right_splitter.addWidget(log_panel)
        right_splitter.setStretchFactor(0, 7)  # Tab 占 70%
        right_splitter.setStretchFactor(1, 3)  # Log 占 30%

        # 主分割器
        main_splitter = QSplitter()
        main_splitter.setOrientation(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 3)  # 左侧占 30%
        main_splitter.setStretchFactor(1, 7)  # 右侧占 70%
        
        layout.addWidget(main_splitter)
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
        self._add_trigger_btn.clicked.connect(self._add_startup_trigger)
        self._edit_trigger_btn.clicked.connect(self._edit_startup_trigger)
        self._del_trigger_btn.clicked.connect(self._remove_startup_trigger)
        self._emergency_hotkey_set_button.clicked.connect(lambda: self._capture_hotkey("emergency", append=False))
        self._emergency_hotkey_add_button.clicked.connect(lambda: self._capture_hotkey("emergency", append=False))

    def _register_emergency_hotkey(self) -> None:
        try:
            self._hotkeys.unregister_hotkey("emergency_stop")
            hotkey = self._settings.emergency_hotkey or DEFAULT_HOTKEY
            self._hotkeys.register_hotkey("emergency_stop", hotkey, self._stop_run)
        except ValueError:
            QMessageBox.warning(self, "热键冲突", "紧急停止热键发生冲突")

    def _load_last_flows(self) -> None:
        if self._settings.last_flows_file:
            path = Path(self._settings.last_flows_file)
            if path.exists():
                self._load_flows_from_path(path)

    def _load_flows_from_path(self, path: Path) -> None:
        self._hotkeys.stop()
        self._scheduler.shutdown()
        self._hotkeys = HotkeyManager()
        self._scheduler = SchedulerManager()
        self._register_emergency_hotkey()
        self._flows = load_flows(path)
        self._flows_list.clear()
        for flow in self._flows:
            item = QListWidgetItem(flow.name)
            item.setData(Qt.ItemDataRole.UserRole, flow.flow_id)
            self._flows_list.addItem(item)
        # self._refresh_startup_flow_list() # Removed
        self._status_label.setText(f"已加载 {len(self._flows)} 个流程")
        if self._flows:
            self._flows_list.setCurrentRow(0)

    def _load_flows(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "打开流程文件", "", "JSON (*.json)")
        if not file_path:
            return
        path = Path(file_path)
        self._load_flows_from_path(path)
        # 更新并保存设置
        self._settings.last_flows_file = str(path)
        self._save_settings_silent()

    def _save_flows(self) -> None:
        self._persist_current_flow()
        file_path, _ = QFileDialog.getSaveFileName(self, "保存流程文件", "", "JSON (*.json)")
        if not file_path:
            return
        path = Path(file_path)
        save_flows(path, self._flows)
        self._status_label.setText("流程已保存")
        # 更新并保存设置
        self._settings.last_flows_file = str(path)
        self._save_settings_silent()

    def _save_settings_silent(self) -> None:
        # 保存设置但不更新 UI 和弹出提示，用于后台保存 last_flows_file
        save_settings(self._settings_path, self._settings)

    def _create_flow(self) -> None:
        name, ok = QInputDialog.getText(self, "新建流程", "请输入流程名称")
        if not ok or not name:
            return
        flow = Flow(flow_id=str(uuid4()), name=name, steps=[])
        self._flows.append(flow)
        item = QListWidgetItem(flow.name)
        item.setData(Qt.ItemDataRole.UserRole, flow.flow_id)
        self._flows_list.addItem(item)
        # self._refresh_startup_flow_list() # Removed
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
            
        # Remove flow from startup triggers
        for trigger in self._settings.startup_triggers:
            if flow.flow_id in trigger.flow_ids:
                trigger.flow_ids.remove(flow.flow_id)
        # Reload triggers UI
        self._load_settings_into_ui()
        
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
        self._floating_window.update_status("正在启动...", is_running=True, flow_name=flow.name)

    def _stop_run(self) -> None:
        if self._runner_thread and self._runner_thread.isRunning():
            self._runner_thread.runner.request_stop()
            self._status_label.setText("已请求停止")
            self._startup_queue = []
            self._startup_trigger = None

    def _on_step_started(self, index: int, action: str) -> None:
        self._log_view.append(f"步骤 {index + 1} 开始：{action}")
        flow_name = self._runner_thread.flow.name if self._runner_thread else None
        self._floating_window.update_status(f"执行步骤 {index + 1}: {action}", is_running=True, flow_name=flow_name)

    def _on_step_finished(self, index: int, status: str) -> None:
        self._log_view.append(f"步骤 {index + 1} 结束：{status}")

    def _on_run_finished(self, status: str) -> None:
        self._log_view.append(f"运行结束，状态：{status}")
        self._status_label.setText(f"运行状态：{status}")
        self._status_label.setStyleSheet("")  # 恢复默认样式
        self._run_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._floating_window.update_status(f"就绪 (上一次: {status})", is_running=False)
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
        for index, step in enumerate(flow.steps):
            item = QListWidgetItem(self._format_step(step, index + 1))
            item.setData(Qt.ItemDataRole.UserRole, step)
            self._steps_list.addItem(item)
        self._current_flow_id = flow.flow_id

    def _format_step(self, step: Step, index: int) -> str:
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
        
        action_name = labels.get(step.action, step.action)
        
        # 格式化参数显示
        params_str = ""
        p = step.params
        
        if step.action == "click":
            btn = "左键" if p.get("button") == "left" else "右键"
            clicks = f"{p.get('clicks')}次" if p.get("clicks", 1) > 1 else ""
            params_str = f"坐标({p.get('x')}, {p.get('y')}) {btn}{clicks}"
            
        elif step.action == "type_text":
            text = p.get("text", "")
            if len(text) > 20:
                text = text[:20] + "..."
            params_str = f"内容: \"{text}\""
            
        elif step.action == "wait":
            params_str = f"{p.get('seconds')} 秒"
            
        elif step.action == "scroll":
            direction = "向下" if p.get("dy", 0) < 0 else "向上"
            amount = abs(p.get("dy", 0))
            params_str = f"{direction}滚动 {amount}"
            
        elif step.action == "key_press":
            params_str = f"按键: {p.get('key')}"
            
        elif step.action == "hotkey":
            keys = "+".join(p.get("keys", []))
            params_str = f"组合键: {keys}"
            
        elif step.action == "browser_open":
            url = p.get("url", "")
            if len(url) > 30:
                url = url[:30] + "..."
            params_str = f"打开: {url}"
            
        else:
            # 默认显示方式，过滤掉一些不重要的参数
            display_params = {k: v for k, v in p.items() if v not in [None, "", 0]}
            if display_params:
                params_str = str(display_params)

        if params_str:
            return f"{index}. {action_name} - {params_str}"
        return f"{index}. {action_name}"

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
            # 使用新列表长度作为索引
            index = len(flow.steps)
            item = QListWidgetItem(self._format_step(step, index))
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
            # 获取当前行号并加1作为步骤序号
            current_row = self._steps_list.row(item)
            item.setText(self._format_step(new_step, current_row + 1))
            self._persist_current_flow()

    def _remove_step(self) -> None:
        item = self._steps_list.currentItem()
        if not item:
            QMessageBox.information(self, "未选择步骤", "请先选择要移除的步骤")
            return
        row = self._steps_list.row(item)
        self._steps_list.takeItem(row)
        self._persist_current_flow()
        # 移除步骤后刷新整个列表以更新序号
        self._on_flow_selected()

    def _load_settings_into_ui(self) -> None:
        self._log_path_input.setText(self._settings.log_path)
        self._close_browser_check.setChecked(self._settings.close_browser_on_finish)
        self._browser_headless_check.setChecked(self._settings.browser_headless)
        self._browser_user_data_input.setText(self._settings.browser_user_data_dir or "")
        self._browser_profile_input.setText(self._settings.browser_profile_dir or "")
        self._emergency_hotkey_keys = list(self._settings.emergency_hotkey or DEFAULT_HOTKEY)
        self._update_hotkey_display()
        self._apply_tooltips()
        
        # Load Triggers
        self._startup_triggers_list.clear()
        for trigger in self._settings.startup_triggers:
            self._add_trigger_to_list(trigger)
            
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

    def _add_trigger_to_list(self, trigger: StartupTriggerConfig) -> None:
        hotkey_str = "+".join(trigger.hotkey)
        flow_names = []
        for flow_id in trigger.flow_ids:
            flow = next((f for f in self._flows if f.flow_id == flow_id), None)
            if flow:
                flow_names.append(flow.name)
            else:
                flow_names.append(f"Unknown({flow_id})")
        
        display_text = f"[{hotkey_str}] -> {', '.join(flow_names)}"
        item = QListWidgetItem(display_text)
        item.setData(Qt.ItemDataRole.UserRole, trigger)
        self._startup_triggers_list.addItem(item)

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
            startup_hotkey=list(self._startup_hotkey_keys),
            emergency_hotkey=list(self._emergency_hotkey_keys),
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
        # Clear old triggers (prefix based to be safe, but unregister_hotkey needs exact name)
        # We don't have a way to list registered hotkeys easily, so we rely on the fact that
        # we only register what we know. But when settings change, we need to unregister old ones.
        # A better approach is to stop the hotkey manager and restart, or keep track of registered names.
        # For now, let's assume we can just re-register everything because HotkeyManager clears on reload?
        # Actually, HotkeyManager.stop() clears everything. But we have flow triggers too.
        # Let's unregister all "startup_trigger_*"
        
        # Since HotkeyManager doesn't support wildcard unregister, and we don't track IDs,
        # we might have a leak if we change hotkeys frequently without restart.
        # However, HotkeyManager overwrites if we use same name.
        # But here names will be dynamic "startup_trigger_{i}".
        # So we should unregister a range or just reload everything.
        # Let's restart all hotkeys to be safe.
        self._hotkeys.stop()
        self._hotkeys = HotkeyManager()
        self._register_emergency_hotkey()
        self._register_flow_triggers()
        
        self._scheduler.remove_job("startup_schedule")
        
        for index, trigger in enumerate(self._settings.startup_triggers):
            if trigger.hotkey:
                try:
                    self._hotkeys.register_hotkey(
                        f"startup_trigger_{index}",
                        trigger.hotkey,
                        lambda t=trigger: self._run_startup_flows(t, trigger="startup_hotkey"),
                    )
                except ValueError:
                    # Ignore conflicts for now or log
                    pass
                    
        if self._settings.startup_schedule:
            # For schedule, we need to decide what flows to run.
            # The current schedule model only supports one schedule for "startup".
            # But which flows? The old model had `startup_flow_ids`.
            # The new model doesn't really have a concept of "default startup flows" unless we designate one trigger as default?
            # Or we keep `startup_flow_ids` for schedule?
            # Wait, `startup_schedule` is global.
            # Let's assume for now schedule runs the first trigger's flows or we need to add flow selection to schedule.
            # Given the UI didn't change for schedule (it's still one global schedule), let's say it runs ALL triggers?
            # Or maybe we should have migrated `startup_flow_ids` to be used by schedule.
            # Let's use the flows from the FIRST trigger if available, or just empty.
            # Actually, the user requirement was "Startup hotkey can be set multiple times".
            # It didn't explicitly say about schedule.
            # But `startup_flow_ids` is deprecated.
            # Let's assume schedule runs the flows from the first defined trigger for now as a fallback,
            # OR we should have kept `startup_flow_ids` for the schedule.
            # Let's use the first trigger's flows for schedule for simplicity, or all of them.
            # Let's run ALL startup triggers' flows sequentially? No that's weird.
            # Let's just pick the first trigger config as the "default" one for schedule.
            
            flows_to_run = []
            if self._settings.startup_triggers:
                flows_to_run = self._settings.startup_triggers[0].flow_ids
            
            schedule_id = "startup_schedule"
            schedule = self._settings.startup_schedule
            
            # We need a wrapper to run flows by IDs
            def run_schedule_flows():
                flows = [f for f in self._flows if f.flow_id in flows_to_run]
                if flows:
                    self._run_flow_sequence(flows, "startup_schedule")

            if schedule.schedule_type == "daily":
                self._scheduler.schedule_daily(schedule_id, schedule.expression, run_schedule_flows)
            elif schedule.schedule_type == "weekly":
                self._scheduler.schedule_weekly(schedule_id, schedule.expression, run_schedule_flows)
            elif schedule.schedule_type == "cron":
                self._scheduler.schedule_cron(schedule_id, schedule.expression, run_schedule_flows)

    def _apply_tooltips(self) -> None:
        self._add_trigger_btn.setToolTip("添加一个新的热键启动项")
        self._startup_schedule_type.setToolTip("选择定时触发类型，未选择则不启用定时启动。")
        self._startup_schedule_expression.setToolTip(
            "每日格式：HH:MM；每周格式：mon,tue@HH:MM；Cron：标准 crontab 表达式。"
        )
        self._log_path_input.setToolTip("日志输出文件路径，默认为 data/runs.jsonl。")
        self._close_browser_check.setToolTip("取消勾选可在流程结束后保留浏览器实例。")
        self._browser_headless_check.setToolTip("启用后使用无头模式启动浏览器。")
        self._browser_user_data_input.setToolTip("Chrome 用户数据目录，可复用登录态。")
        self._browser_profile_input.setToolTip("Chrome Profile 目录，例如：Default。")
        self._emergency_hotkey_input.setToolTip("紧急停止热键，默认 ctrl,alt,esc。")
        self._emergency_hotkey_set_button.setToolTip("点击后按下组合按键录入紧急停止热键。")
        self._emergency_hotkey_add_button.setToolTip("重新录入组合按键。")

    def _run_startup_flows(self, trigger_config: StartupTriggerConfig, trigger: str) -> None:
        flows = [flow for flow in self._flows if flow.flow_id in trigger_config.flow_ids]
        if not flows:
            return
        self._run_flow_sequence(flows, trigger)

    def _run_flow_sequence(self, flows: List[Flow], trigger: str) -> None:
        if self._runner_thread and self._runner_thread.isRunning():
            QMessageBox.warning(self, "流程正在运行", "已有流程正在运行，请稍后重试")
            return
        self._startup_trigger = trigger
        self._startup_queue = flows[1:]
        self._run_flow(flows[0], trigger=trigger)

    def _add_startup_trigger(self) -> None:
        dialog = StartupTriggerDialog(self._flows, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            trigger = dialog.trigger_config
            if trigger.hotkey and trigger.flow_ids:
                self._add_trigger_to_list(trigger)
            else:
                QMessageBox.warning(self, "无效配置", "请设置热键并至少选择一个任务")

    def _edit_startup_trigger(self) -> None:
        item = self._startup_triggers_list.currentItem()
        if not item:
            return
        old_trigger = item.data(Qt.ItemDataRole.UserRole)
        dialog = StartupTriggerDialog(
            self._flows, 
            initial_hotkey=old_trigger.hotkey, 
            initial_flow_ids=old_trigger.flow_ids, 
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_trigger = dialog.trigger_config
            if new_trigger.hotkey and new_trigger.flow_ids:
                item.setData(Qt.ItemDataRole.UserRole, new_trigger)
                # Update display text
                hotkey_str = "+".join(new_trigger.hotkey)
                flow_names = []
                for flow_id in new_trigger.flow_ids:
                    flow = next((f for f in self._flows if f.flow_id == flow_id), None)
                    if flow:
                        flow_names.append(flow.name)
                    else:
                        flow_names.append(f"Unknown({flow_id})")
                item.setText(f"[{hotkey_str}] -> {', '.join(flow_names)}")
            else:
                QMessageBox.warning(self, "无效配置", "请设置热键并至少选择一个任务")

    def _remove_startup_trigger(self) -> None:
        row = self._startup_triggers_list.currentRow()
        if row != -1:
            self._startup_triggers_list.takeItem(row)

    def _update_hotkey_display(self) -> None:
        self._emergency_hotkey_input.setText("+".join(self._emergency_hotkey_keys))

    def _capture_hotkey(self, target: str, append: bool) -> None:
        current: List[str] = []
        if append:
            current = list(self._startup_hotkey_keys if target == "startup" else self._emergency_hotkey_keys)
        dialog = HotkeyCaptureDialog(current, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if target == "startup":
                self._startup_hotkey_keys = dialog.keys
            else:
                self._emergency_hotkey_keys = dialog.keys
            self._update_hotkey_display()


class HotkeyCaptureDialog(QDialog):
    def __init__(self, keys: List[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("录入快捷键")
        self._keys = list(keys)
        
        # UI Elements
        self._info_label = QLabel("请按下组合按键，或手动勾选。")
        self._key_display = QLineEdit()
        self._key_display.setReadOnly(True)
        self._key_display.setText("+".join(self._keys))
        
        # Manual Controls
        manual_group = QGroupBox("手动录入")
        manual_layout = QHBoxLayout()
        
        self._chk_ctrl = QCheckBox("Ctrl")
        self._chk_alt = QCheckBox("Alt")
        self._chk_shift = QCheckBox("Shift")
        self._chk_win = QCheckBox("Win")
        
        self._txt_manual_key = QLineEdit()
        self._txt_manual_key.setPlaceholderText("按键(如s)")
        self._txt_manual_key.setFixedWidth(80)
        
        self._btn_apply_manual = QPushButton("更新")
        
        manual_layout.addWidget(self._chk_ctrl)
        manual_layout.addWidget(self._chk_alt)
        manual_layout.addWidget(self._chk_shift)
        manual_layout.addWidget(self._chk_win)
        manual_layout.addWidget(self._txt_manual_key)
        manual_layout.addWidget(self._btn_apply_manual)
        manual_group.setLayout(manual_layout)

        # Standard Buttons
        self._clear_button = QPushButton("清空")
        self._save_button = QPushButton("确定")
        self._cancel_button = QPushButton("取消")
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self._info_label)
        layout.addWidget(self._key_display)
        layout.addWidget(manual_group)
        
        footer_row = QHBoxLayout()
        footer_row.addWidget(self._clear_button)
        footer_row.addStretch()
        footer_row.addWidget(self._save_button)
        footer_row.addWidget(self._cancel_button)
        layout.addLayout(footer_row)
        self.setLayout(layout)
        
        # Bindings
        self._btn_apply_manual.clicked.connect(self._apply_manual)
        self._clear_button.clicked.connect(self._clear_keys)
        self._save_button.clicked.connect(self.accept)
        self._cancel_button.clicked.connect(self.reject)
        
        # Init manual controls from initial keys
        self._sync_manual_controls()

    @property
    def keys(self) -> List[str]:
        return list(self._keys)

    def _sync_manual_controls(self) -> None:
        self._chk_ctrl.setChecked("ctrl" in self._keys)
        self._chk_alt.setChecked("alt" in self._keys)
        self._chk_shift.setChecked("shift" in self._keys)
        self._chk_win.setChecked("win" in self._keys)
        
        modifiers = {"ctrl", "alt", "shift", "win"}
        other_keys = [k for k in self._keys if k not in modifiers]
        if other_keys:
            self._txt_manual_key.setText(other_keys[0])
        else:
            self._txt_manual_key.clear()

    def _apply_manual(self) -> None:
        keys = []
        if self._chk_ctrl.isChecked(): keys.append("ctrl")
        if self._chk_alt.isChecked(): keys.append("alt")
        if self._chk_shift.isChecked(): keys.append("shift")
        if self._chk_win.isChecked(): keys.append("win")
        
        text = self._txt_manual_key.text().strip().lower()
        if text:
            keys.append(text)
            
        self._keys = keys
        self._key_display.setText("+".join(self._keys))

    def _clear_keys(self) -> None:
        self._keys = []
        self._key_display.setText("")
        self._sync_manual_controls()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        keys = self._build_combo_keys(event)
        
        if keys:
            self._keys = keys
            self._key_display.setText("+".join(self._keys))
            self._sync_manual_controls()
            
            # 不再自动结束录入，允许用户调整
            # 只有当包含非修饰键时，提示已就绪
            modifiers = {"ctrl", "alt", "shift", "win", "control", "meta"}
            is_only_modifiers = all(k in modifiers for k in keys)
            
            if not is_only_modifiers:
                self._info_label.setText("组合键已识别，请点击确定保存。")
            else:
                self._info_label.setText("请按下主按键...")

    def _build_combo_keys(self, event) -> List[str]:
        modifiers = event.modifiers()
        keys: List[str] = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            keys.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            keys.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            keys.append("shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            keys.append("win")
        
        key = event.key()
        # 忽略单纯的修饰键按下事件
        if key in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Meta,
        ):
            return keys
            
        key_text = self._key_to_name(key, event.text())
        if key_text:
            keys.append(key_text)
        return keys

    def _key_to_name(self, key: int, text: str) -> str:
        mapping = {
            Qt.Key.Key_Control: "ctrl",
            Qt.Key.Key_Alt: "alt",
            Qt.Key.Key_Shift: "shift",
            Qt.Key.Key_Meta: "win",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Escape: "esc",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Space: "space",
            # F1-F12
            Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
            Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
            Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
            Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
        }
        if key in mapping:
            return mapping[key]
        text_value = text.strip().lower()
        if text_value:
            return text_value
        try:
            enum_name = Qt.Key(key).name
            return enum_name.replace("Key_", "").lower()
        except (ValueError, AttributeError):
            return ""


def run_app() -> None:
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon("assets/logo.png"))
    window = MainWindow()
    window.show()
    app.aboutToQuit.connect(window.shutdown)
    app.exec()
