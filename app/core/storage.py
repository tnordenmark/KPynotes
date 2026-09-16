import json
import os
from typing import Optional, Dict, List

class LocalStorage:
    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _get_note_path(self, note_id: str) -> str:
        return os.path.join(self.storage_dir, f"{note_id}.json")

    def save_note(self, note_id: str, geometry: str, markdown_content: str):
        data = {
            "id": note_id,
            "geometry": geometry,
            "content": markdown_content
            }
        with open(self._get_note_path(note_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    
        
    def load_note(self, note_id: str) -> Optional[Dict]:
        path = self._get_note_path(note_id)
        if not os.path.exists(path):
            return None
        # with open(path, "r", encoding="utf-8") as f:
        #    return json.load(f)
        
        # Handle the case where the file exists but is empty or corrupted
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # The file exists but is empty or corrupted.
            # Print a warning and return None to load a fresh note.
            print(f"Warning: File '{path}' is empty or corrupted ({e}). Returning fresh state.")
            return None
        
    def list_note_ids(self) -> list[str]:
        if not os.path.exists(self.storage_dir):
            return []
        
        return [
            filename[:-5]
            for filename in os.listdir(self.storage_dir)
            if filename.endswith("json")
        ]

    def delete_note(self, note_id: str) -> None:
        path = self._get_note_path(note_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                print(f"Error deleting file '{path}': {e}")