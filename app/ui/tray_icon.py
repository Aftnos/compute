from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QStyle
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import pyqtSignal

class SystemTrayIcon(QSystemTrayIcon):
    # 定义信号与主窗口通信
    show_window_requested = pyqtSignal()
    toggle_floating_window_requested = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 优先使用自定义图标，如果加载失败则回退到系统默认图标
        icon = QIcon("assets/logo.png")
        if not icon.isNull():
            self.setIcon(icon)
        else:
            self.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        
        self.setVisible(True)
        self._build_menu()

    def _build_menu(self):
        self.menu = QMenu()
        
        self.show_action = QAction("显示主窗口", self)
        self.show_action.triggered.connect(self.show_window_requested.emit)
        self.menu.addAction(self.show_action)
        
        self.floating_action = QAction("显示悬浮窗", self)
        self.floating_action.setCheckable(True)
        self.floating_action.setChecked(False)
        self.floating_action.triggered.connect(self._on_toggle_floating)
        self.menu.addAction(self.floating_action)

        self.menu.addSeparator()

        self.quit_action = QAction("退出", self)
        self.quit_action.triggered.connect(QApplication.instance().quit)
        self.menu.addAction(self.quit_action)

        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_requested.emit()

    def _on_toggle_floating(self, checked):
        self.toggle_floating_window_requested.emit(checked)
    
    def set_floating_checked(self, checked: bool):
        """外部更新菜单选中状态"""
        self.floating_action.setChecked(checked)
