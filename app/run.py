# app/run.py
"""Application entry point: tray icon, note windows, and file watching."""

import logging
import os
import sys
import uuid

from PySide6.QtCore import Qt, QCoreApplication, QFileSystemWatcher, QTimer
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from app.ui.main_window import StickyNoteWindow
from app.core.storage import LocalStorage
from app.ui.settings_window import SettingsDialog
from app.core.settings import AppSettings

logger = logging.getLogger(__name__)


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
        self.app_settings = AppSettings()

        # Retrieve dynamic storage path from settings
        self.storage_path = self.app_settings.get_storage_path()
        # One shared storage instance is injected into every note window so
        # all writers operate on the same directory.
        self.storage = LocalStorage(storage_dir=self.storage_path)

        # Dictionary to keep track of open sticky note windows
        self.active_windows: dict[str, StickyNoteWindow] = {}

        # Prevent the app from shutting down when all note windows are closed
        self.app.setQuitOnLastWindowClosed(False)

        # Setup QFileSystemWatcher and debounce timer to watch for external changes
        self.init_file_system_watcher()

        self.setup_tray_icon()
        self.load_or_create_initial_notes()

        # Centralized OS theme (color scheme) change handling:
        # Subscribe once in the tray app rather than per-window to avoid
        # N connections. When the system theme changes, broadcast
        # apply_stylesheet() to all open note windows.
        self.app.styleHints().colorSchemeChanged.connect(self._on_color_scheme_changed)

    def _on_color_scheme_changed(self):
        """Broadcasts a stylesheet refresh to all open note windows."""
        for window in self.active_windows.values():
            window.apply_stylesheet()

    def init_file_system_watcher(self):
        """Initializes a file system watcher to monitor changes in the storage directory."""
        self.watcher = QFileSystemWatcher()

        # Debounce timer to prevent rapid consecutive file-system events
        self.watcher_timer = QTimer()
        self.watcher_timer.setSingleShot(True)
        self.watcher_timer.setInterval(300)  # 300 ms debounce interval
        self.watcher_timer.timeout.connect(self.sync_active_notes_from_disk)

        self.update_watcher_paths()

        # Connect watcher signals to start debounce timer
        self.watcher.directoryChanged.connect(self.on_disk_change_detected)
        self.watcher.fileChanged.connect(self.on_disk_change_detected)

    def update_watcher_paths(self):
        """Refreshes watched folder and files when storage path changes."""
        # Unwatch previous paths if any exist
        existing_dirs = self.watcher.directories()
        if existing_dirs:
            self.watcher.removePaths(existing_dirs)

        existing_files = self.watcher.files()
        if existing_files:
            self.watcher.removePaths(existing_files)

        # Ensure directory exists before watching
        if os.path.exists(self.storage_path):
            self.watcher.addPath(self.storage_path)

            # Watch individual note files inside storage directory
            for filename in os.listdir(self.storage_path):
                file_path = os.path.join(self.storage_path, filename)
                if filename.endswith(".json") and os.path.isfile(file_path):
                    self.watcher.addPath(file_path)

    def reconcile_watcher_files(self):
        """Ensures note files created after startup are watched for external edits.

        QFileSystemWatcher silently drops deleted files, so this also re-adds
        files that were recreated (e.g. after a delete/rename cycle).
        """
        if not os.path.isdir(self.storage.storage_dir):
            return

        current = {
            os.path.join(self.storage.storage_dir, f"{note_id}.json")
            for note_id in self.storage.list_note_ids()
        }
        missing = current - set(self.watcher.files())
        if missing:
            self.watcher.addPaths(sorted(missing))

    def on_disk_change_detected(self, path: str):
        """Triggered when a file or directory change is detected and starts the debounce timer."""
        # Start or restart the debounce timer
        self.watcher_timer.start()

    def sync_active_notes_from_disk(self):
        """Re-synchronizes active windows and loads newly added notes from disk."""
        # Get the current list of note IDs from storage
        if not os.path.exists(self.storage_path):
            return

        disk_note_ids = set(self.storage.list_note_ids())
        active_note_ids = set(self.active_windows.keys())

        # Load newly created files on disk that aren't open yet
        for note_id in disk_note_ids - active_note_ids:
            self.create_new_note(note_id)

        # Reload contents for already open windows if modified on disk
        for note_id in active_note_ids & disk_note_ids:
            self.active_windows[note_id].reload_from_storage()

        # Handle external deletions (file removed on disk)
        for note_id in active_note_ids - disk_note_ids:
            window = self.active_windows.pop(note_id, None)
            if window:
                # Mark as deleted so closeEvent does not re-create the file
                window.is_deleted = True
                window.close()

        # Watch any note files that were created after startup
        self.reconcile_watcher_files()

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
        # NOTE: QAction.triggered emits a `checked` bool; use a lambda so it
        # is not accidentally passed through as the note_id argument.
        new_note_action = QAction("➕ New Note", self.menu)
        new_note_action.triggered.connect(lambda _checked=False: self.create_new_note())
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

        # Action: Settings
        settings_action = QAction("⚙️ Settings", self.menu)
        settings_action.triggered.connect(self.open_settings)
        self.menu.addAction(settings_action)

        self.menu.addSeparator()

        # Action: Quit App
        # Quit must go through quit_app() so every window flushes its pending
        # autosave first; QApplication.quit() alone skips closeEvent().
        quit_action = QAction("❌ Quit", self.menu)
        quit_action.triggered.connect(self.quit_app)
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

        window = StickyNoteWindow(
            note_id=note_id,
            app_settings=self.app_settings,
            storage=self.storage,
        )
        window.note_deleted.connect(self.on_note_deleted)

        # Keep the Python object so Show All / tray click can reopen a closed note.
        self.active_windows[note_id] = window
        window.show()

        return window

    def load_or_create_initial_notes(self):
        """Loads all saved notes from storage or creates a new one if none exist."""
        saved_note_ids = self.storage.list_note_ids()

        if saved_note_ids:
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
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
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

    def open_settings(self):
        dialog = SettingsDialog()
        # Connect signal to make "Apply" button update open notes live without
        # closing the settings dialog
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec()

    def on_settings_changed(self):
        """Triggered immediately whenever Apply or Ok is clicked in the settings dialog."""
        # Update storage path in case it changed. All windows share
        # self.storage, so updating it once switches every writer.
        new_storage_path = self.app_settings.get_storage_path()
        if new_storage_path != self.storage.storage_dir:
            self.storage.storage_dir = new_storage_path
            self.storage_path = new_storage_path
            self.update_watcher_paths()
            # Flush every open note into the new directory
            for window in self.active_windows.values():
                window.save_data()

        # Re-apply theme and live settings across all open notes
        for window in self.active_windows.values():
            window.apply_live_settings()

    def quit_app(self):
        """Ensures all notes save their data before closing."""
        for window in list(self.active_windows.values()):
            window.close()
        self.tray.hide()
        self.app.quit()

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Windows taskbar group fix
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "com.kpynotes.app.1.0"
        )

    app = QApplication(sys.argv)

    # Application metadata (must be set before the first QSettings access)
    QCoreApplication.setApplicationName("kpynotes")
    QCoreApplication.setOrganizationName("kpynotes")
    QGuiApplication.setApplicationDisplayName("KPynotes")

    # For KDE Plasma Wayland window rules mapping
    QGuiApplication.setDesktopFileName("io.github.tnordenmark.KPynotes")

    # Keep a reference alive for the duration of the event loop
    tray_app = KPynotesTrayApp(app)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
