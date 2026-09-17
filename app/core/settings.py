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
        
    def get_theme_override(self) -> str:
        return str(self.settings.value("theme_override", "system", type=str))
        
    def set_theme_override(self, theme: str) -> None:
        self.settings.setValue("theme_override", theme)
        
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
                reg_settings.setValue("kpynotes", exec_path)
            else:
                reg_settings.remove("kpynotes")
                
        elif sys.platform.startswith('linux'):
            autostart_dir = os.path.expanduser("~/.config/autostart")
            desktop_file = os.path.join(autostart_dir, "kpynotes.desktop")
            
            if enable:
                os.makedirs(autostart_dir, exist_ok=True)
                with open(desktop_file, "w", encoding="utf-8") as f:
                    f.write(f"[Desktop Entry]\n"
                            f"Type=Application\n"
                            f"Name=KPynotes\n"
                            f"Exec={exec_path}\n"
                            f"Hidden=false\n"
                            f"NoDisplay=false\n"
                            f"X-GNOME-Autostart-enabled=true\n")
            else:
                if os.path.exists(desktop_file):
                    os.remove(desktop_file)
