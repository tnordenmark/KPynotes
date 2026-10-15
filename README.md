# KPynotes 📝

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Qt Version](https://img.shields.io/badge/Qt-6.10-green)](https://doc.qt.io/qt-6.10/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)](#)

**KPynotes** is a lightweight, cross-platform sticky note and scratchpad application designed specifically for **Linux (KDE Plasma)** and **Windows**. Built with **PySide6 (Qt 6.10)**, it provides desktop-native performance, seamless window manager integration, and modular cloud sync capabilities.

---

## ✨ Features

- **Native Window Management**: Uses OS-level window compositor delegation (`startSystemMove()`) for frameless window dragging on both KDE Plasma (Wayland/X11) and Windows.
- **OS-Compliant Storage**: Stores user data cleanly in standard system directories (`~/.local/share/kpynotes` on Linux, `%LOCALAPPDATA%\kpynotes` on Windows) via `QStandardPaths`.
- **System Tray Core**: Minimizes cleanly to the system tray with global actions to show, hide, or create notes instantly.
- **Dynamic Appearance**: Features live-switching light, dark, and system-matched themes across open notes.
- **Autostart Integration**: Built-in startup configuration using native Windows registry keys and Linux `.desktop` autostart entries.
- **Extensible Sync Backend**: Architecture ready for optional, asynchronous cloud sync providers (Google Drive, OneDrive).

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Poetry** (Python dependency manager)

If you do not have Poetry installed, install it via:

```bash
pip install poetry
```

---

### Installation & Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/tnordenmark/KPynotes.git
   cd KPynotes
   ```

2. **Install Dependencies**

   Install all required dependencies (including PySide6 and dev tools) into an isolated virtual environment managed by Poetry:

   ```bash
   poetry install
   ```

3. **Run the Application**

   Launch KPynotes directly through Poetry:

   ```bash
   poetry run python main.py
   ```

   Alternatively, use the installed console script:

   ```bash
   poetry run kpynotes
   ```

   Run the unit tests with:

   ```bash
   poetry run pytest
   ```

---

## 🛠️ Building Standalone Binaries

KPynotes can be compiled into single standalone executables using PyInstaller through Poetry.

### Windows (`.exe`)

Run the following inside PowerShell or Command Prompt:

```powershell
poetry run pyinstaller --noconsole --onefile --name "KPynotes" --icon "assets/icon.ico" main.py
```

The resulting executable will be available at `dist/KPynotes.exe`.

### Linux (Executable / AppImage)

Run the following in your Linux terminal:

```bash
poetry run pyinstaller --noconsole --onefile --name "KPynotes" main.py
```

The compiled binary will be placed inside `dist/KPynotes`.

---

## 📁 Project Structure

```text
KPynotes/
├── app/
│   ├── core/
│   │   ├── settings.py          # OS-native paths & autostart handling
│   │   ├── storage.py           # Atomic note persistence & storage manager
│   │   └── sync/                # Modular cloud sync engine interface
│   ├── ui/
│   │   ├── components/          # Reusable UI pieces (editor, title bar)
│   │   ├── main_window.py       # Frameless Sticky Note UI
│   │   └── settings_window.py   # App settings dialog
│   └── run.py                   # Tray app & application entry point
├── assets/                      # Application icons & resources
├── tests/                       # Pytest unit tests
├── main.py                      # Thin compatibility shim → app.run.main
├── pyproject.toml               # Poetry dependencies & metadata
└── README.md
```

---

## 📄 License

Distributed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See the [LICENSE](LICENSE) file for more details.

```text
KPynotes - Simple Sticky Notes for KDE & Windows
Copyright (C) 2026

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.