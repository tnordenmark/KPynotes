# tests/test_sync_protocol.py
"""Unit tests for the Qt-free sync protocol types."""

import pytest

from app.core.sync.base_sync import (
    BaseSyncEngine,
    InMemorySyncStateStore,
    SyncConflict,
    SyncTransportError,
)


def test_engine_is_abstract():
    with pytest.raises(TypeError):
        BaseSyncEngine()  # type: ignore[abstract]


def test_conflict_carries_remote_rev():
    exc = SyncConflict("stale", remote_rev="r7")
    assert exc.remote_rev == "r7"


def test_transport_error_retry_after():
    exc = SyncTransportError("slow down", retry_after=42.0)
    assert exc.retry_after == 42.0
    assert SyncTransportError("x").retry_after is None


def test_in_memory_state_store_roundtrip():
    store = InMemorySyncStateStore()
    assert store.last_rev("n1") is None
    assert store.last_sync("n1") == 0.0
    store.set_last_rev("n1", "r1")
    store.set_last_sync("n1", 123.5)
    assert store.last_rev("n1") == "r1"
    assert store.last_sync("n1") == 123.5
    store.forget("n1")
    assert store.last_rev("n1") is None
    assert store.last_sync("n1") == 0.0
