import json
import os
from typing import Optional, Dict

class LocalStorage:
    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_note(self, note_id: str, position: dict, markdown_content: str):
        filepath = os.path.join(self.storage_dir, f"{note_id}.json")
        data = {
            "position": position,
            "content": markdown_content
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    
        
    def load_note(self, note_id: str) -> Optional[Dict]:
        filepath = os.path.join(self.storage_dir, f"{note_id}.json")
        if not os.path.exists(filepath):
            return None
        
        # Handle the case where the file exists but is empty or corrupted
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # The file exists but is empty or corrupted.
            # Print a warning and return None to load a fresh note.
            print(f"Warning: File '{filepath}' is empty or corrupted. Starting with a fresh note.")
            return None

    def delete_note(self, note_id: str) -> None:
        filepath = os.path.join(self.storage_dir, f"{note_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)