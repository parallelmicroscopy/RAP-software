# tests/conftest.py
# tests/conftest.py

import sys
from pathlib import Path

# 1) Prepend the real python/ folder so import vimba_rap3 works
ROOT = Path(__file__).parent.parent / "python"
sys.path.insert(0, str(ROOT))

# 2) Now it’s safe to import your module
import pytest
import vimba_rap3

# 3) Autouse fixture to disable the stdin‐reader thread
@pytest.fixture(autouse=True)
def disable_stdin_threads(monkeypatch):
    monkeypatch.setattr(vimba_rap3, "add_stdin_input", lambda iq, cq: None)
    yield

