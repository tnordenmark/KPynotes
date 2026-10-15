from abc import ABC, abstractmethod
from typing import Any
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class BaseSyncEngine(ABC):
    """Abstract Base Class that all cloud sync provider plugins must subclass.
    
    Subclasses handle provider-specific authentication, API calls, and local-remote
    file diffing without needing to manage Qt threading logic directly.
    """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Returns the human-readable provider name (e.g., 'Google Drive', 'OneDrive')."""
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Returns True if valid OAuth credentials or access tokens exist."""
        pass

    @abstractmethod
    def sync_note(self, note_id: str, local_data: dict[str, Any]) -> dict[str, Any] | None:
        """Uploads local note data or pulls remote changes.
        
        Returns the updated note data dictionary if changes occurred,
        or None if local and remote are already in sync.
        
        Raises Exception on network/API errors.
        """
        pass

    @abstractmethod
    def delete_note(self, note_id: str) -> bool:
        """Deletes the remote note file corresponding to note_id.
        
        Returns True on successful deletion.
        """
        pass


class SyncWorkerSignals(QObject):
    """Qt Signals instance for emitting worker status back to the main GUI thread.
    
    QRunnable does not inherit from QObject, so signals must be declared on
    a dedicated helper QObject instance.
    """
    started = Signal(str)                          # note_id
    finished = Signal(str, object)                 # note_id, updated_note_data (dict | None)
    failed = Signal(str, str)                      # note_id, error_message


class SyncWorker(QRunnable):
    """Background task executed inside QThreadPool.
    
    Runs cloud IO asynchronously to keep the PySide6 main loop responsive.
    """

    def __init__(self, engine: BaseSyncEngine, note_id: str, local_data: dict[str, Any], action: str = "sync"):
        super().__init__()
        self.engine = engine
        self.note_id = note_id
        self.local_data = local_data
        self.action = action  # "sync" or "delete"
        self.signals = SyncWorkerSignals()

        # Ensure the runnable object cleans itself up after completion
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        """Executed automatically in a background thread by QThreadPool."""
        self.signals.started.emit(self.note_id)
        
        try:
            if self.action == "sync":
                result = self.engine.sync_note(self.note_id, self.local_data)
                self.signals.finished.emit(self.note_id, result)
            elif self.action == "delete":
                self.engine.delete_note(self.note_id)
                self.signals.finished.emit(self.note_id, None)
        except Exception as exc:
            self.signals.failed.emit(self.note_id, str(exc))


class SyncManager(QObject):
    """Orchestrates sync workers across QThreadPool and routes events to KPynotes.
    
    Provides a simple interface for KPynotesTrayApp to dispatch background sync operations.
    """
    sync_completed = Signal(str, object)  # note_id, updated_data
    sync_failed = Signal(str, str)        # note_id, error_msg

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.engine: BaseSyncEngine | None = None
        self.thread_pool = QThreadPool.globalInstance()

    def set_engine(self, engine: BaseSyncEngine):
        """Registers an active sync plugin engine (e.g., GoogleDriveEngine)."""
        self.engine = engine

    def sync_note_async(self, note_id: str, local_data: dict[str, Any]):
        """Schedules a note synchronization task in the background thread pool."""
        if not self.engine or not self.engine.is_authenticated():
            return

        worker = SyncWorker(self.engine, note_id, local_data, action="sync")
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.failed.connect(self._on_worker_failed)
        
        self.thread_pool.start(worker)

    def delete_note_async(self, note_id: str):
        """Schedules a remote deletion task in the background thread pool."""
        if not self.engine or not self.engine.is_authenticated():
            return

        worker = SyncWorker(self.engine, note_id, local_data={}, action="delete")
        worker.signals.finished.connect(self._on_worker_finished)
        worker.signals.failed.connect(self._on_worker_failed)
        
        self.thread_pool.start(worker)

    @Slot(str, object)
    def _on_worker_finished(self, note_id: str, updated_data: Any):
        self.sync_completed.emit(note_id, updated_data)

    @Slot(str, str)
    def _on_worker_failed(self, note_id: str, error_msg: str):
        self.sync_failed.emit(note_id, error_msg)