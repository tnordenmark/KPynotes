# app/ui/settings_window.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFileDialog,
    QMessageBox
)
from app.core.settings import AppSettings


class SettingsDialog(QDialog):
    # Signal to inform main.py to reload open notes or apply theme live
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KPynotes Settings")
        self.setMinimumWidth(450)
        
        # Ensure the dialog behvaes correctly when opened from tray/main window
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.app_settings = AppSettings()
        
        # Store initial state to track "dirty" changes for the Apply button
        self._initial_state = {}

        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Storage path
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.textChanged.connect(self._check_dirty_state)

        # Browse button to select a directory
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_storage_path)

        # Reset button to reset to default storage path from QStandardPaths
        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset to default storage path")
        reset_btn.clicked.connect(self.reset_storage_path)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        path_layout.addWidget(reset_btn)
        path_layout.setContentsMargins(0, 0, 0, 0)

        form_layout.addRow("Storage Folder:", path_layout)

        # Theme override
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Light Mode", "Dark Mode"])
        self.theme_combo.currentIndexChanged.connect(self._check_dirty_state)
        form_layout.addRow("Appearance:", self.theme_combo)

        # Behavior checks
        # Eventual future always on top, not used for now
        # self.on_top_check = QCheckBox("Keep new notes always on top")
        # form_layout.addRow("", self.on_top_check)
        self.autostart_check = QCheckBox("Launch KPynotes at system startup")
        self.autostart_check.stateChanged.connect(self._check_dirty_state)
        form_layout.addRow("", self.autostart_check)

        main_layout.addLayout(form_layout)

        # Save and cancel buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.on_ok_clicked)
        self.button_box.rejected.connect(self.reject)
        
        apply_btn = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn:
            apply_btn.clicked.connect(self.apply_settings)
            # Initially disabled until changes are made
            apply_btn.setEnabled(False)

        main_layout.addWidget(self.button_box)

    def load_current_settings(self):
        self.path_input.setText(self.app_settings.get_storage_path())
        # Eventual future always on top, not used for now
        # self.on_top_check.setChecked(self.app_settings.get_always_on_top())
        self.autostart_check.setChecked(self.app_settings.get_autostart())

        theme = self.app_settings.get_theme_override()
        if theme == "light":
            self.theme_combo.setCurrentIndex(1)
        elif theme == "dark":
            self.theme_combo.setCurrentIndex(2)
        else:
            self.theme_combo.setCurrentIndex(0)
            
        # Capture the state after loading to track future changes
        self._initial_state = self._get_current_ui_state()
        self._check_dirty_state()
        
    def _get_current_ui_state(self):
        """Helper to get the current state of the UI inputs"""
        return {
            "storage_path": self.path_input.text(),
            # "always_on_top": self.on_top_check.isChecked(),
            "autostart": self.autostart_check.isChecked(),
            "theme_override": self.theme_combo.currentIndex(),
        }
        
    def _check_dirty_state(self):
        """Enables/Disables the Apply button if settings differ from saved state."""
        current_state = self._get_current_ui_state()
        is_dirty = current_state != self._initial_state
        
        apply_btn = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn:
            apply_btn.setEnabled(is_dirty)

    def browse_storage_path(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Storage Directory", self.path_input.text()
        )
        if directory:
            self.path_input.setText(directory)
            # Update tooltip so user can see full path on hover
            self.path_input.setToolTip(directory)

    def reset_storage_path(self):
        """Resets the storage path text field to QStandardPaths default."""
        default_path = self.app_settings.get_default_storage_path()
        self.path_input.setText(default_path)

    def save_settings(self):
        """Commit UI values back to QSettings."""
        self.app_settings.set_storage_path(self.path_input.text())
        
        ## Handle Autostart with error checking (to handle Windows/KDE differences)
        autostart_requested = self.autostart_check.isChecked()
        success = self.app_settings.set_autostart(autostart_requested)
        
        if not success and autostart_requested:
            QMessageBox.warning(
                self,
                "Autostart Failed",
                "Failed to enable autostart. Please system permissions.",
            )
            # Revert UI to reflect actual state
            self.autostart_check.setChecked(False)
            
        # Eventual future always on top, not used for now
        # self.app_settings.set_always_on_top(self.on_top_check.isChecked())
        self.app_settings.set_autostart(self.autostart_check.isChecked())

        theme_idx = self.theme_combo.currentIndex()
        if theme_idx == 1:
            self.app_settings.set_theme_override("light")
        elif theme_idx == 2:
            self.app_settings.set_theme_override("dark")
        else:
            self.app_settings.set_theme_override("system")
            
        # Update initial state so Apply button disables after saving
        self._initial_state = self._get_current_ui_state()
        self._check_dirty_state()
        
        # Notify KPynotesTrayApp to reload open notes or apply theme live
        self.settings_changed.emit()

    def apply_settings(self):
        """Action for the Apply button: persist settings and leave the dialog open."""
        self.save_settings()
        
    def on_ok_clicked(self):
        """Action for the OK button: persist settings and close the dialog."""
        # Only save if there are changes to avoid unnecessary writes and signal spam
        if self._get_current_ui_state() != self._initial_state:
            self.save_settings()
        self.accept()