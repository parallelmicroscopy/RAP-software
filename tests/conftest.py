# tests/conftest.py

import sys
from pathlib import Path

# Compute the absolute path to RAP/python, then insert it at the front of sys.path
ROOT = Path(__file__).parent.parent / "python"
sys.path.insert(0, str(ROOT))
