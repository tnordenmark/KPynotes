# app/ui/main_window.py
import logging

from PySide6.QtCore import Qt, QTimer, QEvent, Signal, QByteArray
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QFrame, QMessageBox
from app.ui.components.editor import ScratchpadEditor
from app.ui.components.titlebar import CustomTitleBar
from app.ui.styles import get_note_stylesheet
from app.core.storage import LocalStorage
from app.core.settings import AppSettings

# Import config for save trigger timer delay and other settings
import app.config as config

logger = logging.getLogger(__name__)


class StickyNoteWindow(QWidget):
    # Signal to notify tray app
    note_deleted = Signal(str)

    def __init__(
        self,
        note_id: str,
        app_settings: AppSettings | None = None,
        storage: LocalStorage | None = None,
    ):
        super().__init__()
        self.note_id = note_id
        # Prevent auto-saving a deleted note
        self.is_deleted = False

        # Shared settings/storage instances are injected by the tray app so
        # every window and the tray operate on the same configuration.
        self.app_settings = app_settings if app_settings is not None else AppSettings()
        self.storage = (
            storage
            if storage is not None
            else LocalStorage(storage_dir=self.app_settings.get_storage_path())
        )

        # Modification time of our last successful write; used to ignore the
        # file-watcher events caused by our own saves.
        self._last_saved_mtime: float | None = None

        # Explicitly define the base cursor for the entire window
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Force Qt to track mouse movement even when the window lacks focus
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

        self.setup_window_flags()
        self.init_ui()

        # Call apply_stylesheet directly to detect system theme
        self.apply_stylesheet()

        # Note: OS theme changes are now centrally managed by the tray app
        # (see KPynotesTrayApp._on_color_scheme_changed), so we no longer
        # need to connect to colorSchemeChanged in each window instance.

        self.load_data()
        self.setup_autosave()

    def setup_window_flags(self):
        # Unique identifiers for window rules etc
        self.setWindowTitle(f"KPynotes - {self.note_id}")
        self.setObjectName(f"StickyNote_{self.note_id}")

        # Remove OS borders to make the window frameless
        flags = (
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.CustomizeWindowHint
        )

        # Apply combined window flags
        self.setWindowFlags(flags)

        # Make rounded corners show properly
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Default size, can be adjusted later
        self.resize(300, 350)
        # Enforce minimum size to prevent shrinking it out of existence
        self.setMinimumSize(150, 150)
        # Allow window to track mouse without clicking
        self.setMouseTracking(True)

    def init_ui(self):
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
        # Respect the Theme Override setting
        theme_override = self.app_settings.get_theme_override()

        if theme_override == "light":
            is_dark = False
        elif theme_override == "dark":
            is_dark = True
        else:
            # Fallback to follow system colors
            if scheme is None:
                scheme = QApplication.styleHints().colorScheme()
            is_dark = scheme == Qt.ColorScheme.Dark

        self.setStyleSheet(get_note_stylesheet(is_dark))

    def apply_live_settings(self):
        """Called by the tray app when settings change.

        Storage-path switching is handled centrally by the tray app (which
        owns the shared storage instance); windows only refresh their theme.
        """
        self.apply_stylesheet()

    def get_resize_edge(self, pos):
        # Determine which edge or corner the mouse is near for resizing
        # based on the 8px margin
        margin = 8
        on_left = pos.x() <= margin
        on_right = pos.x() >= self.width() - margin
        on_top = pos.y() <= margin
        on_bottom = pos.y() >= self.height() - margin

        # Corners
        if on_left and on_top:
            return Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        if on_right and on_top:
            return Qt.Edge.TopEdge | Qt.Edge.RightEdge
        if on_left and on_bottom:
            return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if on_right and on_bottom:
            return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        # Sides
        if on_left:
            return Qt.Edge.LeftEdge
        if on_right:
            return Qt.Edge.RightEdge
        if on_top:
            return Qt.Edge.TopEdge
        if on_bottom:
            return Qt.Edge.BottomEdge

        return None

    def eventFilter(self, watched, event):
        event_type = event.type()

        # Only process specific mouse events to reduce overhead
        if event_type in (
            QEvent.Type.MouseMove,
            QEvent.Type.HoverMove,
            QEvent.Type.MouseButtonPress,
        ):

            # Extract global position safely from the event
            if hasattr(event, "globalPosition"):
                global_pos = event.globalPosition().toPoint()
            else:
                return super().eventFilter(watched, event)

            local_pos = self.mapFromGlobal(global_pos)
            edges = self.get_resize_edge(local_pos)

            # Handle hover & cursor changes
            if event_type in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
                if edges:
                    # Apply cursor directly to the widget currently being hovered (overriding child cursors)
                    if edges in (
                        Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
                        Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
                    ):
                        watched.setCursor(Qt.CursorShape.SizeFDiagCursor)
                    elif edges in (
                        Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
                        Qt.Edge.TopEdge | Qt.Edge.RightEdge,
                    ):
                        watched.setCursor(Qt.CursorShape.SizeBDiagCursor)
                    elif edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
                        watched.setCursor(Qt.CursorShape.SizeHorCursor)
                    elif edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
                        watched.setCursor(Qt.CursorShape.SizeVerCursor)

                    # Stop propagation so the text editor doesn't override the cursor
                    return True
                else:
                    # Restore normal cursors based on widget type
                    if (
                        watched == getattr(self, "editor", None)
                        or watched == getattr(self.editor, "viewport", lambda: None)()
                    ):
                        watched.setCursor(Qt.CursorShape.IBeamCursor)
                    else:
                        watched.unsetCursor()

            # Handle mouse click & drag
            elif (
                event_type == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
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
            if (
                watched == getattr(self, "editor", None)
                or watched == getattr(self.editor, "viewport", lambda: None)()
            ):
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
        if hasattr(self, "editor"):
            self.editor.setFocus()

    def save_data(self):
        """Saves the current note data to storage."""
        # A direct save supersedes any pending autosave
        if hasattr(self, "save_timer"):
            self.save_timer.stop()

        # .saveGeometry() -> QByteArray; .toHex() -> QByteArray
        geometry_hex = bytes(self.saveGeometry().toHex().data()).decode("ascii")

        saved = self.storage.save_note(
            note_id=self.note_id,
            geometry=geometry_hex,
            content=self.editor.toPlainText(),
        )
        if saved:
            # Remember our own write so the file watcher can ignore it
            self._last_saved_mtime = self.storage.get_note_mtime(self.note_id)
        else:
            logger.warning(
                "Failed to save note '%s'; will retry on next change.", self.note_id
            )

    def load_data(self):
        data = self.storage.load_note(self.note_id)
        if not data:
            return

        # Prefer the current schema, fall back to the legacy key
        content = data.get("content") or data.get("markdown_content")
        if content:
            self.editor.setPlainText(content)

        # Restore monitor, position and size seamlessly
        if "geometry" in data:
            # Convert the stored hex string back to a QByteArray
            geometry_bytes = QByteArray.fromHex(data["geometry"].encode("ascii"))
            self.restoreGeometry(geometry_bytes)

        # This on-disk version is now the baseline we last saw
        self._last_saved_mtime = self.storage.get_note_mtime(self.note_id)

    def reload_from_storage(self):
        """Reloads content from disk if changed externally, preserving cursor position."""
        # Local unsaved edits win: flush them and skip the external copy.
        if self.save_timer.isActive():
            self.save_timer.stop()
            self.save_data()
            return

        # Our own writes trigger the file watcher; ignore those events.
        mtime = self.storage.get_note_mtime(self.note_id)
        if mtime is not None and mtime == self._last_saved_mtime:
            return

        updated_note = self.storage.load_note(self.note_id)
        if not updated_note:
            return

        new_text = (
            updated_note.get("content") or updated_note.get("markdown_content") or ""
        )
        current_text = self.editor.toPlainText()

        # Only update if content actually differs on disk
        if new_text == current_text:
            return

        # Save cursor position before updating text
        cursor = self.editor.textCursor()
        position = cursor.position()

        # Block signals to prevent the reload itself triggering an autosave
        self.editor.blockSignals(True)
        self.editor.setPlainText(new_text)
        # Restore cursor position bounded to new content length
        cursor.setPosition(min(position, len(new_text)))
        self.editor.setTextCursor(cursor)
        self.editor.blockSignals(False)

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
        # Restart the timer on each change. Guarded because resizeEvent can
        # call this before the autosave timer exists.
        if hasattr(self, "save_timer"):
            self.save_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Trigger save on resize as well
        self.trigger_autosave()

    def request_delete(self):
        # Show confirmation dialog before deleting
        reply = QMessageBox.question(
            self,
            "Delete Note",
            "Are you sure you want to delete this note?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
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

        # For deleted notes, explicitly schedule the window for deletion
        # to prevent memory leaks (the reference in active_windows was already
        # removed by on_note_deleted before close() was called).
        if self.is_deleted:
            self.deleteLater()

        event.accept()
