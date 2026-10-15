# app/core/settings.py
import logging
import os
import sys
from PySide6.QtCore import QSettings, QStandardPaths

logger = logging.getLogger(__name__)


class AppSettings:
    def __init__(self):
        # QSettings automatically uses the Organization and App names
        # set in main.py
        self.settings = QSettings()

    def get_default_storage_path(self) -> str:
        """Returns the OS-specific default storage directory."""
        return QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )

    def get_storage_path(self) -> str:
        default_path = self.get_default_storage_path()
        path = str(self.settings.value("storage_path", default_path, type=str))

        # Ensure the directory exists before the app attempts to write notes.
        # Fall back to the default location if the configured path is
        # unusable (e.g. a file occupies the path, or permissions deny it).
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            logger.error(
                "Cannot use storage path '%s' (%s); falling back to '%s'.",
                path, e, default_path,
            )
            path = default_path
            os.makedirs(path, exist_ok=True)
        return path

    def set_storage_path(self, path: str):
        self.settings.setValue("storage_path", path)

    def get_theme_override(self) -> str:
        return str(self.settings.value("theme_override", "system", type=str))

    def set_theme_override(self, theme: str) -> None:
        self.settings.setValue("theme_override", theme)

    def get_autostart(self) -> bool:
        return bool(self.settings.value("autostart", False, type=bool))

    def set_autostart(self, enabled: bool) -> bool:
        """Persists the preference and applies the OS hook.

        Returns True if the OS-level autostart configuration succeeded.
        """
        self.settings.setValue("autostart", enabled)
        return self._apply_os_autostart(enabled)

    def _apply_os_autostart(self, enable: bool) -> bool:
        """Handles the native OS hooks for launching at startup."""
        # Get the absolute path to how this app was launched
        exec_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

        if sys.platform == "win32":
            # If Windows write to the standard Run registry key
            run_key = r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"
            reg_settings = QSettings(run_key, QSettings.Format.NativeFormat)
            if enable:
                reg_settings.setValue("kpynotes", exec_path)
            else:
                reg_settings.remove("kpynotes")
            reg_settings.sync()
            if reg_settings.status() != QSettings.Status.NoError:
                logger.error("Failed to update the autostart registry key.")
                return False
            return True

        if sys.platform.startswith("linux"):
            # A path containing newlines could inject extra desktop-entry keys
            if any(c in exec_path for c in "\n\r"):
                logger.error(
                    "Refusing to write autostart entry: path contains newline characters."
                )
                return False

            autostart_dir = os.path.expanduser("~/.config/autostart")
            desktop_file = os.path.join(autostart_dir, "kpynotes.desktop")

            if not enable:
                if os.path.exists(desktop_file):
                    try:
                        os.remove(desktop_file)
                    except OSError as e:
                        logger.error(
                            "Error removing autostart file '%s': %s", desktop_file, e
                        )
                        return False
                return True

            # In .desktop Exec keys, '%' starts a field code and must be
            # escaped as '%%' (e.g. paths like /opt/100%portable/...)
            escaped_exec = exec_path.replace("%", "%%")
            try:
                os.makedirs(autostart_dir, exist_ok=True)
                with open(desktop_file, "w", encoding="utf-8") as f:
                    f.write(
                        f"[Desktop Entry]\n"
                        f"Type=Application\n"
                        f"Name=KPynotes\n"
                        f"Exec={escaped_exec}\n"
                        f"Hidden=false\n"
                        f"NoDisplay=false\n"
                        f"X-GNOME-Autostart-enabled=true\n"
                    )
            except OSError as e:
                logger.error(
                    "Error writing autostart file '%s': %s", desktop_file, e
                )
                return False
            return True

        # Unsupported platform (e.g. macOS): nothing to hook into
        logger.warning("Autostart is not supported on '%s'.", sys.platform)
        return False
