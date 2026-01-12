from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from app.actions import ActionContext, create_action
from app.actions.browser import BrowserController, BrowserOptions
from app.loggers import RunLogger
from app.models import Flow


class FlowRunner(QObject):
    step_started = pyqtSignal(int, str)
    step_finished = pyqtSignal(int, str)
    run_finished = pyqtSignal(str)

    def __init__(
        self,
        flow: Flow,
        logger: RunLogger,
        trigger: str,
        browser_controller: BrowserController,
        browser_defaults: BrowserOptions,
        close_browser_on_finish: bool,
        hotkey_trigger_delay: float = 0.5,
    ) -> None:
        super().__init__()
        self._flow = flow
        self._logger = logger
        self._trigger = trigger
        self._browser_controller = browser_controller
        self._browser_defaults = browser_defaults
        self._close_browser_on_finish = close_browser_on_finish
        self._hotkey_trigger_delay = hotkey_trigger_delay
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        # 如果是通过热键触发，等待一小段时间以确保用户释放了物理按键
        # 避免修饰键（如 Ctrl/Alt）干扰后续的键盘输入动作
        if "hotkey" in self._trigger:
            import time
            time.sleep(0.5)

        context = ActionContext(
            require_window_focus=self._flow.require_window_focus,
            browser=self._browser_controller,
            browser_defaults=self._browser_defaults,
            close_browser_on_finish=self._close_browser_on_finish,
            should_stop=lambda: self._stop_requested,
        )
        self._logger.start_run(self._flow.flow_id, self._flow.name, self._trigger)
        status = "已完成"
        try:
            for index, step in enumerate(self._flow.steps):
                if self._stop_requested:
                    status = "已停止"
                    break
                action = create_action(step)
                self.step_started.emit(index, step.action)
                self._logger.log_step_start(index, step.action, action.summary())
                try:
                    action.execute(context)
                    self._logger.log_step_finish(index, "成功")
                    self.step_finished.emit(index, "成功")
                except Exception as exc:  # noqa: BLE001
                    status = "失败"
                    self._logger.log_step_finish(index, "失败", error=str(exc))
                    self.step_finished.emit(index, "失败")
                    break
        finally:
            if context.browser and self._close_browser_on_finish:
                context.browser.shutdown()
        self._logger.finish_run(status)
        self.run_finished.emit(status)


class RunnerThread(QThread):
    def __init__(
        self,
        flow: Flow,
        logger: RunLogger,
        trigger: str,
        browser_controller: BrowserController,
        browser_defaults: BrowserOptions,
        close_browser_on_finish: bool,
        hotkey_trigger_delay: float = 0.5,
    ) -> None:
        super().__init__()
        self._runner = FlowRunner(
            flow,
            logger,
            trigger,
            browser_controller,
            browser_defaults,
            close_browser_on_finish,
            hotkey_trigger_delay,
        )

    @property
    def runner(self) -> FlowRunner:
        return self._runner

    @property
    def flow(self) -> Flow:
        return self._runner._flow

    def run(self) -> None:
        self._runner.run()
