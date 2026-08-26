from PySide6.QtGui import QKeySequence, QShortcut, QTextCharFormat, QFont
from PySide6.QtWidgets import QTextEdit

class ScratchpadEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Type your notes here...")
        self.setup_shortcuts()

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
        weight = QFont.Bold if fmt.fontWeight() != QFont.Bold else QFont.Normal
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
        fmt.setStrikeOut(not fmt.fontStrikeOut())
        self.mergeCurrentCharFormat(fmt)
