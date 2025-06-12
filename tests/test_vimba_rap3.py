import sys
import os
import shutil
import logging
import pytest
from pathlib import Path
from types import SimpleNamespace

import vimba_rap3
from vimba_rap3 import *
from vmbpy import *

# ——— Shared Dummy Classes ——— #

class DummyFrameIncomplete:
    """A frame whose status is never Complete."""
    def get_status(self):
        return FrameStatus.Incomplete

class DummyFrameDirect:
    """A Complete frame already in the opencv_display_format."""
    def __init__(self):
        self._fmt = opencv_display_format

    def get_status(self):
        return FrameStatus.Complete

    def get_pixel_format(self):
        return self._fmt

    def convert_pixel_format(self, fmt):
        # Should never be called in this case
        raise AssertionError("convert_pixel_format should not be used for direct format")

    def as_opencv_image(self):
        return "raw_image"

class DummyFrameConvert:
    def __init__(self, converted):
        # ORIGINAL FORMAT ≠ opencv_display_format, so the handler will convert:
        self._orig_fmt   = PixelFormat.Mono8
        self._converted  = converted

    def get_status(self):
        return FrameStatus.Complete

    def get_pixel_format(self):
        return self._orig_fmt

    def convert_pixel_format(self, fmt):
        assert fmt == opencv_display_format
        return self._converted

    def as_opencv_image(self):
        return "converted_image"


class DummyCamQueue:
    """A camera stub that records frames re-queued by Handler."""
    def __init__(self):
        self.queued = []

    def queue_frame(self, frame):
        self.queued.append(frame)

class DummyFormat:
    def __init__(self, convertible):
        self._conv = convertible
    def get_convertible_formats(self):
        return self._conv
    def __repr__(self):
        return f"<DummyFormat {self._conv!r}>"

class DummyFeature:
    def __init__(self, fail=None):
        self.calls = []
        self._fail = fail
    def set(self, value):
        if self._fail:
            raise self._fail
        self.calls.append(value)

class DummyGVSP:
    def __init__(self, done_after=1):
        self.run_calls = 0
        self.done_after = done_after
    def run(self):
        self.run_calls += 1
    def is_done(self):
        return self.run_calls >= self.done_after

class DummyStream:
    def __init__(self, gvsp):
        self.GVSPAdjustPacketSize = gvsp

class DummyCam2:
    def __init__(self, exp_fail=None, wb_fail=None, gvsp_done=1, bad_stream=False):
        self.ExposureAuto     = DummyFeature(exp_fail)
        self.BalanceWhiteAuto = DummyFeature(wb_fail)
        gvsp = DummyGVSP(done_after=gvsp_done)
        self._streams = [] if bad_stream else [DummyStream(gvsp)]
        self.entered = False
        self.exited  = False
    def __enter__(self):
        self.entered = True
        return self
    def __exit__(self, *args):
        self.exited = True
        return False
    def get_streams(self):
        return self._streams

class FakeVmbSystem:
    def __init__(self, by_id=None, by_id_exc=None, all_cams=None):
        self._by_id     = by_id
        self._by_id_exc = by_id_exc
        self._all       = all_cams or []
    def __enter__(self):
        return SimpleNamespace(
            get_camera_by_id = self._get_by_id,
            get_all_cameras  = lambda: list(self._all)
        )
    def __exit__(self, *args):
        return False
    def _get_by_id(self, cid):
        if self._by_id_exc:
            raise self._by_id_exc
        return self._by_id

# ——— Fixtures ——— #

@pytest.fixture(autouse=True)
def reset_current_save_dir():
    vimba_rap3.currentSaveDirectory = None
    yield
    vimba_rap3.currentSaveDirectory = None

@pytest.fixture(autouse=True)
def reset_logging():
    logging.getLogger().handlers.clear()
    logging.basicConfig(level=logging.DEBUG)
    yield

# ——— create_folder tests ——— #

def test_create_folder_makes_directory(tmp_path):
    new_folder = tmp_path / "subdir_A"
    assert not new_folder.exists()
    create_folder(str(new_folder))
    assert new_folder.exists() and new_folder.is_dir()
    shutil.rmtree(new_folder)


def test_create_folder_when_target_already_exists(tmp_path):
    base = tmp_path / "mydir"
    base.mkdir()
    assert base.exists() and base.is_dir()

    create_folder(str(base))
    expected1 = tmp_path / "mydir1"
    assert expected1.exists() and expected1.is_dir()
    assert vimba_rap3.currentSaveDirectory == expected1.as_posix()

    create_folder(str(base))
    expected2 = tmp_path / "mydir2"
    assert expected2.exists() and expected2.is_dir()
    assert vimba_rap3.currentSaveDirectory == expected2.as_posix()

    assert base.exists() and base.is_dir()
    assert set(os.listdir(tmp_path)) == {"mydir", "mydir1", "mydir2"}

# ——— abort() tests ——— #

def test_abort_logs_error_and_exits(caplog, capsys):
    caplog.set_level(logging.ERROR)
    reason = "Something went terribly wrong"
    code = 5

    with pytest.raises(SystemExit) as exc:
        abort(reason, return_code=code, usage=False)
    assert exc.value.code == code

    # log
    assert any(
        rec.levelno == logging.ERROR and reason in rec.getMessage()
        for rec in caplog.records
    ), f"No ERROR log: {caplog.text}"

    # print
    out = capsys.readouterr().out
    assert f".py. {reason}" in out

# ——— parse_args() tests ——— #

def test_parse_args_no_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["script"])
    assert parse_args() == (1, 1, 1)

def test_parse_args_one_non_help_arg(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["script", "foo"])
    assert parse_args() == (1, 1, 1)

def test_parse_args_help_flag(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["script", "-h"])
    with pytest.raises(SystemExit) as exc:
        parse_args()
    assert exc.value.code == 0
    assert "Usage:" in capsys.readouterr().out

def test_parse_args_two_valid_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["script", "5", "10"])
    assert parse_args() == (5, 10, 0)

def test_parse_args_too_many_args(monkeypatch, capsys, caplog):
    caplog.set_level(logging.ERROR)
    monkeypatch.setattr(sys, "argv", ["script", "1", "2", "3"])
    with pytest.raises(SystemExit) as exc:
        parse_args()
    assert exc.value.code == 2

    out = capsys.readouterr().out
    assert ".py. Invalid number of arguments. Abort." in out
    assert "Usage:" in out
    assert any(
        rec.levelno == logging.ERROR and "Invalid number of arguments. Abort." in rec.getMessage()
        for rec in caplog.records
    )

# ——— get_camera() tests ——— #

def test_get_camera_with_valid_id(monkeypatch):
    fake = object()
    sysobj = FakeVmbSystem(by_id=fake)
    monkeypatch.setattr(vimba_rap3.VmbSystem, "get_instance", classmethod(lambda cls: sysobj))
    assert get_camera("ID") is fake

def test_get_camera_by_id_error(monkeypatch, caplog, capsys):
    sysobj = FakeVmbSystem(by_id_exc=VmbCameraError("oops"))
    monkeypatch.setattr(vimba_rap3.VmbSystem, "get_instance", classmethod(lambda cls: sysobj))
    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        get_camera("BAD")
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Failed to access Camera 'BAD'. Abort." in out
    assert any("Failed to access Camera 'BAD'. Abort." in r.getMessage() for r in caplog.records)

def test_get_camera_no_id_and_no_cameras(monkeypatch, caplog, capsys):
    sysobj = FakeVmbSystem(all_cams=[])
    monkeypatch.setattr(vimba_rap3.VmbSystem, "get_instance", classmethod(lambda cls: sysobj))
    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        get_camera(None)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "No Cameras accessible. Abort." in out
    assert any("No Cameras accessible. Abort." in r.getMessage() for r in caplog.records)

def test_get_camera_no_id_returns_first(monkeypatch):
    a, b = object(), object()
    sysobj = FakeVmbSystem(all_cams=[a, b])
    monkeypatch.setattr(vimba_rap3.VmbSystem, "get_instance", classmethod(lambda cls: sysobj))
    assert get_camera(None) is a

# ——— load_camera_settings() test ——— #

def test_load_camera_settings_invokes_load_settings():
    class DummyCam:
        def __init__(self):
            self.calls = []
        def load_settings(self, file, ptype):
            self.calls.append((file, ptype))

    dummy = DummyCam()
    cfg = "config.xml"
    load_camera_settings(dummy, cfg)
    assert len(dummy.calls) == 1
    file_arg, persist_arg = dummy.calls[0]
    assert file_arg == cfg
    assert persist_arg == PersistType.All

# ——— setup_camera() tests ——— #

def test_setup_camera_happy_path():
    cam = DummyCam2()
    setup_camera(cam)
    assert cam.entered and cam.exited
    assert cam.ExposureAuto.calls == ['Continuous']
    assert cam.BalanceWhiteAuto.calls == ['Continuous']
    streams = cam.get_streams()
    assert len(streams) == 1
    gvsp = streams[0].GVSPAdjustPacketSize
    assert gvsp.run_calls == 2

def test_setup_camera_feature_exceptions_are_ignored():
    from vmbpy import VmbFeatureError
    cam = DummyCam2(exp_fail=VmbFeatureError("e"), wb_fail=VmbFeatureError("f"))
    setup_camera(cam)
    assert cam.entered and cam.exited
    assert cam.ExposureAuto.calls == []
    assert cam.BalanceWhiteAuto.calls == []
    streams = cam.get_streams()
    assert streams and streams[0].GVSPAdjustPacketSize.run_calls == 2

def test_setup_camera_missing_stream_feature_is_ignored():
    cam = DummyCam2(bad_stream=True)
    setup_camera(cam)
    assert cam.entered and cam.exited
    assert cam.ExposureAuto.calls == ['Continuous']
    assert cam.BalanceWhiteAuto.calls == ['Continuous']
