# app/ui/settings_window.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                               QPushButton, QHBoxLayout, QCheckBox, QComboBox,
                               QDialogButtonBox, QFileDialog, QWidget)
from app.core.settings import AppSettings

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KPynotes Settings")
        self.setMinimumWidth(450)
        
        self.app_settings = AppSettings()
        
        self.init_ui()
        self.load_current_settings()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Storage path
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_storage_path)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        path_layout.setContentsMargins(0, 0, 0, 0)
        
        form_layout.addRow("Storage Folder:", path_layout)
        
        # Theme override
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Light Mode", "Dark Mode"])
        form_layout.addRow("Appearance:", self.theme_combo)
        
        # Behavior checks
        self.on_top_check = QCheckBox("Keep new notes always on top")
        form_layout.addRow("", self.on_top_check)
        
        self.autostart_check = QCheckBox("Launch KPynotes at system startup")
        form_layout.addRow("", self.autostart_check)
        
        main_layout.addLayout(form_layout)
        
        # Save and cancel buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)
        
        main_layout.addWidget(self.button_box)
        
    def load_current_settings(self):
        self.path_input.setText(self.app_settings.get_storage_path())
        self.on_top_check.setChecked(self.app_settings.get_always_on_top())
        self.autostart_check.setChecked(self.app_settings.get_autostart())
        
        theme = self.app_settings.get_theme_override()
        if theme == "light":
            self.theme_combo.setCurrentIndex(1)
        if theme == "dark":
            self.theme_combo.setCurrentIndex(2)
        else:
            self.theme_combo.setCurrentIndex(0)
    
    def browse_storage_path(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Storage Directory", self.path_input.text()
        )
        if directory:
            self.path_input.setText(directory)
        
    def save_settings(self):
        # Commit UI values back to QSettings
        self.app_settings.set_storage_path(self.path_input.text())
        self.app_settings.set_always_on_top(self.on_top_check.isChecked())
        self.app_settings.set_autostart(self.autostart_check.isChecked())
        
        theme_idx = self.theme_combo.currentIndex()
        if theme_idx == 1:
            self.app_settings.set_theme_override("light")
        elif theme_idx == 2:
            self.app_settings.set_theme_override("dark")
        else:
            self.app_settings.set_theme_override("system")
        
        self.accept()      