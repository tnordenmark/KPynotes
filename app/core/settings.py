# app/core/settings.py
import os
import sys
from PySide6.QtCore import QSettings

class AppSettings:
    def __init__(self):
        # QSettings automatically uses the Organization and App names
        # set in main.py
        self.settings = QSettings()
        
    def get_storage_path(self) -> str:
        default_path = os.path.expanduser("~/.kpynotes")
        return str(self.settings.value("storage_path", default_path, type=str))
    
    def set_storage_path(self, path: str):
        self.settings.setValue("storage_path", path)
        
    def set_theme_override(self, theme: str) -> None:
        self.settings.setValue("theme_override", "system")
        
    def get_always_on_top(self) -> bool:
        return bool(self.settings.value("always_on_top", False, type=bool))
    
    def set_always_on_top(self, enabled: bool):
        self.settings.setValue("always_on_top", enabled)
        
    def get_autostart(self) -> bool:
        return bool(self.settings.value("autostart", False, type=bool))
    
    def set_autostart(self, enabled: bool):
        self.settings.setValue("autostart", enabled)
        self._apply_os_autostart(enabled)
        
    def _apply_os_autostart(self, enable: bool):
        """Handles the native OS hooks for launching at startup."""
        # Get the absolute path to how this app was launched
        exec_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
        
        if sys.platform == 'win32':
            # If Windows write to the standard Run registry key
            run_key = r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"
            reg_settings = QSettings(run_key, QSettings.Format.NativeFormat)
            if enable:
                reg_settings.setValues("kpynotes", exec_path)
            else:
                reg_settings.remove("kpynotes")
                
        elif sys.platform.startswith('linux'):
            autostart_dir = os.path.expanduser("~/.confg/autostart")
            desktop_file = os.path.join(autostart_dir, "kpynotes.desktop")
            
            if enable:
                os.makedirs(autostart_dir, exist_ok=True)
    
    