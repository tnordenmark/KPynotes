# app/ui/main_window.py
from PySide6.QtCore import Qt, QTimer, QEvent, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QFrame, QMessageBox
from app.ui.components.editor import ScratchpadEditor
from app.ui.components.titlebar import CustomTitleBar
from app.core.storage import LocalStorage
# Import config for save trigger timer delay and other settings
import app.config as config

class StickyNoteWindow(QWidget):
    # Signal to notify tray app
    note_deleted = Signal(str)
    
    def __init__(self, note_id: str):
        super().__init__()
        self.note_id = note_id
        # Prevent auto-saving a deleted note
        self.is_deleted = False
        
        # Initialize Core Storage from config
        self.storage = LocalStorage(storage_dir=config.STORAGE_DIR)
        
        # Explicitly define the base cursor for the entire window
        self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # Force Qt to track mouse movement even when the window lacks focus
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        
        self.setup_window_flags()
        self.init_ui()
        self.apply_stylesheet()
        
        self.load_data()
        self.setup_autosave()
        
    def setup_window_flags(self):
        # Remove OS borders to make the window frameless
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
            # In case you want the window to always stay on top
            # Qt.WindowType.WindowStaysOnTopHint |
        )
        # Make rounded corners show properly
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Default size, can be adjusted later
        self.resize(300, 350)
        # Enforce minimum size to prevent shrinking it out of existence
        self.setMinimumSize(150, 150)
        
        # Allow window to track mouse without clicking
        self.setMouseTracking(True)

    def init_ui(self):
        self.title_bar = CustomTitleBar(title="KPynotes", parent=self)
        # Base layout, 0 margins so the frame dictates the borders
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Main container, i.e the actual sticky note
        self.container = QFrame(self)
        self.container.setObjectName("NoteContainer")
        # Make sure container doesn't block mouse tracking
        self.container.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.container.setMouseTracking(True)
        main_layout.addWidget(self.container)
        
        # Vertical container layout
        container_layout = QVBoxLayout(self.container)
        # Set margins to use as resize border
        container_layout.setContentsMargins(8, 8, 8, 8)
        
        # Add custom title bar and editor to the container
        self.title_bar = CustomTitleBar(title="KPynotes", parent=self)
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.delete_requested.connect(self.request_delete)
        
        self.editor = ScratchpadEditor(self)
        self.editor.setMouseTracking(True)
        # Ensure the viewport also tracks mouse events
        self.editor.viewport().setMouseTracking(True)
        
        # To capture mouse events for moving the window
        self.container.installEventFilter(self)
        self.editor.installEventFilter(self)
        self.editor.viewport().installEventFilter(self)
        self.title_bar.installEventFilter(self)
        self.title_bar.close_btn.installEventFilter(self)
        self.title_bar.delete_btn.installEventFilter(self)
        
        container_layout.addWidget(self.title_bar)
        container_layout.addWidget(self.editor)
        
        # Set focus to the editor for immediate typing
        self.editor.setFocus()
        
        # Create a horizontal layout for the bottom row to hold
        # resize handles
        # bottom_layout = QHBoxLayout()
        # bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # Bottom left resize grip
        # self.size_grip_bottom_left = QSizeGrip(self)
        # self.size_grip_bottom_left.setFixedSize(16, 16)
        # # Use SizeBDiagCursor for bottom left corner
        # self.size_grip_bottom_left.setCursor(Qt.CursorShape.SizeBDiagCursor)
        
        # Bottom right resize grip
        # self.size_grip_bottom_right = QSizeGrip(self)
        # self.size_grip_bottom_right.setFixedSize(16, 16)
        # # Use SizeFDiagCursor for bottom right corner
        # self.size_grip_bottom_right.setCursor(Qt.CursorShape.SizeFDiagCursor)
        
        # # Add both resize grips to the bottom layout, with a stretch in between to push them to corners
        # Ommit size for addStretch() to make it take all available space
        # bottom_layout.addWidget(self.size_grip_bottom_left)
        # bottom_layout.addStretch()
        # bottom_layout.addWidget(self.size_grip_bottom_right)
        
        #container_layout.addLayout(bottom_layout)
        
    def apply_stylesheet(self):
        # A soft yellow and flat-design sticky note look
        self.setStyleSheet("""
            QFrame#NoteContainer {
                background-color: #FFF9C4;
                border: 1px solid #E6EE9C;
                border-radius: 8px;
            }
            QWidget#TitleBar {
                background-color: #FFF59D;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
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
            QPushButton#DeleteButton {
                background: transparent;
                border: none;
                font-size: 14px;
                }
                QPushButton#DeleteButton:hover {
                background-color: #FFCDD2;
                border-radius: 4px;
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
        
    def get_resize_edge(self, pos):
        # Determine which edge or corner the mouse is near for resizing
        # based on the 8px margin
        margin = 8
        on_left = pos.x() <= margin
        on_right = pos.x() >= self.width() - margin
        on_top = pos.y() <= margin
        on_bottom = pos.y() >= self.height() - margin
        
        # Corners
        if on_left and on_top: return Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        if on_right and on_top: return Qt.Edge.TopEdge | Qt.Edge.RightEdge
        if on_left and on_bottom: return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if on_right and on_bottom: return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        # Sides
        if on_left: return Qt.Edge.LeftEdge
        if on_right: return Qt.Edge.RightEdge
        if on_top: return Qt.Edge.TopEdge
        if on_bottom: return Qt.Edge.BottomEdge
        
        return None
        
    def eventFilter(self, watched, event):
        # Handle mouse move, hover move and leave events
        event_type = event.type()
        
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
            # Convert global mouse position to local window coordinates
            global_pos = event.globalPosition().toPoint()
            local_pos = self.mapFromGlobal(global_pos)
            
            edges = self.get_resize_edge(local_pos)
            
            if edges is not None:
                # Dynamically change cursor based on the edge
                if edges in (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
                    self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif edges in (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge, Qt.Edge.TopEdge | Qt.Edge.RightEdge):
                    self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                elif edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
                    self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                # Inside the note interior (not on an edge): 
                # Release window-level override so child widgets (Editor, Buttons, Titlebar) 
                # display their own configured cursors
                self.unsetCursor()
                
        # Reset cursor if the mouse leaves the window
        elif event_type in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self.unsetCursor()
                
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self.get_resize_edge(event.pos())
            if edges:
                window = self.windowHandle()
                if window:
                    # Hand off the dragging to KDE / Windows natively
                    window.startSystemResize(edges)
                event.accept()
                return
        super().mousePressEvent(event)
        
    def showEvent(self, event):
        """Called automatically when the window become visible"""
        super().showEvent(event)
        # Bring the window to the front
        self.raise_()
        # Wake up OS window management
        self.activateWindow()
        # Focus the note content text box
        if hasattr(self, 'editor'):
            self.editor.setFocus()
        
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
            # Restore window size if available
            if "size" in data:
                self.resize(data["size"]["width"], data["size"]["height"])

    def setup_autosave(self):
        # Set up a timer to auto-save the note every AUTOSAVE_DELAY_MS milliseconds
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        
        # Use config for the delay
        self.save_timer.setInterval(config.AUTOSAVE_DELAY_MS)
        self.save_timer.timeout.connect(self.save_data)
        
        # Monitor the editor for changes to trigger auto-save
        self.editor.textChanged.connect(self.trigger_autosave)
        
    def trigger_autosave(self):
        # Restart the timer on each change
        self.save_timer.start()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Trigger save on resize as well
        self.trigger_autosave()

    def save_data(self):
        # The Window coordinates the UI data with the Core storage
        self.storage.save_note(
            note_id=self.note_id,
            position={"x": self.x(), "y": self.y()},
            size={"width": self.width(), "height": self.height()},
            markdown_content=self.editor.toMarkdown()
        )
        
    def request_delete(self):
        # Show confirmation dialog before deleting
        reply = QMessageBox.question(
            self,
            "Delete Note",
            "Are you sure you want to delete this note?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Flag to bypass save in closeEvent
            self.is_deleted = True
            self.storage.delete_note(self.note_id)
            # Tell main.py to remove note from memory
            self.note_deleted.emit(self.note_id)
            self.close()

    # App close event to ensure data is saved before the window closes
    def closeEvent(self, event):
        # Stop the timer to prevent any pending saves
        self.save_timer.stop()
        
        # Only save if NOT deleting
        if not self.is_deleted:
            self.save_data()
        
        event.accept()
