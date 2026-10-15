# Ensures the repository root is importable when running pytest,
# regardless of the working directory.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
