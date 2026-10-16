# app/core/sync/base_sync.py
"""Cloud-sync protocol for KPynotes.

This module defines the *contract* between the application and a sync
provider plugin. It is deliberately free of Qt and of any network code:

* ``BaseSyncEngine``    - the abstract API every provider plugin implements
* value types           - ``RemoteNote``, ``SyncResult``, error hierarchy
* ``LocalNoteProvider`` - structural interface to the app's note storage
* ``SyncStateStore``    - per-note sync bookkeeping (+ in-memory default)

Threading contract
------------------
* Engine methods are only ever called from worker threads (``SyncManager``
  guarantees this); implementations may use internal locks for token refresh.
* ``is_authenticated()`` must be cheap, side-effect free, and safe to call
  from the main thread (no network I/O).
* All other engine methods may block.

Revision tokens
---------------
``rev`` is an opaque string that changes whenever the remote note changes
(Google Drive file ``version``, OneDrive ``eTag``, folder ``mtime:size``).
``upload_note(..., base_rev)`` implements optimistic concurrency: if the
remote copy no longer matches ``base_rev``, raise ``SyncConflict``. Passing
``base_rev=None`` means "create or overwrite unconditionally" (used for the
first upload of a note or when the caller knowingly replaced a lost file).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Protocol


# --- value types -----------------------------------------------------------

@dataclass(frozen=True)
class RemoteNote:
    """Metadata of one note file on the remote side."""
    note_id: str
    rev: str
    modified: float


@dataclass(frozen=True)
class SyncResult:
    """Successful outcome of a worker operation."""
    status: str            # "pushed" | "fetched" | "deleted" | "listed"
    note_id: str
    rev: str | None = None
    data: object = None    # "fetched": note dict; "listed": remote/tombstones


# --- errors ----------------------------------------------------------------

class SyncError(Exception):
    """Base class for sync provider errors."""


class SyncTransportError(SyncError):
    """Transient network/server failure; the manager may retry with backoff."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class SyncConflict(SyncError):
    """Remote copy changed since ``base_rev`` (optimistic concurrency failure)."""

    def __init__(self, message: str, remote_rev: str | None = None):
        super().__init__(message)
        self.remote_rev = remote_rev


class AuthExpired(SyncError):
    """Access token expired or was revoked and could not be refreshed."""


class AuthRequired(SyncError):
    """No usable credentials; the user must sign in first."""


# --- engine contract -------------------------------------------------------

# UI hook: the engine asks the application to open a URL in the browser
# (OAuth authorization page). Called from a worker thread; implementations
# of the application side must be thread-safe (e.g. a queued signal).
AuthPrompt = Callable[[str], None]


class BaseSyncEngine(ABC):
    """Abstract base class that all cloud sync provider plugins subclass.

    Subclasses handle provider-specific authentication and API calls. They
    must NOT implement diffing, conflict policy, retries, or threading -
    ``SyncManager`` owns all of that so every provider behaves identically.
    """

    @abstractmethod
    def provider_id(self) -> str:
        """Stable machine key for the provider (e.g. 'gdrive', 'folder')."""

    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name (e.g. 'Google Drive')."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """True if usable credentials exist. Cheap; no network; main-thread safe."""

    @abstractmethod
    def authenticate(self, prompt: AuthPrompt) -> None:
        """Perform the sign-in flow (may block; runs in a worker thread).

        Uses ``prompt(url)`` to ask the UI to open the authorization page.
        Raises ``SyncError`` subclasses on failure.
        """

    @abstractmethod
    def sign_out(self) -> None:
        """Forget credentials/tokens. Must be idempotent."""

    @abstractmethod
    def list_remote(self) -> dict[str, RemoteNote]:
        """Return metadata for every note currently on the remote side."""

    @abstractmethod
    def fetch_note(self, note_id: str) -> tuple[dict, str]:
        """Download one note. Returns ``(note_data, rev)``."""

    @abstractmethod
    def upload_note(self, note_id: str, data: dict, base_rev: str | None) -> str:
        """Upload one note with optimistic concurrency.

        Returns the new remote ``rev``. Raises ``SyncConflict`` (with the
        current ``remote_rev``) if the remote copy no longer matches
        ``base_rev``; ``base_rev=None`` creates/overwrites unconditionally.
        """

    @abstractmethod
    def delete_remote(self, note_id: str, base_rev: str | None) -> bool:
        """Delete the remote note file. Returns True if it is gone."""

    @abstractmethod
    def list_tombstones(self) -> dict[str, float]:
        """Return ``note_id -> deletion timestamp`` for remote deletions."""

    @abstractmethod
    def record_tombstone(self, note_id: str, deleted_ts: float) -> None:
        """Publish a deletion so other devices can honor it."""

    @abstractmethod
    def clear_tombstone(self, note_id: str) -> None:
        """Retract a tombstone (a local edit "won" over a remote delete)."""


# --- application-side interfaces -------------------------------------------

class LocalNoteProvider(Protocol):
    """Structural interface to the application's note storage.

    The real implementation wraps ``LocalStorage``; tests use a dict-backed
    fake. All calls happen on the main thread.
    """

    def list_local_notes(self) -> dict[str, float]:
        """Return ``note_id -> last modified timestamp`` for all local notes."""

    def read_note(self, note_id: str) -> dict | None:
        """Return the note dict, or None if it does not exist."""

    def write_note(self, note_id: str, data: dict) -> None:
        """Persist a note pulled from the remote side."""

    def remove_note(self, note_id: str) -> None:
        """Delete a note locally (remote tombstone honored)."""


class SyncStateStore(ABC):
    """Per-note sync bookkeeping. All access happens on the main thread."""

    @abstractmethod
    def last_rev(self, note_id: str) -> str | None:
        """Remote rev of the last converged (conflict-free) sync, if any."""

    @abstractmethod
    def set_last_rev(self, note_id: str, rev: str) -> None: ...

    @abstractmethod
    def last_sync(self, note_id: str) -> float:
        """Local timestamp of the last successful sync (0.0 if never)."""

    @abstractmethod
    def set_last_sync(self, note_id: str, ts: float) -> None: ...

    @abstractmethod
    def forget(self, note_id: str) -> None:
        """Drop all bookkeeping for a note (deleted everywhere)."""


class InMemorySyncStateStore(SyncStateStore):
    """Default, non-persistent store. A file-backed store lands with the
    first provider integration (Phase B)."""

    def __init__(self) -> None:
        self._revs: dict[str, str] = {}
        self._syncs: dict[str, float] = {}

    def last_rev(self, note_id: str) -> str | None:
        return self._revs.get(note_id)

    def set_last_rev(self, note_id: str, rev: str) -> None:
        self._revs[note_id] = rev

    def last_sync(self, note_id: str) -> float:
        return self._syncs.get(note_id, 0.0)

    def set_last_sync(self, note_id: str, ts: float) -> None:
        self._syncs[note_id] = ts

    def forget(self, note_id: str) -> None:
        self._revs.pop(note_id, None)
        self._syncs.pop(note_id, None)
