# tests/test_sync_manager.py
"""Behavioural tests for SyncManager: coalescing, single-flight, conflicts,
tombstones, retries, and Qt signal delivery."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from app.core.sync.base_sync import AuthExpired, SyncConflict, SyncTransportError
from app.core.sync.manager import SyncManager
from tests.fakes import FakeEngine, FakeLocalNotes


@pytest.fixture
def env(qt_app):
    engine = FakeEngine()
    local = FakeLocalNotes()
    mgr = SyncManager(engine, local, debounce_ms=10, retry_delays=(0.01, 0.01))
    events = SimpleNamespace(synced=[], pulled=[], deleted=[], conflict=[],
                             errors=[], states=[])
    mgr.note_synced.connect(lambda nid: events.synced.append(nid))
    mgr.note_pulled.connect(lambda nid, data: events.pulled.append((nid, data)))
    mgr.remote_deleted.connect(lambda nid: events.deleted.append(nid))
    mgr.conflict_detected.connect(
        lambda nid, data: events.conflict.append((nid, data)))
    mgr.sync_error.connect(lambda nid, msg: events.errors.append((nid, msg)))
    mgr.sync_state_changed.connect(
        lambda nid, state: events.states.append((nid, state)))
    return SimpleNamespace(engine=engine, local=local, mgr=mgr, events=events)


# -- push path --------------------------------------------------------------

def test_first_push_creates_and_updates_state(env):
    env.mgr.schedule_push("n1", {"content": "hi"})
    assert env.mgr.flush()
    assert env.engine.calls_of("upload") == [("upload", "n1", None)]
    assert env.engine.remote["n1"][0] == {"content": "hi"}
    assert env.mgr.state.last_rev("n1") == env.engine.remote["n1"][1]
    assert env.events.synced == ["n1"]


def test_debounce_coalesces_pushes_to_latest(env):
    for i in range(5):
        env.mgr.schedule_push("n1", {"content": f"v{i}"})
    assert env.mgr.flush()
    assert len(env.engine.calls_of("upload")) == 1
    assert env.engine.remote["n1"][0] == {"content": "v4"}


def test_single_flight_runs_newest_queued_push_after_first(env):
    env.engine.block = threading.Event()  # hold the first push in-flight
    env.mgr.schedule_push("n1", {"content": "first"})
    assert env.mgr.flush(timeout_ms=200) is False  # worker is blocked
    env.mgr.schedule_push("n1", {"content": "second"})
    env.engine.block.set()
    assert env.mgr.flush()

    uploads = env.engine.calls_of("upload")
    assert [(c[0], c[2]) for c in uploads] == [("upload", None), ("upload", "r1")]
    assert env.engine.remote["n1"] == ({"content": "second"}, "r2")


def test_push_conflict_local_wins_with_conflict_copy_event(env):
    rev_a = env.engine.put_remote("n1", {"content": "theirs-old"})
    env.mgr.state.set_last_rev("n1", rev_a)
    env.engine.put_remote("n1", {"content": "theirs-new"})  # other device pushes
    env.local.add("n1", {"content": "mine"}, mtime=time.time())

    env.mgr.schedule_push("n1", {"content": "mine"})
    assert env.mgr.flush()

    # Losing remote version was handed to the app for a conflict copy...
    assert [c[0] for c in env.events.conflict] == ["n1"]
    assert env.events.conflict[0][1] == {"content": "theirs-new"}
    # ...and the local version won the note itself.
    assert env.engine.remote["n1"][0] == {"content": "mine"}
    assert env.mgr.state.last_rev("n1") == env.engine.remote["n1"][1]
    assert env.events.synced == ["n1"]


def test_repeated_conflicts_give_up_with_error(env):
    # Every push sees a remote that changed again -> conflict ping-pong.
    rev = env.engine.put_remote("n1", {"content": "r"})
    env.local.add("n1", {"content": "mine"}, mtime=time.time())
    env.mgr.state.set_last_rev("n1", rev)

    def churn(note_id, data, base_rev):
        env.engine.put_remote(note_id, {"content": f"churn-{time.time()}"})
        raise SyncConflict("remote changed again", remote_rev="rX")

    env.engine.upload_note = churn  # type: ignore[method-assign]
    env.mgr.schedule_push("n1", {"content": "mine"})
    env.mgr.flush(timeout_ms=5000)
    assert any("Repeated conflicts" in msg for _nid, msg in env.events.errors)


# -- pull-all path ----------------------------------------------------------

def test_pull_all_fetches_new_remote_note(env):
    env.engine.put_remote("r-note", {"content": "from cloud"})
    env.mgr.schedule_pull_all()
    assert env.mgr.flush()
    assert env.events.pulled == [("r-note", {"content": "from cloud"})]
    assert env.local.notes["r-note"] == {"content": "from cloud"}
    assert env.mgr.state.last_rev("r-note") is not None


def test_pull_all_remote_edit_with_clean_local_pulls(env):
    rev = env.engine.put_remote("n1", {"content": "v1"})
    env.local.add("n1", {"content": "v1"}, mtime=1000.0)
    env.mgr.state.set_last_rev("n1", rev)
    env.mgr.state.set_last_sync("n1", 1000.0)
    env.engine.put_remote("n1", {"content": "v2"})

    env.mgr.schedule_pull_all()
    assert env.mgr.flush()
    assert env.local.notes["n1"] == {"content": "v2"}
    assert env.events.pulled and not env.events.conflict


def test_pull_all_conflict_keeps_local_and_copies_remote(env):
    env.engine.put_remote("n1", {"content": "theirs-old"})   # r1: last synced
    env.local.add("n1", {"content": "mine"}, mtime=2000.0)
    env.mgr.state.set_last_rev("n1", "r1")
    env.mgr.state.set_last_sync("n1", 1000.0)
    env.engine.put_remote("n1", {"content": "theirs"})       # r2: other device

    env.mgr.schedule_pull_all()
    assert env.mgr.flush()
    assert [c[0] for c in env.events.conflict] == ["n1"]
    assert env.events.conflict[0][1] == {"content": "theirs"}
    assert env.local.notes["n1"] == {"content": "mine"}
    assert env.engine.remote["n1"][0] == {"content": "mine"}


def test_pull_all_pushes_local_edit_when_remote_unchanged(env):
    # Edit survived locally (e.g. crash before autosave pushed it) while
    # the remote copy stayed at the last synced rev.
    env.engine.put_remote("n1", {"content": "old"})
    env.local.add("n1", {"content": "edited"}, mtime=2000.0)
    env.mgr.state.set_last_rev("n1", "r1")
    env.mgr.state.set_last_sync("n1", 1000.0)

    env.mgr.schedule_pull_all()
    assert env.mgr.flush()
    assert env.engine.remote["n1"][0] == {"content": "edited"}
    assert env.events.conflict == []


def test_pull_all_pushes_new_local_note(env):
    env.local.add("l-note", {"content": "fresh"}, mtime=1000.0)
    env.mgr.schedule_pull_all()
    assert env.mgr.flush()
    assert env.engine.remote["l-note"][0] == {"content": "fresh"}


# -- tombstones / deletions -------------------------------------------------

def test_remote_tombstone_removes_stale_local_copy(env):
    env.local.add("n1", {"content": "old"}, mtime=1000.0)
    env.engine.tombstones["n1"] = 2000.0
    env.mgr.schedule_pull_all()
    assert env.mgr.flush()
    assert "n1" not in env.local.notes
    assert env.events.deleted == ["n1"]


def test_local_edit_after_tombstone_resurrects_note(env):
    env.local.add("n1", {"content": "edited later"}, mtime=3000.0)
    env.engine.tombstones["n1"] = 2000.0
    env.mgr.schedule_pull_all()
    assert env.mgr.flush()
    assert env.engine.remote["n1"][0] == {"content": "edited later"}
    assert "n1" not in env.engine.tombstones
    assert env.events.deleted == []


def test_local_delete_propagates_tombstone(env):
    rev = env.engine.put_remote("n1", {"content": "x"})
    env.local.add("n1", {"content": "x"})
    env.mgr.state.set_last_rev("n1", rev)
    env.mgr.schedule_delete("n1")
    assert env.mgr.flush()
    assert "n1" not in env.engine.remote
    assert "n1" in env.engine.tombstones
    assert env.mgr.state.last_rev("n1") is None


# -- retries / auth ---------------------------------------------------------

def test_transport_errors_retry_then_succeed(env):
    env.engine.fail_queue = [SyncTransportError("down"),
                             SyncTransportError("still down")]
    env.mgr.schedule_push("n1", {"content": "hi"})
    assert env.mgr.flush()
    assert len(env.engine.calls_of("upload")) == 3  # 1 try + 2 retries
    assert env.events.synced == ["n1"]
    assert env.events.errors == []


def test_retry_exhausted_emits_error(env):
    env.engine.fail_queue = [SyncTransportError("down")] * 3
    env.mgr.schedule_push("n1", {"content": "hi"})
    env.mgr.flush()
    assert len(env.engine.calls_of("upload")) == 3
    assert len(env.events.errors) == 1
    assert ("n1", "error") in env.events.states


def test_retry_after_hint_is_honoured(env):
    env.engine.fail_queue = [SyncTransportError("slow", retry_after=0.01)]
    env.mgr.schedule_push("n1", {"content": "hi"})
    assert env.mgr.flush()
    assert env.events.synced == ["n1"]


def test_auth_expired_pauses_sync(env):
    env.engine.fail_queue = [AuthExpired("expired")]
    env.mgr.schedule_push("n1", {"content": "hi"})
    env.mgr.flush()
    assert any("Authentication" in msg for _nid, msg in env.events.errors)
    assert not env.mgr.is_ready()
    before = len(env.engine.calls)
    env.mgr.schedule_push("n1", {"content": "more"})
    env.mgr.flush()
    assert len(env.engine.calls) == before  # paused: nothing new executed


# -- Qt integration ---------------------------------------------------------

def test_workers_run_off_main_thread_and_signals_arrive(qt_app):
    engine = FakeEngine()
    local = FakeLocalNotes()
    mgr = SyncManager(engine, local, debounce_ms=5)
    synced: list[str] = []
    mgr.note_synced.connect(synced.append)

    main_thread = threading.get_ident()
    mgr.schedule_push("n1", {"content": "x"})
    deadline = time.monotonic() + 5
    while not synced and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert synced == ["n1"]
    assert engine.thread_ids and engine.thread_ids[0] != main_thread


def test_shutdown_flushes_pending_work(qt_app):
    engine = FakeEngine()
    local = FakeLocalNotes()
    mgr = SyncManager(engine, local, debounce_ms=50)
    mgr.schedule_push("n1", {"content": "final"})
    assert mgr.shutdown(3000)
    assert engine.remote["n1"][0] == {"content": "final"}
