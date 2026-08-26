# main.py
import sys
from PySide6.QtWidgets import QApplication
from app.ui.main_window import StickyNoteWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # In the future, note_manager.py will dictate how many windows spawn here
    window = StickyNoteWindow(note_id="default_note_1")
    window.show()
    
    sys.exit(app.exec())