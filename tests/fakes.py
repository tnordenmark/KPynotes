# tests/fakes.py
"""Test doubles for the sync subsystem."""
from __future__ import annotations

import threading
import time

from app.core.sync.base_sync import (
    BaseSyncEngine,
    RemoteNote,
    SyncConflict,
)


class FakeEngine(BaseSyncEngine):
    """In-memory engine with realistic optimistic concurrency.

    * ``remote``: note_id -> (data, rev); revs are "r1", "r2", ...
    * ``tombstones``: note_id -> deletion timestamp
    * ``fail_queue``: exceptions raised (once each) on subsequent calls
    * ``block``: optional threading.Event to pause inside any call
    * ``calls`` / ``thread_ids``: execution log for assertions
    """

    def __init__(self, authenticated: bool = True):
        self.authenticated = authenticated
        self.remote: dict[str, tuple[dict, str]] = {}
        self.tombstones: dict[str, float] = {}
        self._rev_counter = 0
        self.fail_queue: list[Exception] = []
        self.block: threading.Event | None = None
        self.calls: list[tuple] = []
        self.thread_ids: list[int] = []

    # -- test helpers -------------------------------------------------------

    def put_remote(self, note_id: str, data: dict, rev: str | None = None) -> str:
        """Seed/overwrite a remote note (simulates another device)."""
        self._rev_counter += 1
        rev = rev or f"r{self._rev_counter}"
        self.remote[note_id] = (dict(data), rev)
        return rev

    def calls_of(self, name: str) -> list[tuple]:
        return [c for c in self.calls if c[0] == name]

    def _enter(self, name: str, *args) -> None:
        self.calls.append((name, *args))
        self.thread_ids.append(threading.get_ident())
        if self.block is not None:
            self.block.wait(timeout=10)
        if self.fail_queue:
            raise self.fail_queue.pop(0)

    # -- engine API ---------------------------------------------------------

    def provider_id(self) -> str:
        return "fake"

    def display_name(self) -> str:
        return "Fake Cloud"

    def is_authenticated(self) -> bool:
        return self.authenticated

    def authenticate(self, prompt) -> None:
        self._enter("authenticate")

    def sign_out(self) -> None:
        self.authenticated = False

    def list_remote(self) -> dict[str, RemoteNote]:
        self._enter("list_remote")
        now = time.time()
        return {nid: RemoteNote(nid, rev, now)
                for nid, (_data, rev) in self.remote.items()}

    def fetch_note(self, note_id: str) -> tuple[dict, str]:
        self._enter("fetch", note_id)
        data, rev = self.remote[note_id]
        return dict(data), rev

    def upload_note(self, note_id: str, data: dict, base_rev: str | None) -> str:
        self._enter("upload", note_id, base_rev)
        current = self.remote.get(note_id)
        if current is not None and base_rev is not None and base_rev != current[1]:
            raise SyncConflict("stale base_rev", remote_rev=current[1])
        self._rev_counter += 1
        rev = f"r{self._rev_counter}"
        self.remote[note_id] = (dict(data), rev)
        return rev

    def delete_remote(self, note_id: str, base_rev: str | None) -> bool:
        self._enter("delete_remote", note_id)
        self.remote.pop(note_id, None)
        return True

    def list_tombstones(self) -> dict[str, float]:
        self._enter("list_tombstones")
        return dict(self.tombstones)

    def record_tombstone(self, note_id: str, deleted_ts: float) -> None:
        self._enter("record_tombstone", note_id)
        self.tombstones[note_id] = deleted_ts

    def clear_tombstone(self, note_id: str) -> None:
        self._enter("clear_tombstone", note_id)
        self.tombstones.pop(note_id, None)


class FakeLocalNotes:
    """Dict-backed LocalNoteProvider with controllable mtimes."""

    def __init__(self):
        self.notes: dict[str, dict] = {}
        self.mtimes: dict[str, float] = {}

    def add(self, note_id: str, data: dict, mtime: float | None = None) -> None:
        self.notes[note_id] = dict(data)
        self.mtimes[note_id] = time.time() if mtime is None else mtime

    def list_local_notes(self) -> dict[str, float]:
        return dict(self.mtimes)

    def read_note(self, note_id: str) -> dict | None:
        data = self.notes.get(note_id)
        return dict(data) if data is not None else None

    def write_note(self, note_id: str, data: dict) -> None:
        self.notes[note_id] = dict(data)
        self.mtimes[note_id] = time.time()

    def remove_note(self, note_id: str) -> None:
        self.notes.pop(note_id, None)
        self.mtimes.pop(note_id, None)
