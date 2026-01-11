from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pynput import mouse

from app.models import Step


ActionGetter = Callable[[], Dict[str, Any]]
ActionSetter = Callable[[Dict[str, Any]], None]


class ClickCapture(QObject):
    point_captured = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self._listener: Optional[mouse.Listener] = None

    def start(self) -> None:
        if self._listener:
            return

        def on_click(x: int, y: int, button: mouse.Button, pressed: bool) -> Optional[bool]:
            if pressed:
                self.stop()
                self.point_captured.emit(int(x), int(y))
                return False
            return None

        self._listener = mouse.Listener(on_click=on_click)
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None


class StepEditorDialog(QDialog):
    def __init__(self, step: Optional[Step] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑步骤")
        self.setModal(True)
        self._action_combo = QComboBox()
        self._forms: Dict[str, tuple[QWidget, ActionGetter, ActionSetter]] = {}
        self._stack = QStackedWidget()
        self._click_capture = ClickCapture()
        self._click_capture.point_captured.connect(self._on_point_captured)
        self._capture_targets: Optional[Tuple[QSpinBox, QSpinBox, QLabel]] = None

        self._build_forms()
        self._build_layout()

        if step:
            self.set_step(step)

    def _build_layout(self) -> None:
        layout = QVBoxLayout()
        layout.addWidget(QLabel("动作类型"))
        layout.addWidget(self._action_combo)
        layout.addWidget(self._stack)

        button_layout = QHBoxLayout()
        save_button = QPushButton("保存")
        cancel_button = QPushButton("取消")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self._action_combo.currentIndexChanged.connect(self._on_action_changed)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._click_capture.stop()
        super().closeEvent(event)

    def _build_forms(self) -> None:
        self._add_form("type_text", "输入文本", self._build_type_text_form())
        self._add_form("key_press", "按键", self._build_key_press_form())
        self._add_form("hotkey", "组合键", self._build_hotkey_form())
        self._add_form("click", "鼠标点击", self._build_click_form())
        self._add_form("scroll", "鼠标滚动", self._build_scroll_form())
        self._add_form("wait", "等待", self._build_wait_form())
        self._add_form("focus_window", "聚焦窗口", self._build_focus_form())
        self._add_form("move_mouse", "鼠标移动", self._build_move_mouse_form())
        self._add_form("drag_mouse", "鼠标拖拽", self._build_drag_mouse_form())
        self._add_form("browser_open", "浏览器打开", self._build_browser_open_form())
        self._add_form("browser_click", "浏览器点击元素", self._build_browser_click_form())
        self._add_form("browser_type", "浏览器输入", self._build_browser_type_form())
        self._add_form("browser_wait", "浏览器等待元素", self._build_browser_wait_form())
        self._add_form("browser_press", "浏览器按键", self._build_browser_press_form())
        self._add_form("browser_close", "浏览器关闭", self._build_browser_close_form())

    def _add_form(
        self,
        action: str,
        label: str,
        form_info: tuple[QWidget, ActionGetter, ActionSetter],
    ) -> None:
        widget, getter, setter = form_info
        self._forms[action] = (widget, getter, setter)
        self._action_combo.addItem(label, userData=action)
        self._stack.addWidget(widget)

    def _on_action_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def set_step(self, step: Step) -> None:
        action_index = self._action_combo.findData(step.action, role=Qt.ItemDataRole.UserRole)
        if action_index != -1:
            self._action_combo.setCurrentIndex(action_index)
        form = self._forms.get(step.action)
        if form:
            _, _, setter = form
            setter(step.params)

    def build_step(self) -> Step:
        action = self._action_combo.currentData(Qt.ItemDataRole.UserRole)
        widget, getter, _ = self._forms[action]
        params = getter()
        return Step(action=action, params=params)

    def _build_type_text_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        text_input = QTextEdit()
        mode_combo = QComboBox()
        mode_combo.addItem("逐字输入", userData="key_in")
        mode_combo.addItem("剪贴板粘贴", userData="paste")
        interval_input = QSpinBox()
        interval_input.setRange(0, 10000)
        interval_input.setSuffix(" ms")
        layout.addRow("文本内容", text_input)
        layout.addRow("输入模式", mode_combo)
        layout.addRow("间隔", interval_input)
        widget.setLayout(layout)

        mode_combo.setToolTip("逐字输入适合普通文本，剪贴板粘贴适合大段文本。")
        interval_input.setToolTip("每个字符之间的延迟，单位毫秒。")

        def getter() -> Dict[str, Any]:
            return {
                "text": text_input.toPlainText(),
                "mode": mode_combo.currentData(Qt.ItemDataRole.UserRole),
                "interval_ms": interval_input.value(),
            }

        def setter(params: Dict[str, Any]) -> None:
            text_input.setPlainText(str(params.get("text", "")))
            index = mode_combo.findData(params.get("mode", "key_in"), role=Qt.ItemDataRole.UserRole)
            if index != -1:
                mode_combo.setCurrentIndex(index)
            interval_input.setValue(int(params.get("interval_ms", 0)))

        return widget, getter, setter

    def _build_key_press_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        key_input = QLineEdit()
        layout.addRow("按键", key_input)
        widget.setLayout(layout)

        key_input.setToolTip("示例：enter、tab、esc。")

        def getter() -> Dict[str, Any]:
            return {"key": key_input.text().strip()}

        def setter(params: Dict[str, Any]) -> None:
            key_input.setText(str(params.get("key", "")))

        return widget, getter, setter

    def _build_hotkey_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        keys_input = QLineEdit()
        layout.addRow("组合键(逗号分隔)", keys_input)
        widget.setLayout(layout)

        keys_input.setToolTip("示例：ctrl,shift,s。")

        def getter() -> Dict[str, Any]:
            keys = [item.strip() for item in keys_input.text().split(",") if item.strip()]
            return {"keys": keys}

        def setter(params: Dict[str, Any]) -> None:
            keys_input.setText(",".join(params.get("keys", [])))

        return widget, getter, setter

    def _build_click_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        x_input = QSpinBox()
        x_input.setRange(-10000, 10000)
        y_input = QSpinBox()
        y_input.setRange(-10000, 10000)
        button_combo = QComboBox()
        button_combo.addItem("左键", userData="left")
        button_combo.addItem("右键", userData="right")
        button_combo.addItem("中键", userData="middle")
        clicks_input = QSpinBox()
        clicks_input.setRange(1, 5)
        capture_button = QPushButton("点击屏幕取点")
        capture_hint = QLabel("点击按钮后在屏幕上选择坐标")
        capture_hint.setWordWrap(True)
        layout.addRow("X 坐标", x_input)
        layout.addRow("Y 坐标", y_input)
        layout.addRow("按钮", button_combo)
        layout.addRow("点击次数", clicks_input)
        layout.addRow(capture_button)
        layout.addRow(capture_hint)
        widget.setLayout(layout)

        capture_button.setToolTip("点击后最小化窗口，在屏幕上选择坐标。")
        capture_hint.setToolTip("提示信息：捕获坐标后会自动恢复窗口。")

        def start_capture() -> None:
            self._capture_targets = (x_input, y_input, capture_hint)
            capture_hint.setText("请在屏幕上点击目标位置...")
            self.setWindowState(Qt.WindowState.WindowMinimized)
            self._click_capture.start()

        capture_button.clicked.connect(start_capture)

        def getter() -> Dict[str, Any]:
            return {
                "x": x_input.value(),
                "y": y_input.value(),
                "button": button_combo.currentData(Qt.ItemDataRole.UserRole),
                "clicks": clicks_input.value(),
            }

        def setter(params: Dict[str, Any]) -> None:
            x_input.setValue(int(params.get("x", 0)))
            y_input.setValue(int(params.get("y", 0)))
            index = button_combo.findData(params.get("button", "left"), role=Qt.ItemDataRole.UserRole)
            if index != -1:
                button_combo.setCurrentIndex(index)
            clicks_input.setValue(int(params.get("clicks", 1)))

        return widget, getter, setter

    def _build_scroll_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        delta_input = QSpinBox()
        delta_input.setRange(-10000, 10000)
        x_input = QSpinBox()
        x_input.setRange(-10000, 10000)
        y_input = QSpinBox()
        y_input.setRange(-10000, 10000)
        position_checkbox = QCheckBox("指定滚动位置")
        layout.addRow("滚动量", delta_input)
        layout.addRow(position_checkbox)
        layout.addRow("X 坐标", x_input)
        layout.addRow("Y 坐标", y_input)
        widget.setLayout(layout)
        x_input.setEnabled(False)
        y_input.setEnabled(False)

        def toggle_position(state: int) -> None:
            enabled = state == Qt.CheckState.Checked
            x_input.setEnabled(enabled)
            y_input.setEnabled(enabled)

        position_checkbox.stateChanged.connect(toggle_position)

        position_checkbox.setToolTip("勾选后指定滚动位置，否则使用当前鼠标位置。")
        delta_input.setToolTip("正数向上滚动，负数向下滚动。")

        def getter() -> Dict[str, Any]:
            params: Dict[str, Any] = {"delta": delta_input.value()}
            if position_checkbox.isChecked():
                params["x"] = x_input.value()
                params["y"] = y_input.value()
            return params

        def setter(params: Dict[str, Any]) -> None:
            delta_input.setValue(int(params.get("delta", 0)))
            has_pos = "x" in params and "y" in params
            position_checkbox.setChecked(has_pos)
            x_input.setValue(int(params.get("x", 0)))
            y_input.setValue(int(params.get("y", 0)))
            x_input.setEnabled(has_pos)
            y_input.setEnabled(has_pos)

        return widget, getter, setter

    def _build_wait_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        ms_input = QSpinBox()
        ms_input.setRange(0, 600000)
        ms_input.setSuffix(" ms")
        layout.addRow("等待时间", ms_input)
        widget.setLayout(layout)

        ms_input.setToolTip("等待指定毫秒数后继续执行下一步。")

        def getter() -> Dict[str, Any]:
            return {"ms": ms_input.value()}

        def setter(params: Dict[str, Any]) -> None:
            ms_input.setValue(int(params.get("ms", 0)))

        return widget, getter, setter

    def _build_focus_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        title_input = QLineEdit()
        layout.addRow("窗口标题包含", title_input)
        widget.setLayout(layout)

        title_input.setToolTip("填写窗口标题关键字以激活对应窗口。")

        def getter() -> Dict[str, Any]:
            return {"title_contains": title_input.text().strip()}

        def setter(params: Dict[str, Any]) -> None:
            title_input.setText(str(params.get("title_contains", "")))

        return widget, getter, setter

    def _build_move_mouse_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        x_input = QSpinBox()
        x_input.setRange(-10000, 10000)
        y_input = QSpinBox()
        y_input.setRange(-10000, 10000)
        duration_input = QSpinBox()
        duration_input.setRange(0, 10000)
        duration_input.setSuffix(" ms")
        layout.addRow("X 坐标", x_input)
        layout.addRow("Y 坐标", y_input)
        layout.addRow("移动耗时", duration_input)
        widget.setLayout(layout)

        def getter() -> Dict[str, Any]:
            return {
                "x": x_input.value(),
                "y": y_input.value(),
                "duration_ms": duration_input.value(),
            }

        def setter(params: Dict[str, Any]) -> None:
            x_input.setValue(int(params.get("x", 0)))
            y_input.setValue(int(params.get("y", 0)))
            duration_input.setValue(int(params.get("duration_ms", 0)))

        return widget, getter, setter

    def _build_drag_mouse_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        from_x_input = QSpinBox()
        from_x_input.setRange(-10000, 10000)
        from_y_input = QSpinBox()
        from_y_input.setRange(-10000, 10000)
        to_x_input = QSpinBox()
        to_x_input.setRange(-10000, 10000)
        to_y_input = QSpinBox()
        to_y_input.setRange(-10000, 10000)
        duration_input = QSpinBox()
        duration_input.setRange(0, 10000)
        duration_input.setSuffix(" ms")
        layout.addRow("起点 X", from_x_input)
        layout.addRow("起点 Y", from_y_input)
        layout.addRow("终点 X", to_x_input)
        layout.addRow("终点 Y", to_y_input)
        layout.addRow("拖拽耗时", duration_input)
        widget.setLayout(layout)

        def getter() -> Dict[str, Any]:
            return {
                "from_x": from_x_input.value(),
                "from_y": from_y_input.value(),
                "to_x": to_x_input.value(),
                "to_y": to_y_input.value(),
                "duration_ms": duration_input.value(),
            }

        def setter(params: Dict[str, Any]) -> None:
            from_x_input.setValue(int(params.get("from_x", 0)))
            from_y_input.setValue(int(params.get("from_y", 0)))
            to_x_input.setValue(int(params.get("to_x", 0)))
            to_y_input.setValue(int(params.get("to_y", 0)))
            duration_input.setValue(int(params.get("duration_ms", 0)))

        return widget, getter, setter

    def _build_browser_open_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        url_input = QLineEdit()
        use_defaults_check = QCheckBox("使用全局浏览器设置")
        use_defaults_check.setChecked(True)
        headless_check = QCheckBox("无头模式")
        user_data_input = QLineEdit()
        profile_input = QLineEdit()
        layout.addRow("网址", url_input)
        layout.addRow(use_defaults_check)
        layout.addRow(headless_check)
        layout.addRow("用户数据目录", user_data_input)
        layout.addRow("Profile 目录", profile_input)
        widget.setLayout(layout)

        use_defaults_check.setToolTip("勾选后将使用系统设置中的默认浏览器参数。")
        headless_check.setToolTip("无头模式不会显示浏览器窗口。")
        user_data_input.setToolTip("Chrome 用户数据目录，可复用登录态。")
        profile_input.setToolTip("Profile 目录，例如：Default 或 Profile 1。")

        def toggle_fields(checked: bool) -> None:
            headless_check.setEnabled(not checked)
            user_data_input.setEnabled(not checked)
            profile_input.setEnabled(not checked)

        toggle_fields(use_defaults_check.isChecked())
        use_defaults_check.toggled.connect(toggle_fields)

        def getter() -> Dict[str, Any]:
            return {
                "url": url_input.text().strip(),
                "use_defaults": use_defaults_check.isChecked(),
                "headless": None if use_defaults_check.isChecked() else headless_check.isChecked(),
                "user_data_dir": None if use_defaults_check.isChecked() else user_data_input.text().strip() or None,
                "profile_dir": None if use_defaults_check.isChecked() else profile_input.text().strip() or None,
            }

        def setter(params: Dict[str, Any]) -> None:
            url_input.setText(str(params.get("url", "")))
            use_defaults_check.setChecked(bool(params.get("use_defaults", True)))
            headless_check.setChecked(bool(params.get("headless", False)))
            user_data_input.setText(str(params.get("user_data_dir", "") or ""))
            profile_input.setText(str(params.get("profile_dir", "") or ""))
            toggle_fields(use_defaults_check.isChecked())

        return widget, getter, setter

    def _on_point_captured(self, x: int, y: int) -> None:
        if not self._capture_targets:
            return
        x_input, y_input, hint_label = self._capture_targets
        x_input.setValue(x)
        y_input.setValue(y)
        hint_label.setText(f"已选择坐标：({x}, {y})")
        self._capture_targets = None
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _build_browser_click_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        selector_input = QLineEdit()
        by_combo = QComboBox()
        by_combo.addItem("CSS 选择器", userData="css")
        by_combo.addItem("XPath", userData="xpath")
        by_combo.addItem("ID", userData="id")
        by_combo.addItem("Name", userData="name")
        layout.addRow("选择器", selector_input)
        layout.addRow("定位方式", by_combo)
        widget.setLayout(layout)

        def getter() -> Dict[str, Any]:
            return {"selector": selector_input.text().strip(), "by": by_combo.currentData(Qt.ItemDataRole.UserRole)}

        def setter(params: Dict[str, Any]) -> None:
            selector_input.setText(str(params.get("selector", "")))
            index = by_combo.findData(params.get("by", "css"), role=Qt.ItemDataRole.UserRole)
            if index != -1:
                by_combo.setCurrentIndex(index)

        return widget, getter, setter

    def _build_browser_type_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        selector_input = QLineEdit()
        text_input = QTextEdit()
        by_combo = QComboBox()
        by_combo.addItem("CSS 选择器", userData="css")
        by_combo.addItem("XPath", userData="xpath")
        by_combo.addItem("ID", userData="id")
        by_combo.addItem("Name", userData="name")
        clear_check = QCheckBox("输入前清空")
        clear_check.setChecked(True)
        layout.addRow("选择器", selector_input)
        layout.addRow("输入文本", text_input)
        layout.addRow("定位方式", by_combo)
        layout.addRow(clear_check)
        widget.setLayout(layout)

        def getter() -> Dict[str, Any]:
            return {
                "selector": selector_input.text().strip(),
                "text": text_input.toPlainText(),
                "by": by_combo.currentData(Qt.ItemDataRole.UserRole),
                "clear_first": clear_check.isChecked(),
            }

        def setter(params: Dict[str, Any]) -> None:
            selector_input.setText(str(params.get("selector", "")))
            text_input.setPlainText(str(params.get("text", "")))
            index = by_combo.findData(params.get("by", "css"), role=Qt.ItemDataRole.UserRole)
            if index != -1:
                by_combo.setCurrentIndex(index)
            clear_check.setChecked(bool(params.get("clear_first", True)))

        return widget, getter, setter

    def _build_browser_wait_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        selector_input = QLineEdit()
        by_combo = QComboBox()
        by_combo.addItem("CSS 选择器", userData="css")
        by_combo.addItem("XPath", userData="xpath")
        by_combo.addItem("ID", userData="id")
        by_combo.addItem("Name", userData="name")
        timeout_input = QSpinBox()
        timeout_input.setRange(1, 120)
        timeout_input.setSuffix(" 秒")
        layout.addRow("选择器", selector_input)
        layout.addRow("定位方式", by_combo)
        layout.addRow("超时", timeout_input)
        widget.setLayout(layout)

        def getter() -> Dict[str, Any]:
            return {
                "selector": selector_input.text().strip(),
                "by": by_combo.currentData(Qt.ItemDataRole.UserRole),
                "timeout_s": timeout_input.value(),
            }

        def setter(params: Dict[str, Any]) -> None:
            selector_input.setText(str(params.get("selector", "")))
            index = by_combo.findData(params.get("by", "css"), role=Qt.ItemDataRole.UserRole)
            if index != -1:
                by_combo.setCurrentIndex(index)
            timeout_input.setValue(int(params.get("timeout_s", 10)))

        return widget, getter, setter

    def _build_browser_press_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        keys_input = QLineEdit()
        layout.addRow("按键(逗号分隔)", keys_input)
        widget.setLayout(layout)

        def getter() -> Dict[str, Any]:
            keys = [item.strip() for item in keys_input.text().split(",") if item.strip()]
            return {"keys": keys}

        def setter(params: Dict[str, Any]) -> None:
            keys_input.setText(",".join(params.get("keys", [])))

        return widget, getter, setter

    def _build_browser_close_form(self) -> tuple[QWidget, ActionGetter, ActionSetter]:
        widget = QWidget()
        layout = QFormLayout()
        layout.addRow(QLabel("关闭当前浏览器实例"))
        widget.setLayout(layout)

        def getter() -> Dict[str, Any]:
            return {}

        def setter(params: Dict[str, Any]) -> None:
            return

        return widget, getter, setter
