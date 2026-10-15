# tests/test_storage.py
import os

import pytest

from app.core.storage import LocalStorage, is_valid_note_id


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(storage_dir=str(tmp_path / "notes"))


def test_save_and_load_roundtrip(storage):
    assert storage.save_note("abc-123", geometry="ff00", content="hello")
    data = storage.load_note("abc-123")
    assert data == {"id": "abc-123", "geometry": "ff00", "content": "hello"}


def test_load_missing_note_returns_none(storage):
    assert storage.load_note("does-not-exist") is None


def test_save_leaves_no_temp_file(storage):
    assert storage.save_note("abc-123", geometry="ff", content="x")
    assert os.listdir(storage.storage_dir) == ["abc-123.json"]


def test_empty_file_is_quarantined(storage):
    path = storage._get_note_path("broken")
    open(path, "w").close()
    assert storage.load_note("broken") is None
    assert not os.path.exists(path)
    assert os.path.exists(path + ".corrupt")


def test_corrupted_json_is_quarantined(storage):
    path = storage._get_note_path("broken")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ not valid json")
    assert storage.load_note("broken") is None
    assert os.path.exists(path + ".corrupt")


def test_list_note_ids_filters_non_notes(storage):
    storage.save_note("real-note", geometry="", content="")
    base = storage.storage_dir
    # Suffix without dot, extra extension, wrong extension, and directories
    for name in ("badjson", "noext.json.bak", "notes.txt"):
        with open(os.path.join(base, name), "w", encoding="utf-8") as f:
            f.write("x")
    os.makedirs(os.path.join(base, "directory.json"))
    assert storage.list_note_ids() == ["real-note"]


def test_delete_note_is_idempotent(storage):
    storage.save_note("gone", geometry="", content="x")
    storage.delete_note("gone")
    assert storage.load_note("gone") is None
    storage.delete_note("gone")  # deleting again must not raise


def test_get_note_mtime(storage):
    assert storage.get_note_mtime("missing") is None
    storage.save_note("abc", geometry="", content="x")
    assert storage.get_note_mtime("abc") is not None


@pytest.mark.parametrize(
    "bad_id", ["", "..", "../evil", "a/b", "a\\b", ".hidden", "-leading"]
)
def test_invalid_note_ids_rejected(storage, bad_id):
    with pytest.raises(ValueError):
        storage.save_note(bad_id, geometry="", content="x")
    with pytest.raises(ValueError):
        storage.load_note(bad_id)


def test_is_valid_note_id():
    assert is_valid_note_id("550e8400-e29b-41d4-a716-446655440000")
    assert is_valid_note_id("note_1.a")
    assert not is_valid_note_id("")
    assert not is_valid_note_id("..")
    assert not is_valid_note_id("a..b")
    assert not is_valid_note_id("a/b")
