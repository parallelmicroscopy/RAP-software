# tests/conftest.py
# tests/conftest.py

import sys
from pathlib import Path

# 1) Prepend the real python/ folder so import vimba_rap3 works
ROOT = Path(__file__).parents[2] / "python"
sys.path.insert(0, str(ROOT))

import sys
from types import ModuleType

# ─── 0) Stub out cv2 entirely ───
# Create a fake cv2 module that provides exactly the names
# vimba_rap3 will ever touch (and no GUI code).
_fake_cv2 = ModuleType("cv2")
_fake_cv2.namedWindow    = lambda *args, **kwargs: None
_fake_cv2.moveWindow     = lambda *args, **kwargs: None
_fake_cv2.imshow         = lambda *args, **kwargs: None
_fake_cv2.resizeWindow   = lambda *args, **kwargs: None
_fake_cv2.WINDOW_NORMAL  = 0
# (if you see any more cv2.* names used in your code, stub them here)
sys.modules["cv2"] = _fake_cv2

# ─── 1) Now import pytest and your module ───
import pytest
import vimba_rap3

# ─── 2) Autouse fixture to stub out stdin‐threads ───
class DummyThread:
    def __init__(self, *args, **kwargs): pass
    @property
    def daemon(self): return True
    @daemon.setter
    def daemon(self, v): pass
    def start(self): pass

@pytest.fixture(autouse=True)
def disable_backgrounds(monkeypatch):
    # 2a) replace threading.Thread inside vimba_rap3
    monkeypatch.setattr(vimba_rap3.threading, "Thread", DummyThread)
    # 2b) replace the stdin‐reader so even if started it does nothing
    monkeypatch.setattr(vimba_rap3, "add_stdin_input", lambda iq, cq: None)
    yield
