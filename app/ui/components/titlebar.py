# app/ui/components/titlebar.py
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

class CustomTitleBar(QWidget):
    # Signal to tell the main window to close
    close_requested = Signal()

    def __init__(self, title: str = "Scratchpad", parent=None):
        super().__init__(parent)
        self.drag_position = QPoint()
        self.init_ui(title)

    def init_ui(self, title: str):
        self.setFixedHeight(30)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title Label
        self.title_label = QLabel(title)
        self.title_label.setObjectName("TitleLabel")

        # Close Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_requested.emit)

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.close_btn)

    # Dragging logic for the title bar
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Calculate where the user clicked relative to the top-left of the window
            self.drag_position = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            # Calculate the new intended window position
            new_pos = event.globalPosition().toPoint() - self.drag_position
            
            # Pass the coordinate to the main window to handle edge-snapping
            if hasattr(self.window(), 'move_and_snap'):
                self.window().move_and_snap(new_pos)
            else:
                self.window().move(new_pos)
            event.accept()