from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QTextCharFormat, QFont, QCursor
from PySide6.QtWidgets import QTextEdit

class ScratchpadEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set explicit text editing cursors on both the widget and its interior viewport
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        
        self.setPlaceholderText("Type your notes here...")
        self.setup_shortcuts()
        
    def contextMenuEvent(self, event):
        # Generate default context menu and pass local position so
        # selection / cursor placement context works. Useful to for example
        # format text or for future spell check
        menu = self.createStandardContextMenu(event.pos())
        
        # Map local viewport position to global surface coordinates for Wayland
        global_pos = self.viewport().mapToGlobal(event.pos())
        
        # Display context menu at the mapped position
        menu.exec(global_pos)

    def setup_shortcuts(self):
        # Bold formatting shortcut
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(self.toggle_bold)
        # Italic formatting shortcut
        QShortcut(QKeySequence("Ctrl+I"), self).activated.connect(self.toggle_italic)
        # Underline formatting shortcut
        QShortcut(QKeySequence("Ctrl+U"), self).activated.connect(self.toggle_underline)
        # Strikethrough formatting shortcut
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self.toggle_strikethrough)
        
    # Formatting methods
    def toggle_bold(self):
        fmt = self.currentCharFormat()
        weight = QFont.Weight.Bold if fmt.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal
        fmt.setFontWeight(weight)
        self.mergeCurrentCharFormat(fmt)

    def toggle_italic(self):
        fmt = self.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.mergeCurrentCharFormat(fmt)

    def toggle_underline(self):
        fmt = self.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.mergeCurrentCharFormat(fmt)

    def toggle_strikethrough(self):
        fmt = self.currentCharFormat()
        fmt.setFontStrikeOut(not fmt.fontStrikeOut())
        self.mergeCurrentCharFormat(fmt)
