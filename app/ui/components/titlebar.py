# app/ui/components/titlebar.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

class CustomTitleBar(QWidget):
    # Signal to tell the main window to close
    close_requested = Signal()

    def __init__(self, title: str = "KPynotes", parent=None):
        super().__init__(parent)
        
        # Assign an objectName to the TitleBar for styling purposes
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        # Show a move cursor when hovering over the title bar
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.init_ui(title)

    def init_ui(self, title: str):
        self.setFixedHeight(30)
        
        # Titlebar container without margins to ensure the title bar fills the width of the window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title label
        self.title_label = QLabel(title)
        self.title_label.setObjectName("TitleLabel")
        # Allow mouse events to pass through the label to the title bar for dragging
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Close Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setFixedSize(24, 24)
        # Reset cursor back to pointing hand over the close button
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_requested.emit)

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.close_btn)

    # Dragging logic for the title bar
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Delegate movement directly to the OS Window Manager
            window = self.window().windowHandle()
            if window:
                window.startSystemMove()
            event.accept()
        else:
            super().mousePressEvent(event)