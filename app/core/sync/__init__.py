# app/core/sync/__init__.py
"""Cloud sync subsystem.

* ``base_sync``  - provider protocol (Qt-free): engines, value types, stores
* ``manager``    - Qt orchestration: single-flight, coalescing, retries
* ``registry``   - plugin registry (added with the first provider, Phase B)
"""
from app.core.sync.base_sync import (
    AuthExpired,
    AuthRequired,
    BaseSyncEngine,
    InMemorySyncStateStore,
    LocalNoteProvider,
    RemoteNote,
    SyncConflict,
    SyncError,
    SyncResult,
    SyncStateStore,
    SyncTransportError,
)
from app.core.sync.manager import SyncManager

__all__ = [
    "AuthExpired",
    "AuthRequired",
    "BaseSyncEngine",
    "InMemorySyncStateStore",
    "LocalNoteProvider",
    "RemoteNote",
    "SyncConflict",
    "SyncError",
    "SyncManager",
    "SyncResult",
    "SyncStateStore",
    "SyncTransportError",
]
