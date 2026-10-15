# main.py
"""Backwards-compatible entry point; the application lives in app/run.py."""

import sys

from app.run import main

if __name__ == "__main__":
    sys.exit(main())
