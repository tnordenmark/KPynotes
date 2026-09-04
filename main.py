# main.py
import sys
import uuid
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from app.ui.main_window import StickyNoteWindow
from app.core.storage import LocalStorage
import app.config as config

def create_fallback_icon() -> QIcon:
    """Creates a small yellow sticky note icon as a fallback for the system tray."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw yellow sticky note body
    painter.setBrush(QColor("#FFF9C4"))
    painter.setPen(QColor("#E6EE9C"))
    painter.drawRoundedRect(2, 2, 28, 28, 4, 4)
    painter.end()
    
    return QIcon(pixmap)

class KPynotesTrayApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.storage = LocalStorage(storage_dir=config.STORAGE_DIR)
        # Dictionary to keep track of open sticky note windows
        self.active_windows: dict[str, StickyNoteWindow] = {}
        
        # Prevent the app from shutting down when all note windows are closed
        self.app.setQuitOnLastWindowClosed(False)
        
        self.setup_tray_icon()
        self.load_or_create_initial_notes()
        
    def setup_tray_icon(self):
        # Try loading system theme icon first, then fallback icon
        icon = QIcon.fromTheme("text-x-generic", create_fallback_icon())
        
        self.tray = QSystemTrayIcon(icon, parent=self.app)
        self.tray.setToolTip("KPynotes - Sticky Notes")
        
        # Context menu for the tray icon
        self.menu = QMenu()
        self.update_menu()
        
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.on_tray_icon_activated)
        self.tray.show()
        
    def update_menu(self):
        """Rebuilds the tray context menu dynamically."""
        self.menu.clear()
        
        # Action: New Note
        new_note_action = QAction("➕ New Note", self.menu)
        new_note_action.triggered.connect(self.create_new_note)
        self.menu.addAction(new_note_action)
        
        self.menu.addSeparator()
        
        # Action: Show All / Hide All
        show_all_action = QAction("👁️ Show All Notes", self.menu)
        show_all_action.triggered.connect(self.show_all_notes)
        self.menu.addAction(show_all_action)
        
        hide_all_action = QAction("🙈 Hide All Notes", self.menu)
        hide_all_action.triggered.connect(self.hide_all_notes)
        self.menu.addAction(hide_all_action)
        
        self.menu.addSeparator()
        
        # Action: Quit App
        quit_action = QAction("❌ Quit KPynotes", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def create_new_note(self, note_id: str | None = None) -> StickyNoteWindow:
        """Spawns a new or existing note window by ID."""
        if not note_id:
            note_id = str(uuid.uuid4())
        
        if note_id in self.active_windows:
            # If the note already exists, bring it to the front
            window = self.active_windows[note_id]
            window.show()
            window.activateWindow()
            
            return window
        
        window = StickyNoteWindow(note_id=note_id)
        
        # Connect the deletion signal to clean up memory
        window.note_deleted.connect(self.on_note_deleted)
        
        # Override standard close behavior to keep track in active_windows
        original_close_event = window.closeEvent
        def custom_close_event(event):
            original_close_event(event)
            # Retain window reference in self.active_windows to allow reopening
            
        window.closeEvent = custom_close_event
        
        self.active_windows[note_id] = window
        window.show()
        
        return window
    
    def load_or_create_initial_notes(self):
        """Loads the first note from storage or creates a new one if none exist."""
        saved_note_ids = self.storage.list_note_ids()
        
        if saved_note_ids:
            # If a note exists, load the first existing note
            for note_id in saved_note_ids:
                self.create_new_note(note_id)
        else:
            # If no notes exist, create a new one
            self.create_new_note()
           
    def show_all_notes(self):
        for window in self.active_windows.values():
            window.show()
            window.activateWindow()
    
    def hide_all_notes(self):
        for window in self.active_windows.values():
            window.hide()
                
    def on_tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Triggers when clicking the tray icon itself."""
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            # Bring all notes to front or toggle visibility
            any_visible = any(w.isVisible() for w in self.active_windows.values())
            if any_visible:
                self.hide_all_notes()
            else:
                self.show_all_notes()
                
    def on_note_deleted(self, note_id: str):
        """Removes the deleted note from active memory."""
        if note_id in self.active_windows:
            del self.active_windows[note_id]
        # Update the tray menu to reflect the change
        self.update_menu()
                
    def quit_app(self):
        """Ensures all notes save their data before closing."""
        for window in list(self.active_windows.values()):
            window.close()
        self.tray.hide()
        self.app.quit()        
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # In the future, note_manager.py will dictate how many windows spawn here
    tray_app = KPynotesTrayApp(app)
    sys.exit(app.exec())
