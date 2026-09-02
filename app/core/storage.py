import json
import os
from typing import Optional, Dict

class LocalStorage:
    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _get_note_path(self, note_id: str) -> str:
        return os.path.join(self.storage_dir, f"{note_id}.json")

    def save_note(self, note_id: str, position: dict, size: dict, markdown_content: str):
        data = {
            "id": note_id,
            "position": position,
            "size": size,
            "content": markdown_content
            }
        with open(self._get_note_path(note_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    
        
    def load_note(self, note_id: str) -> Optional[Dict]:
        path = self._get_note_path(note_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
        
        # Handle the case where the file exists but is empty or corrupted
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # The file exists but is empty or corrupted.
            # Print a warning and return None to load a fresh note.
            print(f"Warning: File '{filepath}' is empty or corrupted. Starting with a fresh note.")
            return None
        
    def list_note_ids(self) -> list[str]:
        if not os.path.exists(self.storage_dir):
            return []
        
        note_ids = []
        for filename in os.listdir(self.storage_dir):
            # Remove the .json extension
            if filename.endswith(".json"):
                note_ids.append(filename[:-5])
        return note_ids

    def delete_note(self, note_id: str) -> None:
        filepath = os.path.join(self.storage_dir, f"{note_id}.json")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Error deleting file '{filepath}': {e}")