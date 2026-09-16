# app/ui/main_window.py
from PySide6.QtCore import Qt, QTimer, QEvent, Signal, QByteArray
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
        
        # Call apply_stylesheet directly to detect system theme
        self.apply_stylesheet()
        
        # Liten for OS theme changed and re-apply stylesheet dynamically
        QApplication.styleHints().colorSchemeChanged.connect(self.apply_stylesheet)
        
        self.load_data()
        self.setup_autosave()
        
    def setup_window_flags(self):
        # Unique identifiers for window rules etc
        self.setWindowTitle(f"KPynotes - {self.note_id}")
        self.setObjectName(f"StickyNote_{self.note_id}")
        
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
        container_layout.setContentsMargins(0, 0, 0, 0)
        # Remove spacing so the editor conects seamlessly to the bottom of
        # the title bar
        container_layout.setSpacing(0)
        
        # Add custom title bar and editor to the container
        self.title_bar = CustomTitleBar(title="KPynotes", parent=self)
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.delete_requested.connect(self.request_delete)
        self.title_bar.setContentsMargins(8, 4, 8, 4)
        
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
        
    def apply_stylesheet(self, scheme=None):
        # If not passed by the signal, fetch the current color scheme natively
        if scheme is None:
            scheme = QApplication.styleHints().colorScheme()
            
        is_dark = (scheme == Qt.ColorScheme.Dark)
        
        # Define color palettes
        if is_dark:
            # Dark Mode Palette (Sleek Dark Gray/Charcoal)
            bg_color = "#2D2D2D"
            title_bg = "#1E1E1E"
            border_color = "#3D3D3D"
            text_color = "#E0E0E0"
            title_text = "#B0B0B0"
            btn_hover_bg = "#4A4A4A"
            close_hover_text = "#FF5252"
        else:
            # Light Mode Palette (Original Soft Yellow)
            bg_color = "#FFF9C4"
            title_bg = "#FFF59D"
            border_color = "#E6EE9C"
            text_color = "#333333"
            title_text = "#555555"
            btn_hover_bg = "#FFCDD2"
            close_hover_text = "#FF1744"
        
        # A soft yellow and flat-design sticky note look
        self.setStyleSheet(f"""
            QFrame#NoteContainer {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QWidget#TitleBar {{
                background-color: {title_bg};
                /* Subtract 1px from the container's 8px radius to account for the border width */
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                /* Add a subtle bottom border to separate the title bar from the editor */
                border-bottom: 1px solid {border_color};
            }}
            QTextEdit {{
                background: transparent;
                border: none;
                padding: 4px;
                font-family: 'Segoe UI', 'Noto Sans', sans-serif;
                font-size: 14px;
                color: {text_color};
            }}
            QLabel#TitleLabel {{
                font-weight: bold;
                color: {title_text};
            }}
            QPushButton#DeleteButton {{
                background: transparent;
                border: none;
                font-size: 14px;
                }}
            QPushButton#DeleteButton:hover {{
                background-color: {btn_hover_bg};
                border-radius: 4px;
            }}
            QPushButton#CloseButton {{
                background: transparent;
                border: none;
                font-weight: bold;
                color: {close_hover_text};
                font-size: 14px;
            }}
            QPushButton#CloseButton:hover {{
                color: #FF1744;
            }}
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
        event_type = event.type()
        
        # Only process specific mouse events to reduce overhead
        if event_type in (QEvent.Type.MouseMove, QEvent.Type.HoverMove, QEvent.Type.MouseButtonPress):
            
            # Extract global position safely from the event
            if hasattr(event, 'globalPosition'):
                global_pos = event.globalPosition().toPoint()
            else:
                return super().eventFilter(watched, event)
                
            local_pos = self.mapFromGlobal(global_pos)
            edges = self.get_resize_edge(local_pos)
            
            # Handle hover & cursor changes
            if event_type in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
                if edges:
                    # Apply cursor directly to the widget currently being hovered (overriding child cursors)
                    if edges in (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
                        watched.setCursor(Qt.CursorShape.SizeFDiagCursor)
                    elif edges in (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge, Qt.Edge.TopEdge | Qt.Edge.RightEdge):
                        watched.setCursor(Qt.CursorShape.SizeBDiagCursor)
                    elif edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
                        watched.setCursor(Qt.CursorShape.SizeHorCursor)
                    elif edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
                        watched.setCursor(Qt.CursorShape.SizeVerCursor)
                        
                    # Stop propagation so the text editor doesn't override the cursor
                    return True 
                else:
                    # Restore normal cursors based on widget type
                    if watched == getattr(self, 'editor', None) or watched == getattr(self.editor, 'viewport', lambda: None)():
                        watched.setCursor(Qt.CursorShape.IBeamCursor)
                    else:
                        watched.unsetCursor()
                        
            # Handle mouse click & drag
            elif event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                if edges:
                    # Acknowledge the press natively for the OS
                    event.accept()
                    window = self.windowHandle()
                    if window:
                        window.startSystemResize(edges)
                    # Block child widgets from starting text selection during resize
                    return True
                    
        # Handle mouse leaving the window
        elif event_type in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            if watched == getattr(self, 'editor', None) or watched == getattr(self.editor, 'viewport', lambda: None)():
                watched.setCursor(Qt.CursorShape.IBeamCursor)
            else:
                watched.unsetCursor()
                
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
            
            # Restore monitor, position and size seamlessly
            if "geometry" in data:
                geometry_bytes = QByteArray.fromBase64(data["geometry"].encode('utf-8'))
                self.restoreGeometry(geometry_bytes)
            
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
        # saveGeometry() packs position, size and screen index to a hex string
        geometry_b64 = self.saveGeometry().toBase64().data().decode('utf-8')
        
        # The Window coordinates the UI data with the Core storage
        self.storage.save_note(
            note_id=self.note_id,
            geometry=geometry_b64,
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
