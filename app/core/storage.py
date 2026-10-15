# app/core/storage.py
import json
import logging
import os
import re
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Note IDs are either locally generated UUIDs or file names discovered on
# disk. Validate them before using them as path components to prevent
# path traversal if a sync provider ever supplies remote identifiers.
_NOTE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def is_valid_note_id(note_id: str) -> bool:
    """Returns True if note_id is safe to use as a single file name component."""
    return bool(note_id) and ".." not in note_id and bool(_NOTE_ID_RE.match(note_id))


class LocalStorage:
    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_note_path(self, note_id: str) -> str:
        if not is_valid_note_id(note_id):
            raise ValueError(f"Invalid note id: {note_id!r}")
        return os.path.join(self.storage_dir, f"{note_id}.json")

    def save_note(self, note_id: str, geometry: str, content: str) -> bool:
        """Atomically persists a note. Returns True on success.

        Writes to a temporary sibling file and renames it over the target so
        a crash or power loss mid-write can never truncate the real note.
        """
        data = {
            "id": note_id,
            "geometry": geometry,
            "content": content,
        }
        path = self._get_note_path(note_id)
        tmp_path = f"{path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            os.replace(tmp_path, path)
            return True
        except OSError as e:
            logger.error("Error saving note '%s': %s", note_id, e)
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            return False

    def load_note(self, note_id: str) -> Optional[Dict]:
        path = self._get_note_path(note_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            # Quarantine the unreadable file so the next autosave cannot
            # silently overwrite whatever content it still contains.
            quarantine = f"{path}.corrupt"
            try:
                os.replace(path, quarantine)
                logger.warning(
                    "Note file '%s' is unreadable (%s). Moved to '%s'.",
                    path,
                    e,
                    quarantine,
                )
            except OSError as rename_err:
                logger.warning(
                    "Note file '%s' is unreadable (%s) and could not be "
                    "quarantined: %s",
                    path,
                    e,
                    rename_err,
                )
            return None

    def list_note_ids(self) -> list[str]:
        if not os.path.exists(self.storage_dir):
            return []

        suffix = ".json"
        return [
            filename[: -len(suffix)]
            for filename in os.listdir(self.storage_dir)
            if filename.endswith(suffix)
            and is_valid_note_id(filename[: -len(suffix)])
            and os.path.isfile(os.path.join(self.storage_dir, filename))
        ]

    def get_note_mtime(self, note_id: str) -> Optional[float]:
        """Returns the note file's modification time, or None if unavailable."""
        try:
            return os.path.getmtime(self._get_note_path(note_id))
        except OSError:
            return None

    def delete_note(self, note_id: str) -> None:
        path = self._get_note_path(note_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.error("Error deleting file '%s': %s", path, e)
