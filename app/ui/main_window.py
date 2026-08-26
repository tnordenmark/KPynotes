# app/ui/main_window.py
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout
from app.ui.components.editor import ScratchpadEditor
from app.ui.components.titlebar import CustomTitleBar
from app.core.storage import LocalStorage
# Import config for save trigger timer delay and other settings
import app.config as config

class StickyNoteWindow(QWidget):
    def __init__(self, note_id: str):
        super().__init__()
        self.note_id = note_id
        
        # Initialize Core Storage from config
        self.storage = LocalStorage(storage_dir=config.STORAGE_DIR) 
        
        self.setup_window_flags()
        self.init_ui()
        self.apply_stylesheet()
        
        self.load_data()
        self.setup_autosave()
        
    def setup_window_flags(self):
        # Remove os borders to make the window frameless
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            # Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        # Make rounded corners show properly
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Default size, can be adjusted later
        self.resize(300, 350)

    def init_ui(self):
        # Base layout, 0 margins so the frame dictates the borders
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Main container, i.e the actual sticky note
        self.container = QFrame(self)
        self.container.setObjectName("NoteContainer")
        main_layout.addWidget(self.container)
        
        # Container layout
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        
        # Add custom components
        self.title_bar = CustomTitleBar(title="KPynotes", parent=self)
        self.title_bar.close_requested.connect(self.close)
        
        # Use the custom editor with built-in formatting!
        self.editor = ScratchpadEditor(self)
        
        container.layout().addWidget(self.title_bar)
        container.layout().addWidget(self.editor)
        
    def apply_stylesheet(self):
        # A soft yellow and flat-design sticky note look
        self.setStyleSheet("""
            QFrame#NoteContainer {
                background-color: #FFF9C4;
                border: 1px solid #E6EE9C;
                border-radius: 8px;
            }
            QTextEdit {
                background: transparent;
                border: none;
                font-family: 'Segoe UI', 'Noto Sans', sans-serif;
                font-size: 14px;
                color: #333333;
            }
            QLabel#TitleLabel {
                font-weight: bold;
                color: #555555;
            }
            QPushButton#CloseButton {
                background: transparent;
                border: none;
                font-weight: bold;
                color: #999999;
                font-size: 14px;
            }
            QPushButton#CloseButton:hover {
                color: #FF1744;
            }
        """)
        
    def move_and_snap(self, new_pos):
        """Called by the title bar to move the window and snap to edges if close enough."""
        screen = QApplication.primaryScreen().availableGeometry()
        margin = config.SNAP_MARGIN_PX
        
        # Snap logic, Left, Right, Top, Bottom
        if abs(new_pos.x() - screen.left()) < margin:
            new_pos.setX(screen.left())
        elif abs(new_pos.x() + self.width() - screen.right()) < margin:
            new_pos.setX(screen.right() - self.width())
            
        if abs(new_pos.y() - screen.top()) < margin:
            new_pos.setY(screen.top())
        elif abs(new_pos.y() + self.height() - screen.bottom()) < margin:
            new_pos.setY(screen.bottom() - self.height())
            
        self.move(new_pos)
        
    # Load and auto-save methods
    def load_data(self):
        data = self.storage.load_note(self.note_id)
        if data:
            # Pass the markdown string to the editor
            if "content" in data:
                self.editor.setMarkdown(data["content"])
            
            # Restore window position
            if "position" in data:
                self.move(data["position"]["x"], data["position"]["y"])

    def setup_autosave(self):
        # Set up a timer to auto-save the note every AUTOSAVE_DELAY_MS milliseconds
        self.autosave_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        
        # Use config for the delay
        self.save_timer.setInterval(config.AUTOSAVE_DELAY_MS)
        self.save_timer.timeout.connect(self.save_data)
        
    def trigger_autosave(self):
        # Restart the timer on each change
        self.save_timer.start()

    def save_data(self):
        # The Window coordinates the UI data with the Core storage
        self.storage.save_note(
            note_id=self.note_id,
            position={"x": self.x(), "y": self.y()},
            markdown_content=self.editor.toMarkdown()
        )

    # You could trigger save_data() on a timer, or override closeEvent
    def closeEvent(self, event):
        self.save_data()
        event.accept()