from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout, 
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QCursor

class FloatingWindow(QWidget):
    stop_requested = pyqtSignal()
    restore_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置无边框、置顶、工具窗口属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        # 设置背景透明 (关键，否则阴影不显示)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(260, 140)
        
        self._drag_pos = None
        self._setup_ui()

    def _setup_ui(self):
        # 主布局 - 用于承载带阴影的 Container
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 留出阴影空间

        # 容器 Frame
        self.container = QFrame()
        self.container.setObjectName("Container")
        
        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 2)
        self.container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(8)
        container_layout.setContentsMargins(12, 8, 12, 12)

        # 1. 顶部标题栏
        title_bar = QHBoxLayout()
        title_bar.setSpacing(6)
        
        # 拖动指示图标
        self.icon_label = QLabel("⚡")
        self.icon_label.setObjectName("Icon")
        
        self.title_label = QLabel("自动化工具")
        self.title_label.setObjectName("Title")
        
        self.restore_btn = QPushButton("❐")
        self.restore_btn.setObjectName("RestoreBtn")
        self.restore_btn.setToolTip("恢复主窗口 (双击窗口也可恢复)")
        self.restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_btn.setFixedSize(24, 24)
        self.restore_btn.clicked.connect(self.restore_requested.emit)

        title_bar.addWidget(self.icon_label)
        title_bar.addWidget(self.title_label)
        title_bar.addStretch()
        title_bar.addWidget(self.restore_btn)
        
        container_layout.addLayout(title_bar)
        
        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setObjectName("Line")
        line.setFixedHeight(1)
        container_layout.addWidget(line)

        # 2. 流程名称区域
        self.flow_label = QLabel("无运行任务")
        self.flow_label.setObjectName("FlowName")
        self.flow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flow_label.setWordWrap(True)
        container_layout.addWidget(self.flow_label)

        # 3. 状态信息区域
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("Status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        container_layout.addWidget(self.status_label)

        # 4. 停止按钮
        self.stop_button = QPushButton("停止运行")
        self.stop_button.setObjectName("StopBtn")
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.stop_button.hide()
        container_layout.addWidget(self.stop_button)

        main_layout.addWidget(self.container)
        
        self._apply_styles(is_running=False)

    def _apply_styles(self, is_running: bool):
        if is_running:
            # 运行态：科技绿/蓝风格
            bg_color = "rgba(16, 30, 40, 0.95)"
            border_color = "rgba(0, 255, 150, 0.6)"
            title_color = "#00ff96"
        else:
            # 空闲态：深灰科技风格
            bg_color = "rgba(30, 32, 35, 0.95)"
            border_color = "rgba(255, 255, 255, 0.2)"
            title_color = "#e0e0e0"

        self.setStyleSheet(f"""
            QFrame#Container {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            QLabel#Icon {{
                color: {title_color};
                font-size: 16px;
            }}
            QLabel#Title {{
                color: {title_color};
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton#RestoreBtn {{
                color: #aaaaaa;
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton#RestoreBtn:hover {{
                color: white;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }}
            QFrame#Line {{
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
            }}
            QLabel#FlowName {{
                color: white;
                font-weight: bold;
                font-size: 15px;
                padding: 4px 0;
            }}
            QLabel#Status {{
                color: #cccccc;
                font-size: 12px;
            }}
            QPushButton#StopBtn {{
                background-color: rgba(255, 77, 79, 0.9);
                border: 1px solid #ff7875;
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
                font-weight: bold;
                font-size: 13px;
                margin-top: 4px;
            }}
            QPushButton#StopBtn:hover {{
                background-color: #ff7875;
            }}
            QPushButton#StopBtn:pressed {{
                background-color: #d9363e;
            }}
        """)

    def update_status(self, status: str, is_running: bool, flow_name: str = None):
        """更新悬浮窗状态显示"""
        self.status_label.setText(status)
        
        if flow_name:
            self.flow_label.setText(flow_name)
            self.flow_label.show()
        elif not is_running:
            self.flow_label.setText("无运行任务")
        
        if is_running:
            self.stop_button.show()
        else:
            self.stop_button.hide()
            
        self._apply_styles(is_running)

    # --- 交互逻辑 ---
    def enterEvent(self, event):
        # 鼠标移入时改变光标，提示可交互
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().enterEvent(event)

    def mouseDoubleClickEvent(self, event):
        # 双击恢复主窗口
        if event.button() == Qt.MouseButton.LeftButton:
            self.restore_requested.emit()
            event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 记录点击位置用于拖拽
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
