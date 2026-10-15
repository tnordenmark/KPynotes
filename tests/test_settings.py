# tests/test_settings.py
import os
import sys

import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from app.core.settings import AppSettings

LINUX_ONLY = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Linux .desktop autostart logic",
)


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    QCoreApplication.setOrganizationName("kpynotes-tests")
    QCoreApplication.setApplicationName("kpynotes-tests")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    return app


@pytest.fixture
def app_settings(qapp, tmp_path, monkeypatch):
    # Isolate QSettings in a per-test ini file
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )
    # Isolate autostart side effects (~/.config/autostart resolves under HOME)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setattr(sys, "executable", "/opt/KPynotes/kpynotes")
    return AppSettings()


def _autostart_file() -> str:
    return os.path.expanduser("~/.config/autostart/kpynotes.desktop")


def test_default_storage_path_created(app_settings, tmp_path):
    path = app_settings.get_storage_path()
    assert path.startswith(str(tmp_path))
    assert os.path.isdir(path)


def test_storage_path_round_trip(app_settings, tmp_path):
    custom = str(tmp_path / "custom-notes")
    app_settings.set_storage_path(custom)
    assert app_settings.get_storage_path() == custom
    assert os.path.isdir(custom)


def test_invalid_storage_path_falls_back_to_default(app_settings, tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("i am a file", encoding="utf-8")
    app_settings.set_storage_path(str(blocker / "sub"))
    fallback = app_settings.get_default_storage_path()
    assert app_settings.get_storage_path() == fallback
    assert os.path.isdir(fallback)


def test_theme_override_round_trip(app_settings):
    assert app_settings.get_theme_override() == "system"
    app_settings.set_theme_override("dark")
    assert app_settings.get_theme_override() == "dark"


@LINUX_ONLY
def test_autostart_enable_writes_desktop_file(app_settings):
    assert app_settings.set_autostart(True) is True
    assert app_settings.get_autostart() is True
    with open(_autostart_file(), encoding="utf-8") as f:
        content = f.read()
    assert "[Desktop Entry]" in content
    assert "Exec=" in content


@LINUX_ONLY
def test_autostart_disable_removes_desktop_file(app_settings):
    app_settings.set_autostart(True)
    assert app_settings.set_autostart(False) is True
    assert not os.path.exists(_autostart_file())


@LINUX_ONLY
def test_autostart_escapes_percent_in_exec_path(app_settings, monkeypatch):
    monkeypatch.setattr(sys, "executable", "/opt/100%portable/kpynotes")
    assert app_settings.set_autostart(True) is True
    with open(_autostart_file(), encoding="utf-8") as f:
        content = f.read()
    assert "100%%portable" in content


@LINUX_ONLY
def test_autostart_rejects_newline_paths(app_settings, monkeypatch):
    monkeypatch.setattr(sys, "executable", '/opt/evil"\nExec=rm -rf /')
    assert app_settings.set_autostart(True) is False
    assert not os.path.exists(_autostart_file())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows registry autostart")
def test_autostart_registry_round_trip(app_settings):
    assert app_settings.set_autostart(True) is True
    assert app_settings.get_autostart() is True
    assert app_settings.set_autostart(False) is True
