# tests/conftest.py
import pytest
from PySide6.QtCore import QCoreApplication


@pytest.fixture(scope="session")
def qt_app():
    """Session-wide QCoreApplication for Qt-dependent tests (headless-safe)."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app
