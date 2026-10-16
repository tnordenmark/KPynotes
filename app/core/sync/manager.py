# app/core/sync/manager.py
"""Background sync orchestration for KPynotes (Qt layer).

``SyncManager`` owns everything provider-agnostic:

* debounced push coalescing (autosave storms collapse into one upload)
* per-note single-flight (never two workers on the same note)
* retries with exponential backoff for transient transport errors
* pull-all planning, including remote tombstones and conflict handling
* marshalling worker-thread results back to the main thread via signals

Provider engines stay Qt-free (see ``base_sync.py``); this module is the
only place sync interacts with Qt threading primitives.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QRunnable,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)

from app.core.sync.base_sync import (
    AuthExpired,
    BaseSyncEngine,
    InMemorySyncStateStore,
    LocalNoteProvider,
    RemoteNote,
    SyncConflict,
    SyncResult,
    SyncStateStore,
    SyncTransportError,
)

logger = logging.getLogger(__name__)

# Sentinel queue key that serializes global (whole-remote) operations.
_PULL_ALL_KEY = "\x00pull_all"

# Safety valve: give up on a note after this many consecutive conflicts
# (remote is being changed by someone else as fast as we push).
_MAX_CONFLICT_ROUNDS = 3


@dataclass
class _Op:
    """One unit of sync work executed by a worker thread."""
    kind: str                      # "push" | "fetch" | "delete" | "pull_all"
    note_id: str = ""
    data: dict | None = None       # push payload
    base_rev: str | None = None    # optimistic-concurrency base
    conflict: bool = False         # fetch: part of a conflict resolution
    clear_tombstone: bool = False  # push: resurrect over a remote delete
    resolve_base: bool = False     # push: re-read last_rev right before running
    attempts: int = 0              # transport retries so far

    @property
    def key(self) -> str:
        return _PULL_ALL_KEY if self.kind == "pull_all" else self.note_id


@dataclass
class _Outcome:
    """Worker result handed back to the manager thread."""
    op: _Op
    result: SyncResult | None = None
    error: Exception | None = None


class _WorkerSignals(QObject):
    """QRunnable has no QObject; signals live on this helper instead."""
    started = Signal(str)      # note_id ("" for pull_all)
    done = Signal(object)      # _Outcome


class _SyncWorker(QRunnable):
    """Executes one ``_Op`` against the engine inside QThreadPool."""

    def __init__(self, engine: BaseSyncEngine, op: _Op):
        super().__init__()
        self.engine = engine
        self.op = op
        self.signals = _WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        self.signals.started.emit(self.op.note_id)
        outcome = _Outcome(op=self.op)
        try:
            op = self.op
            if op.kind == "pull_all":
                outcome.result = SyncResult(
                    status="listed",
                    note_id="",
                    data={
                        "remote": self.engine.list_remote(),
                        "tombstones": self.engine.list_tombstones(),
                    },
                )
            elif op.kind == "push":
                if op.clear_tombstone:
                    self.engine.clear_tombstone(op.note_id)
                rev = self.engine.upload_note(op.note_id, op.data, op.base_rev)
                outcome.result = SyncResult("pushed", op.note_id, rev)
            elif op.kind == "fetch":
                data, rev = self.engine.fetch_note(op.note_id)
                outcome.result = SyncResult("fetched", op.note_id, rev, data)
            elif op.kind == "delete":
                self.engine.record_tombstone(op.note_id, time.time())
                self.engine.delete_remote(op.note_id, op.base_rev)
                outcome.result = SyncResult("deleted", op.note_id)
            else:
                raise ValueError(f"unknown sync op kind {op.kind!r}")
        except Exception as exc:  # noqa: BLE001 - results are typed below
            outcome.error = exc
        self.signals.done.emit(outcome)


class SyncManager(QObject):
    """Orchestrates sync operations and routes results back to the GUI.

    Thread rules: engine methods run only in pool threads; everything else
    (state store, local provider, signals) runs on the manager's thread.
    """

    # Events for the application (delivered on the main thread):
    note_pulled = Signal(str, object)        # note_id, note data (applied locally)
    remote_deleted = Signal(str)             # note_id (removed locally)
    conflict_detected = Signal(str, object)  # note_id, losing (remote) note data
    note_synced = Signal(str)                # note_id (converged)
    sync_state_changed = Signal(str, str)    # note_id, "syncing"|"synced"|"error"
    sync_error = Signal(str, str)            # note_id ("" = global), message

    def __init__(
        self,
        engine: BaseSyncEngine,
        local_provider: LocalNoteProvider,
        state_store: SyncStateStore | None = None,
        *,
        parent: QObject | None = None,
        debounce_ms: int = 2000,
        retry_delays: tuple[float, ...] = (5.0, 25.0),
        thread_pool: QThreadPool | None = None,
    ):
        super().__init__(parent)
        self.engine = engine
        self.local = local_provider
        self.state: SyncStateStore = state_store or InMemorySyncStateStore()
        self.retry_delays = tuple(retry_delays)
        self.thread_pool = thread_pool or QThreadPool.globalInstance()

        self._dirty: set[str] = set()
        self._pending_pushes: dict[str, dict] = {}  # note_id -> latest data
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(debounce_ms)
        self._debounce.timeout.connect(self._flush_pending_pushes)

        self._queued: dict[str, _Op] = {}            # newest op per key
        self._in_flight: set[str] = set()            # keys currently running
        self._workers: dict[str, _SyncWorker] = {}   # keep refs alive
        self._retry_timers: set[QTimer] = set()
        self._conflict_rounds: dict[str, int] = {}
        self._auth_ok = True

    # -- public API ---------------------------------------------------------

    def is_ready(self) -> bool:
        """True when sync is enabled, authenticated and not paused."""
        return bool(self.engine) and self._auth_ok and self.engine.is_authenticated()

    def schedule_push(self, note_id: str, data: dict) -> None:
        """Coalesced, debounced upload request (call on every autosave)."""
        if not self.is_ready():
            return
        self._dirty.add(note_id)
        self._pending_pushes[note_id] = dict(data)
        self._debounce.start()

    def schedule_delete(self, note_id: str) -> None:
        """Propagate a local deletion (tombstone + remote file removal)."""
        if not self.is_ready():
            return
        self._pending_pushes.pop(note_id, None)
        self._dirty.discard(note_id)
        self._enqueue(_Op(kind="delete", note_id=note_id,
                          base_rev=self.state.last_rev(note_id)))

    def schedule_pull_all(self) -> None:
        """Reconcile the full remote state (startup, timer, manual sync)."""
        if not self.is_ready():
            return
        self._enqueue(_Op(kind="pull_all"))

    def flush(self, timeout_ms: int = 5000) -> bool:
        """Synchronously drive the queue to idle (tests, shutdown).

        Pumps pending debounced pushes immediately, then processes Qt
        events until no work remains or the timeout elapses. Returns True
        when fully idle.
        """
        self._debounce.stop()
        self._flush_pending_pushes()
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            if self._pending_pushes and not self._in_flight:
                self._flush_pending_pushes()
            if not (self._pending_pushes or self._queued or self._in_flight
                    or self._retry_timers):
                return True
            QCoreApplication.processEvents()
            time.sleep(0.005)
        return not (self._queued or self._in_flight)

    def shutdown(self, timeout_ms: int = 3000) -> bool:
        """Flush pending work before app quit; bounded wait."""
        return self.flush(timeout_ms)

    # -- queue internals (main thread only) ---------------------------------

    def _enqueue(self, op: _Op) -> None:
        """Start op now, or supersede any queued op with the same key."""
        key = op.key
        if key in self._in_flight:
            self._queued[key] = op
            return
        self._start_worker(op)

    def _run_next(self, key: str) -> None:
        """After a key frees up, run the newest queued op for it, if any."""
        op = self._queued.pop(key, None)
        if op is not None:
            self._enqueue(op)

    def _flush_pending_pushes(self) -> None:
        for note_id, data in self._pending_pushes.items():
            self._dirty.add(note_id)
            # base_rev is resolved at execution time: when the op waits in
            # the queue behind an in-flight push for the same note, the
            # completed push updates last_rev first (avoids false conflicts).
            self._enqueue(_Op(kind="push", note_id=note_id, data=data,
                              resolve_base=True))
        self._pending_pushes.clear()

    def _start_worker(self, op: _Op) -> None:
        if op.resolve_base:
            op.base_rev = self.state.last_rev(op.note_id)
        worker = _SyncWorker(self.engine, op)
        worker.signals.started.connect(self._on_worker_started)
        worker.signals.done.connect(self._on_worker_done)
        self._in_flight.add(op.key)
        self._workers[op.key] = worker
        self.thread_pool.start(worker)

    @Slot(str)
    def _on_worker_started(self, note_id: str) -> None:
        if note_id:
            self.sync_state_changed.emit(note_id, "syncing")

    @Slot(object)
    def _on_worker_done(self, outcome: object) -> None:
        outcome: _Outcome = outcome
        op = outcome.op
        self._in_flight.discard(op.key)
        self._workers.pop(op.key, None)

        try:
            if outcome.error is not None:
                self._handle_error(op, outcome.error)
            else:
                self._handle_result(op, outcome.result)
        finally:
            self._run_next(op.key)

    def _handle_result(self, op: _Op, result: SyncResult) -> None:
        if op.kind == "push":
            assert result.rev is not None
            self.state.set_last_rev(op.note_id, result.rev)
            self.state.set_last_sync(op.note_id, time.time())
            self._dirty.discard(op.note_id)
            self._conflict_rounds.pop(op.note_id, None)
            self.sync_state_changed.emit(op.note_id, "synced")
            self.note_synced.emit(op.note_id)
        elif op.kind == "fetch":
            self._handle_fetch(op, result)
        elif op.kind == "delete":
            self.state.forget(op.note_id)
            self._conflict_rounds.pop(op.note_id, None)
            self.sync_state_changed.emit(op.note_id, "synced")
        elif op.kind == "pull_all":
            self._handle_listed(result.data)

    def _handle_fetch(self, op: _Op, result: SyncResult) -> None:
        data, rev = result.data, result.rev
        if op.conflict:
            # Local copy wins: hand the losing remote version to the app
            # (it stores a conflict copy), then push local over it.
            self.conflict_detected.emit(op.note_id, data)
            local_data = self.local.read_note(op.note_id)
            if local_data is not None:
                self._enqueue(_Op(kind="push", note_id=op.note_id,
                                  data=local_data, base_rev=rev))
                return
            # Local note vanished meanwhile - a plain pull is the right move.
        self.local.write_note(op.note_id, data)
        self.state.set_last_rev(op.note_id, rev)
        self.state.set_last_sync(op.note_id, time.time())
        self._dirty.discard(op.note_id)
        self.note_pulled.emit(op.note_id, data)

    def _handle_error(self, op: _Op, exc: Exception) -> None:
        note_id = op.note_id
        if isinstance(exc, SyncConflict):
            self._conflict_rounds[note_id] = self._conflict_rounds.get(note_id, 0) + 1
            if self._conflict_rounds[note_id] <= _MAX_CONFLICT_ROUNDS:
                self._enqueue(_Op(kind="fetch", note_id=note_id, conflict=True))
                return
            self.sync_state_changed.emit(note_id, "error")
            self.sync_error.emit(note_id, f"Repeated conflicts syncing '{note_id}'")
            return
        if isinstance(exc, AuthExpired):
            self._auth_ok = False
            self.sync_state_changed.emit(note_id, "error")
            self.sync_error.emit(note_id, "Authentication expired - please sign in again")
            return
        if isinstance(exc, SyncTransportError):
            if op.attempts < len(self.retry_delays):
                delay = exc.retry_after
                if delay is None:
                    delay = self.retry_delays[op.attempts]
                op.attempts += 1
                self._retry_later(op, float(delay))
                return
        # Unknown error or retries exhausted: surface it; keep the note
        # dirty so the next push / pull_all retries later.
        logger.warning("Sync failed for '%s': %s", note_id, exc)
        self.sync_state_changed.emit(note_id, "error")
        self.sync_error.emit(note_id, str(exc))

    def _retry_later(self, op: _Op, delay_s: float) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(max(1, int(delay_s * 1000)))
        timer.timeout.connect(lambda t=timer, o=op: self._on_retry_timer(t, o))
        self._retry_timers.add(timer)
        timer.start()

    def _on_retry_timer(self, timer: QTimer, op: _Op) -> None:
        self._retry_timers.discard(timer)
        timer.deleteLater()
        self._enqueue(op)

    # -- pull-all planning (pure decision logic) ---------------------------

    def _handle_listed(self, payload: object) -> None:
        remote: dict[str, RemoteNote] = payload["remote"]
        tombstones: dict[str, float] = payload["tombstones"]
        local = self.local.list_local_notes()

        ops, removals = self._plan_pull_all(remote, tombstones, local)
        for note_id in removals:
            self.local.remove_note(note_id)
            self.state.forget(note_id)
            self.remote_deleted.emit(note_id)
        for op in ops:
            self._enqueue(op)

    def _plan_pull_all(
        self,
        remote: dict[str, RemoteNote],
        tombstones: dict[str, float],
        local: dict[str, float],
    ) -> tuple[list[_Op], list[str]]:
        """Decide, for every note, what to do. Returns (ops, local_removals)."""
        ops: list[_Op] = []
        removals: list[str] = []

        for note_id in set(remote) | set(local) | set(tombstones):
            r = remote.get(note_id)
            lmod = local.get(note_id)
            tomb = tombstones.get(note_id)
            last_rev = self.state.last_rev(note_id)
            dirty = note_id in self._dirty

            if tomb is not None and (lmod is None or lmod < tomb):
                # Remote deletion wins over an untouched/older local copy.
                if lmod is not None:
                    removals.append(note_id)
                continue
            if tomb is not None and lmod is not None and lmod >= tomb:
                # Local edit happened after the remote delete: resurrect.
                ops.append(_Op(kind="push", note_id=note_id,
                               data=self.local.read_note(note_id),
                               base_rev=r.rev if r else None,
                               clear_tombstone=True))
                continue
            if r is not None and lmod is None:
                ops.append(_Op(kind="fetch", note_id=note_id))
                continue
            if r is not None and lmod is not None:
                if r.rev == last_rev:
                    # Push when edits are pending (flagged by schedule_push,
                    # or detected by mtime after a crash/missed autosave).
                    if dirty or lmod > self.state.last_sync(note_id):
                        ops.append(_Op(kind="push", note_id=note_id,
                                       data=self.local.read_note(note_id),
                                       base_rev=r.rev))
                elif dirty or lmod > self.state.last_sync(note_id):
                    ops.append(_Op(kind="fetch", note_id=note_id, conflict=True))
                else:
                    ops.append(_Op(kind="fetch", note_id=note_id))
                continue
            if r is None and lmod is not None:
                # Local-only note: first upload, or resurrect a file that
                # vanished remotely without a tombstone.
                ops.append(_Op(kind="push", note_id=note_id,
                               data=self.local.read_note(note_id),
                               base_rev=last_rev))
        return ops, removals
