import sys
import os
import shutil
import logging
import pytest
from pathlib import Path
from types import SimpleNamespace
import logging
import vimba_rap3
from vimba_rap3 import *
from vmbpy import *
import types
from queue import Queue
import queue

# ——— Shared Dummy Classes ——— #



# A minimal stub for cv2 to record calls
class DummyCV2:
    WINDOW_NORMAL = 100  # arbitrary placeholder

    def __init__(self):
        self.named_calls = []  # tuples of (window_title, flag)
        self.move_calls  = []  # tuples of (window_title, x, y)

    def namedWindow(self, title, flag):
        self.named_calls.append((title, flag))

    def moveWindow(self, title, x, y):
        self.move_calls.append((title, x, y))

class DummyCV2Show(DummyCV2):
    def __init__(self):
        super().__init__()
        self.shown = []  # record (title, image) tuples

    def imshow(self, title, img):
        self.shown.append((title, img))

class FakeStdin:
    def __init__(self, data):
        self.data = list(data)
    def read(self, n):
        if self.data:
            return self.data.pop(0)
        raise EOFError

class DummyCam:
    pass

class DummyCV:
    def __init__(self):
        self.destroy_calls = 0
        self.resize_calls  = []
        self.move_calls    = []
    def destroyAllWindows(self):
        self.destroy_calls += 1
    def resizeWindow(self, title, w, h):
        self.resize_calls.append((title, w, h))
    def moveWindow(self, title, x, y):
        self.move_calls.append((title, x, y))

class DummyCamExposure:
    def __init__(self):
        self.ExposureAuto = SimpleNamespace(set_calls=[])
        self.ExposureTime = SimpleNamespace(set_calls=[])
    def _record_auto(self, val):
        self.ExposureAuto.set_calls.append(val)
    def _record_time(self, val):
        self.ExposureTime.set_calls.append(val)

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
def reset_maybesaveimage_globals():
    # Ensure a clean slate before each test
    vimba_rap3.SAVETOGGLE   = 0
    vimba_rap3.savedframes  = 0
    vimba_rap3.save_max     = 3
    yield

@pytest.fixture(autouse=True)
def reset_js_input_flag():
    import vimba_rap3
    vimba_rap3.js_input_started = False
    yield
    vimba_rap3.js_input_started = False
@pytest.fixture(autouse=True)
def reset_js_globals(monkeypatch):
    vimba_rap3.cancel_main_loop = 0
    vimba_rap3.cancel_save      = 0
    vimba_rap3.mode             = -1
    vimba_rap3.number_of_wells  = 0
    vimba_rap3.savedframes      = 0
    vimba_rap3.save_max         = 0
    vimba_rap3.SAVETOGGLE       = 0
    yield

@pytest.fixture(autouse=True)
def reset_processsave_globals():
    # Ensure a clean slate for each test
    vimba_rap3.mode        = 99
    vimba_rap3.savedframes = 42
    vimba_rap3.save_max    = 100
    yield

@pytest.fixture(autouse=True)
def reset_processcommand_globals(monkeypatch):
    # Always start tests with a clean slate
    vimba_rap3.number_of_wells = 2
    vimba_rap3.screenres       = [1000, 1000]
    vimba_rap3.alliedxy        = [100, 200]
    yield

@pytest.fixture(autouse=True)
def stub_dummy_cam_methods(monkeypatch):
    """Attach .set() to our DummyCamExposure components."""
    def attach(cam):
        cam.ExposureAuto.set = cam._record_auto
        cam.ExposureTime.set = cam._record_time
        return cam
    return attach

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

# --setup_pixel_format() tests --#

def test_setup_pixel_format_direct(monkeypatch):
    """  
    If opencv_display_format is directly supported, it should be chosen.    """    # Make intersect_pixel_formats return all formats unfiltered
    monkeypatch.setattr(vimba_rap3, 'intersect_pixel_formats',
                        lambda fmts, subset: list(fmts))

    calls = []
    class Cam:
        def get_pixel_formats(self):
            return [opencv_display_format]
        def set_pixel_format(self, fmt):
            calls.append(fmt)

    cam = Cam()
    setup_pixel_format(cam)
    assert calls == [opencv_display_format]

def test_setup_pixel_format_convertible_color(monkeypatch):
    """
    If no direct support, but a color format is convertible → pick that.    """
    monkeypatch.setattr(vimba_rap3, 'intersect_pixel_formats', lambda fmts, subset: list(fmts))

    fmt1 = DummyFormat([opencv_display_format])   # convertible color
    fmt2 = DummyFormat([])                        # not convertible

    calls = []
    class Cam:
        def get_pixel_formats(self):
            return [fmt1, fmt2]
        def set_pixel_format(self, fmt):
            calls.append(fmt)

    cam = Cam()
    setup_pixel_format(cam)
    assert calls == [fmt1]

def test_setup_pixel_format_convertible_mono(monkeypatch):
    """  
    If neither direct nor color‐convertible, but a mono format is convertible → pick that.    """    # fake_intersect returns [] on first (color) call, then raw fmts on second (mono) call
    call_sequence = []
    def fake_intersect(fmts, subset):
        if not call_sequence:
            call_sequence.append(True)
            return []
        return list(fmts)

    monkeypatch.setattr(vimba_rap3, 'intersect_pixel_formats', fake_intersect)

    fmt = DummyFormat([opencv_display_format])
    calls = []
    class Cam:
        def get_pixel_formats(self):
            return [fmt]
        def set_pixel_format(self, fmt):
            calls.append(fmt)

    cam = Cam()
    setup_pixel_format(cam)
    assert calls == [fmt]

def test_setup_pixel_format_no_compatible(monkeypatch, caplog, capsys):
    """  
    If there’s no direct support and no convertible formats → abort.    """    # force both color and mono intersects to return empty
    monkeypatch.setattr(vimba_rap3, 'intersect_pixel_formats',
                        lambda fmts, subset: [])

    class Cam:
        def get_pixel_formats(self):
            return []

    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as exc:
        setup_pixel_format(Cam())
    assert exc.value.code == 1

    out = capsys.readouterr().out
    assert "Camera does not support an OpenCV compatible format. Abort." in out

    assert any(
        rec.levelno == logging.ERROR and
        "Camera does not support an OpenCV compatible format. Abort." in rec.getMessage()
        for rec in caplog.records
    )

# --class handler tests-- #

def test_handler_skips_incomplete_frame():
    """
    If frame.get_status() != Complete, Handler should do nothing:    no increment of frnum, no queue put, no cam.queue_frame().    """
    handler = Handler(cv2=None)
    cam = DummyCamQueue()
    frame = DummyFrameIncomplete()

    handler(cam, None, frame)

    # frnum stays at 0
    assert handler.frnum == 0
    # nothing was queued for display
    assert handler.display_queue.empty()
    # camera never re-queued the frame
    assert cam.queued == []

def test_handler_puts_direct_format():
    """
    Complete frames already in opencv_display_format should be    enqueued directly and re-queued back to the camera.    """
    handler = Handler(cv2=None)
    cam = DummyCamQueue()
    frame = DummyFrameDirect()

    handler(cam, None, frame)

    # Handler should have incremented its frame counter
    assert handler.frnum == 1

    (img, queued_fn), num = handler.get_image()
    assert img == "raw_image"
    assert queued_fn == 1
    assert num == 1

    # and the original frame object is returned to the camera
    assert cam.queued == [frame]

def test_handler_converts_format():
    """
    If the frame isn’t already in opencv_display_format, Handler    should call frame.convert_pixel_format(...) then enqueue.    """
    converted_frame = DummyFrameDirect()  # this will be returned by convert_pixel_format
    frame = DummyFrameConvert(converted_frame)

    handler = Handler(cv2=None)
    cam = DummyCamQueue()

    handler(cam, None, frame)

    # frnum was incremented
    assert handler.frnum == 1

    # get_image should yield the converted image
    (img, queued_fn), num = handler.get_image()
    assert img == "converted_image"
    assert queued_fn == 1
    assert num == 1

    # but the camera gets the *original* frame re-queued
    assert cam.queued == [frame]

def test_handler_prints_queue_full_and_status_message(capsys):
    """
    When verbose=1 and the internal queue is full, Handler should print    'queue full'. Also every 500th frame prints a status line starting with '.py.'.    """
    handler = Handler(cv2=None)
    handler.verbose = 1

    # stub out display_queue to simulate full() always True
    handler.display_queue = SimpleNamespace(
        full=lambda: True,
        put=lambda item, block: None
    )

    # Create a frame that is complete and in direct format
    frame = DummyFrameDirect()
    cam = DummyCamQueue()

    # First call: frnum starts at 0, so frnum%500 == 0 → status message printed
    handler(cam, None, frame)

    out = capsys.readouterr().out
    assert "queue full" in out
    assert ".py." in out and "acquired with" in out

# -- parsefile() tests -- #
def test_parsefile_sets_auto_and_time(tmp_path, stub_dummy_cam_methods, monkeypatch):
    # 1) Write a RAPcommand.txt in a fresh tmp dir
    monkeypatch.chdir(tmp_path)
    (tmp_path / "RAPcommand.txt").write_text("12345\n")

    # 2) Create our dummy and hook in the .set() recorders
    cam = stub_dummy_cam_methods(DummyCamExposure())

    # 3) Call parsefile → should print and then set ExposureAuto to 'Off', ExposureTime to 12345
    parsefile(cam)

    # 4) Verify
    assert cam.ExposureAuto.set_calls == ['Off']
    assert cam.ExposureTime.set_calls == [12345]

# ——— makepanels() tests ——— #

@pytest.mark.parametrize("xdim, ydim, expected", [
    (1, 1, [[0]]),
    (2, 2, [[0, 1],
            [0, 1]]),
    (3, 1, [[0, 1, 2]]),
    (1, 3, [[0],
            [0],
            [0]]),
    (4, 3, [[0, 1, 2, 3],
            [0, 1, 2, 3],
            [0, 1, 2, 3]]),
])
def test_makepanels_various_sizes(xdim, ydim, expected):
    # reset any old data
    vimba_rap3.frame_array = None

    # call under test
    vimba_rap3.makepanels(xdim, ydim)

    # after calling, frame_array must match the expected 2D grid
    assert vimba_rap3.frame_array == expected

#-- parsecommand() tests --#

@pytest.mark.parametrize("s, cmd, expected", [
    # pure‐digits → parsed
    ("wells=123",       "wells=",  (0,   123)),
    ("foo wells=321",   "wells=",  (4,   321)),
    ("mode=  15",       "mode=",   (0,    15)),
    # keyword not present → both -1
    ("random text",     "wells=",  (-1,  -1)),
])
def test_parsecommand_behavior(s, cmd, expected):
    assert parsecommand(s, cmd) == expected

#-- processcommand() tests --#


def test_processcommand_wells_changed_triggers_destroy(tmp_path):
    cv = DummyCV()
    # starting number_of_wells is 2
    assert vimba_rap3.number_of_wells == 2

    # call with wells=5 → should update global and call destroy
    vimba_rap3.processcommand(cv, "wells=5")
    assert vimba_rap3.number_of_wells == 5
    assert cv.destroy_calls == 1

def test_processcommand_wells_same_does_nothing():
    cv = DummyCV()
    # set wells to 3
    vimba_rap3.number_of_wells = 3

    # call again with the same value
    vimba_rap3.processcommand(cv, "wells=3")
    # no change, no destroy
    assert vimba_rap3.number_of_wells == 3
    assert cv.destroy_calls == 0

def test_processcommand_tile_resizes_and_moves_windows():
    cv = DummyCV()

    # ensure number_of_wells > 0
    vimba_rap3.number_of_wells = 3
    # alliedxy = [100,200], screenres = [1000,1000] (from fixture)

    # now issue tile=2 → should call resize/move 3×
    vimba_rap3.processcommand(cv, "tile=2")

    # exactly one resize + one move per well:
    assert len(cv.resize_calls) == 3
    assert len(cv.move_calls)   == 3

    # each resize call got (title, width=2, height=int(200/ (100/2) )==4)
    # and each move call got x positions 0,2,4 and y=0
    for i, ((title_r, w, h), (title_m, x, y)) in enumerate(zip(cv.resize_calls, cv.move_calls)):
        # title_r and title_m should match windowtitle.format(i)
        expected_title = vimba_rap3.windowtitle.format(i)
        assert title_r == expected_title
        assert title_m == expected_title

        assert w == 2
        assert h == int(vimba_rap3.alliedxy[1] / (vimba_rap3.alliedxy[0] / 2))
        # x positions should step by w each time; y stays 0 because screenres is big
        assert x == i * w
        assert y == 0

def test_processcommand_no_match_does_nothing():
    cv = DummyCV()
    # neither "wells=" nor "tile=" in the string
    vimba_rap3.processcommand(cv, "foo=1")
    # no side‐effects at all
    assert cv.destroy_calls == 0
    assert cv.resize_calls  == []
    assert cv.move_calls    == []

#-- processsave() tests --#

@pytest.mark.parametrize("cmd_str, expected_max", [
    ("save=10",               10),
    ("save=  20  ",           20),   # trims whitespace
    ("prefix=ignored=30",     30),   # rfind picks last “=”
    ("save=0",                 0),
    ("save=-5",               -5),   # negative allowed by int()
])
def test_processsave_parses_and_sets_globals(cmd_str, expected_max):
    """
    processsave should set:
      mode       → 0
      savedframes→ 0
      save_max   → integer parsed after last '='
    """
    vimba_rap3.processsave(None, cmd_str)
    assert vimba_rap3.mode        == 0
    assert vimba_rap3.savedframes == 0
    assert vimba_rap3.save_max    == expected_max

#-- array_in_array() tests --#

def test_array_in_array_basic_placement_only_arrays():
    # a1 is a 5×5×3 zero‐array
    a1 = np.zeros((5, 5, 3), dtype=int)
    # a2 is a 2×3×3 ramp
    a2 = np.arange(2*3*3).reshape((2, 3, 3))

    # place it at offset (1,2)
    array_in_array(a1, a2, 1, 2)

    # the region [1:3,2:5,:] must exactly match a2
    assert np.array_equal(a1[1:1+2, 2:2+3, :], a2)

    # everything else should remain zero
    mask = np.ones_like(a1, dtype=bool)
    mask[1:3, 2:5, :] = False
    assert np.all(a1[mask] == 0)

#-- checkkeypress() tests --#

@pytest.mark.parametrize("key, expect_destroy, expect_parse, expect_ret", [
    (13,  True,  False, -1),   # Enter
    (ord("r"), False, True,   0),   # 'r'
    (42,  False, False,  0),   # anything else
])
def test_checkkeypress_param(key, expect_destroy, expect_parse, expect_ret, monkeypatch):
    # 1) ensure there's a module‐level cam for parsefile(cam) to pick up
    monkeypatch.setattr(vimba_rap3, "cam", "MY_CAMERA", raising=False)

    # 2) stub out parsefile so it just records calls
    parse_calls = []
    monkeypatch.setattr(vimba_rap3, "parsefile", lambda cam_arg: parse_calls.append(cam_arg))

    # 3) build a tiny fake cv
    calls = []
    cv = types.SimpleNamespace(
        waitKey=lambda t: key,
        destroyAllWindows=lambda: calls.append("destroy")
    )

    # 4) invoke
    ret = checkkeypress(cv, None)

    # 5) assertions
    assert ret == expect_ret
    assert (len(calls) > 0) == expect_destroy
    assert (parse_calls == ["MY_CAMERA"]) == expect_parse

# -- start_save() tests --#

def test_start_save_resets_and_toggles_and_changes_dir_and_logs(monkeypatch, caplog, tmp_path):
    # 1) Prepare: push savedframes to a non-zero, and SAVETOGGLE off
    vimba_rap3.savedframes = 7
    vimba_rap3.SAVETOGGLE   = 0

    # 2) Capture INFO logs
    caplog.set_level(logging.INFO)

    # 3) Stub os.chdir so it doesn't actually move us around
    called = []
    monkeypatch.setattr(os, "chdir", lambda p: called.append(p))

    # 4) Call under test
    folder = str(tmp_path / "my_output_folder")
    vimba_rap3.start_save(folder)

    # 5) Assert savedframes was reset
    assert vimba_rap3.savedframes == 0

    # 6) Assert SAVETOGGLE was flipped on
    assert vimba_rap3.SAVETOGGLE == 1

    # 7) Assert os.chdir was called exactly once with our folder
    assert called == [folder]

    # 8) Assert a log record was emitted mentioning our folder
    assert any(
        "startsave called, with {}".format(folder) in rec.getMessage()
        for rec in caplog.records
    )

# -- stop_save() tests -- #

def test_stop_save_turns_off_savetoggle_and_logs(caplog):
    # 1) Arrange: turn SAVETOGGLE on
    vimba_rap3.SAVETOGGLE = 1

    # 2) Capture INFO‐level logs
    caplog.set_level(logging.INFO)

    # 3) Act
    vimba_rap3.stop_save()

    # 4) Assert SAVETOGGLE was reset to 0
    assert vimba_rap3.SAVETOGGLE == 0

    # 5) Assert an INFO‐level record “stopsave called” was emitted
    assert any(
        "stopsave called" in rec.getMessage() and rec.levelno == logging.INFO
        for rec in caplog.records
    )

# -- process_js_command() tests -- #

# ——— Helper to capture stdout and logs ——— #
def capture(monkeypatch):
    out = []
    monkeypatch.setattr(sys, "stdout", type("O", (), {"write": lambda _self, s: out.append(s), "flush": lambda _self: None})())
    return out

# ——— 1) loadcamerasettings / loadcamera ——— #
def test_process_js_loadcamera_requires_path(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(vimba_rap3, "load_camera_settings", lambda cam, p: called.append(p))
    process_js_command("loadcamera", DummyCam())
    out = capsys.readouterr().out
    assert "Error - require a path to an xml file" in out
    assert called == []

def test_process_js_loadcamera_ok(monkeypatch, caplog, capsys):
    called = []
    monkeypatch.setattr(vimba_rap3, "load_camera_settings", lambda cam, p: called.append(p))
    caplog.set_level(logging.INFO)
    process_js_command("loadcamerasettings,  foo.xml  ", DummyCam())
    assert called == ["foo.xml"]
    out = capsys.readouterr().out
    assert ".py. processing command loadcamerasettings" in out
    assert any("process_js_command understood = loadcamerasettings" in r.getMessage() for r in caplog.records)

# ——— 2) trigger ——— #
def test_process_js_trigger_true_false_and_invalid(monkeypatch, capsys, caplog):
    called = []
    monkeypatch.setattr(vimba_rap3, "load_camera_settings", lambda cam, p: called.append(p))
    # true
    process_js_command("trigger, true", DummyCam())
    assert called[-1] == vimba_rap3.defaultTriggerConfigfile
    # false
    process_js_command("trigger,0", DummyCam())
    assert called[-1] == vimba_rap3.defaultFreerunConfigfile
    # invalid
    process_js_command("trigger, maybe", DummyCam())
    out = capsys.readouterr().out
    assert "Error - true/false argument not parsed" in out

# ——— 3) framerate, gain, exposure ——— #
def test_process_js_framerate_gain_exposure(monkeypatch):
    fr, gn, ex = [], [], []
    monkeypatch.setattr(vimba_rap3, "set_framerate", lambda c,v: fr.append(v))
    monkeypatch.setattr(vimba_rap3, "set_gain",      lambda c,v: gn.append(v))
    monkeypatch.setattr(vimba_rap3, "set_exposure",  lambda c,v: ex.append(v))

    cam = DummyCam()
    process_js_command("framerate, 30", cam)
    assert fr[-1] == 30.0

    process_js_command("gain, -5", cam)
    assert gn[-1] == 0.0
    process_js_command("gain, 50", cam)
    assert gn[-1] == 45.0

    process_js_command("exposure, 10", cam)
    assert ex[-1] == 20.0
    process_js_command("exposure, 2000000", cam)
    assert ex[-1] == 1000000.0

# ——— 4) wells, jmessage, quit ——— #
def test_process_js_wells_jmessage_quit(monkeypatch, capsys):
    # wells clamp
    process_js_command("wells, 0", None)
    assert vimba_rap3.number_of_wells == 1
    process_js_command("wells, 30", None)
    assert vimba_rap3.number_of_wells == 24

    # jmessage
    _ = capsys.readouterr()
    process_js_command("jmessage", None)
    out = capsys.readouterr().out
    assert "Generic message received" in out

    # quit
    process_js_command("quit", None)
    assert vimba_rap3.cancel_main_loop == 1

# ——— 5) startsave, stopsave ——— #
def test_process_js_startstop_save(monkeypatch):
    ss, sp = [], []
    # stub out create_folder/start_save/stop_save
    monkeypatch.setattr(vimba_rap3, "create_folder", lambda p: setattr(vimba_rap3, "currentSaveDirectory", "/tmp/X"))
    monkeypatch.setattr(vimba_rap3, "start_save", lambda p: ss.append(p))
    monkeypatch.setattr(vimba_rap3, "stop_save",  lambda : sp.append(True))

    # startsave no-arg → uses currentSaveDirectory
    process_js_command("startsave", DummyCam())
    assert ss[-1] == vimba_rap3.currentSaveDirectory
    # startsave with arg
    process_js_command("startsave, custom", DummyCam())
    assert ss[-1] == "custom"
    # stopsave
    process_js_command("stopsave", DummyCam())
    assert sp == [True]

# ——— 6) free, mode, savedir, unknown ——— #
def test_process_js_free_mode_savedir_unknown(monkeypatch, caplog, capsys):
    lc = []
    monkeypatch.setattr(vimba_rap3, "load_camera_settings", lambda c,p: lc.append(p))
    caplog.set_level(logging.INFO)

    process_js_command("free", None)
    assert lc[-1] == vimba_rap3.defaultFreerunConfigfile

    process_js_command("mode,2", None)
    assert vimba_rap3.mode == 2

    process_js_command("savedir, /var/tmp", None)
    assert any("/var/tmp" in rec.getMessage() for rec in caplog.records)

    # unknown
    _ = capsys.readouterr()
    process_js_command("foo", None)
    out = capsys.readouterr().out
    assert "command foo not understood" in out

# -- add_stdin_input() tests -- #

def test_add_stdin_input_single_command(monkeypatch):
    """
    Input "<hello>" should queue "hello" as one command, and leave the input queue empty.
    """
    stdin = FakeStdin("<hello>")
    monkeypatch.setattr(sys, "stdin", stdin)

    iq, cq = Queue(), Queue()
    with pytest.raises(EOFError):
        add_stdin_input(iq, cq)  # It will raise EOFError once FakeStdin is exhausted

    # The command queue should have exactly one entry "hello"
    assert cq.get_nowait() == "hello"
    # The raw input-queue should be empty
    assert iq.empty()

def test_add_stdin_input_partial_no_close(monkeypatch):
    """
    Input without a closing '>' should never emit a command, but all non-'<' chars go into the input queue.
    """
    stdin = FakeStdin("abc<foo")
    monkeypatch.setattr(sys, "stdin", stdin)

    iq, cq = Queue(), Queue()
    with pytest.raises(EOFError):
        add_stdin_input(iq, cq)

    # No complete command was emitted
    assert cq.empty()
    # Every character except the '<' was pushed into iq, and none removed
    assert list(iq.queue) == ["a", "b", "c", "f", "o", "o"]

def test_add_stdin_input_multiple_commands(monkeypatch):
    """
    Multiple "<a><b>" sequences should produce two commands "a" and "b", and leave iq empty.
    """
    stdin = FakeStdin("<a><b>")
    monkeypatch.setattr(sys, "stdin", stdin)

    iq, cq = Queue(), Queue()
    with pytest.raises(EOFError):
        add_stdin_input(iq, cq)

    # We should have seen exactly ["a", "b"] in the command queue
    assert list(cq.queue) == ["a", "b"]
    # And no leftover characters in the input queue
    assert iq.empty()

# -- maybesaveimage() tests -- #

def test_maybesaveimage_does_nothing_when_toggle_off(tmp_path):
    """If SAVETOGGLE==0, nothing should be written and counters untouched."""
    calls = []
    dummy_cv2 = type("CV", (), {"imwrite": lambda self, fn, img: calls.append((fn, img))})()
    vimba_rap3.SAVETOGGLE = 0
    vimba_rap3.savedframes = 5
    vimba_rap3.save_max    = 10

    # call with toggle off
    vimba_rap3.maybesaveimage(dummy_cv2, display="IMGDATA", num=7)

    # no write, no counter change, toggle stays off
    assert calls == []
    assert vimba_rap3.savedframes == 5
    assert vimba_rap3.SAVETOGGLE   == 0

def test_maybesaveimage_writes_and_increments_below_max(tmp_path):
    """With SAVETOGGLE==1 and savedframes+1 < save_max: write once, counter++, toggle stays on."""
    calls = []
    dummy_cv2 = type("CV", (), {"imwrite": lambda self, fn, img: calls.append((fn, img))})()
    vimba_rap3.SAVETOGGLE = 1
    vimba_rap3.savedframes = 0
    vimba_rap3.save_max    = 2

    # first save: 0→1 (<2)
    vimba_rap3.maybesaveimage(dummy_cv2, display="DATA1", num=0)
    assert calls == [("img000000000.tif", "DATA1")]
    assert vimba_rap3.savedframes == 1
    assert vimba_rap3.SAVETOGGLE   == 1

    # second save: 1→2 (==2, still < save_max? actually ==, toggle off only when >=)
    calls.clear()
    vimba_rap3.maybesaveimage(dummy_cv2, display="DATA2", num=1)
    assert calls == [("img000000001.tif", "DATA2")]
    assert vimba_rap3.savedframes == 2
    # now savedframes == save_max, so toggle should flip off
    assert vimba_rap3.SAVETOGGLE   == 0

# -- setupdisplaywindows() tests -- #

def test_setupdisplaywindows_24_grid():
    """
    When number_of_wells==24, we should get a 4×6 grid:
      - 24 calls to namedWindow with titles windowtitle.format(0..23)
      - 24 calls to moveWindow with x=j*280+1600, y=i*230
      - return list of those 24 titles in order
    """
    cv2 = DummyCV2()

    # Use a simple windowtitle so we can predict it
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("dummy", "unused")  # no-op, just to grab monkeypatch API
    # Actually patch the module globals directly:
    vimba_rap3.windowtitle = "W{}"
    # alliedxy not used in the 24-grid branch

    titles = setupdisplaywindows(cv2, 24)

    # Expect titles == ["W0", "W1", ..., "W23"]
    expected_titles = [f"W{i}" for i in range(24)]
    assert titles == expected_titles

    # Check namedWindow calls
    assert [t for t, _ in cv2.named_calls] == expected_titles
    # Check moveWindow geometry
    expected_moves = []
    c = 0
    for i in range(4):
        for j in range(6):
            expected_moves.append((f"W{c}", j*280 + 1600, i*230))
            c += 1
    assert cv2.move_calls == expected_moves

    monkeypatch.undo()


@pytest.mark.parametrize("n_wells,expected_titles,expected_moves", [
    # 1 well → one window at (0,0)
    (1, ["W0"], [("W0", 0, 0)]),
    # 3 wells → three windows at x offsets 0,624,0 (given alliedxy=[816,624])
    (3,
     ["W0", "W1", "W2"],
     [("W0", 0, 0),
      ("W1", 0, 624),
      ("W2", 0, 0)]),
])
def test_setupdisplaywindows_small(monkeypatch, n_wells, expected_titles, expected_moves):
    """
    For number_of_wells ≠ 24, uses the 2×2/3×2 tiling:
      xi = w%2, yi = (w//3)%2
      x = yi*alliedxy[0], y = xi*alliedxy[1]
    """
    cv2 = DummyCV2()
    # Make alliedxy predictable
    vimba_rap3.alliedxy = [816, 624]
    vimba_rap3.windowtitle = "W{}"

    titles = setupdisplaywindows(cv2, n_wells)
    assert titles == expected_titles
    # namedWindow calls in order
    assert [t for t, _ in cv2.named_calls] == expected_titles
    # moveWindow calls match expected
    assert cv2.move_calls == expected_moves

# -- maybeshowimage() tests -- #

@pytest.mark.parametrize("num,n_wells,expected_idx", [
    (5, 4, 1),    # 5 % 4 == 1
    (0, 4, 0),    # 0 % 4 == 0
    (7, 3, 1),    # 7 % 3 == 1
])
def test_maybeshowimage_wraps_and_displays_correct_window(num, n_wells, expected_idx):
    cv2 = DummyCV2Show()
    # pick a template that makes titles obvious
    vimba_rap3.windowtitle = "Win{}"

    vimba_rap3.maybeshowimage(cv2, display="FRAME", num=num, number_of_wells=n_wells)

    # should have exactly one imshow call with title Win{expected_idx}
    assert cv2.shown == [(f"Win{expected_idx}", "FRAME")]

# -- main() tests --#


# 1) Too many arguments → parse_args() will abort(code=2, usage=True)
def test_main_exits_on_too_many_args(monkeypatch, capsys):
    # Simulate: prog + three extra args
    monkeypatch.setattr(sys, "argv", ["prog", "1", "2", "3"])
    with pytest.raises(SystemExit) as exc:
        main()
        # parse_args should have called abort(return_code=2, usage=True)
    assert exc.value.code == 2

    out = capsys.readouterr().out
    # Usage should have been printed
    assert "Usage:" in out


# 2) Slave-mode == 0 → print preamble, then exit from stubbed camera immediately
def test_main_prints_preamble_when_slave_mode_zero(monkeypatch, capsys, tmp_path):
    # stub out the display routines so no real OpenCV windows ever appear
    monkeypatch.setattr(vimba_rap3, "setupdisplaywindows", lambda *args, **kwargs: [])
    monkeypatch.setattr(vimba_rap3, "maybeshowimage",     lambda *args, **kwargs: None)
    # 1) stub out parse_args
    monkeypatch.setattr(vimba_rap3, "parse_args", lambda: (5,6,0))

    # 2) ***This must be at top‐level inside the test, not indented under FakeSys!***
    monkeypatch.setattr(vimba_rap3, "savedirectory", str(tmp_path))

    # 3) stub out VmbSystem and get_camera
    class FakeSys:
        def __enter__(self): return None
        def __exit__(self,*a): return False

    monkeypatch.setattr(vimba_rap3.VmbSystem, "get_instance",
                        classmethod(lambda cls: FakeSys()))
    monkeypatch.setattr(vimba_rap3, "get_camera",
                        lambda cid: (_ for _ in ()).throw(SystemExit(7)))

    # 4) now run main—os.chdir(tmp_path) will succeed
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 7

    out = capsys.readouterr().out
    assert "/// vimba opencv" in out


# 3) Slave-mode != 0 → skip preamble entirely, then exit
def test_main_skips_preamble_when_slave_mode_one(monkeypatch, capsys):
    # stub out the display routines so no real OpenCV windows ever appear
    monkeypatch.setattr(vimba_rap3, "setupdisplaywindows", lambda *args, **kwargs: [])
    monkeypatch.setattr(vimba_rap3, "maybeshowimage",     lambda *args, **kwargs: None)
    monkeypatch.setattr(vimba_rap3, "parse_args", lambda: (1,1,1))
    monkeypatch.setattr(os, "chdir", lambda _: None)   # no-op

    class FakeSys:
        def __enter__(self): return None
        def __exit__(self,*a): return False
    monkeypatch.setattr(vimba_rap3.VmbSystem, "get_instance", classmethod(lambda cls: FakeSys()))
    monkeypatch.setattr(vimba_rap3, "get_camera", lambda cid: (_ for _ in ()).throw(SystemExit(8)))

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 8

    out = capsys.readouterr().out
    assert "/// vimba opencv" not in out
