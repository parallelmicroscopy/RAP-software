from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import numpy as np
import pytest

import rap_labthings.controller as controller_module
from rap_labthings.controller import (
    RAPBusyError,
    RAPCameraError,
    RAPCaptureError,
    RAPController,
    RAPControllerConfig,
)

app_module = importlib.import_module("rap_labthings.app")


class FakeVmbSystemContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeCamera:
    def __init__(self, frame):
        self.frame = frame
        self.enter_count = 0
        self.exit_count = 0
        self.get_frame_calls = []

    def __enter__(self):
        self.enter_count += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exit_count += 1
        return False

    def get_frame(self, timeout_ms):
        self.get_frame_calls.append(timeout_ms)
        return self.frame


class FakeFrame:
    def __init__(self, image, pixel_format, converted_frame=None):
        self._image = image
        self._pixel_format = pixel_format
        self._converted_frame = converted_frame
        self.convert_calls = []

    def get_status(self):
        return controller_module.rap.FrameStatus.Complete

    def get_pixel_format(self):
        return self._pixel_format

    def convert_pixel_format(self, pixel_format):
        self.convert_calls.append(pixel_format)
        if self._converted_frame is None:
            raise AssertionError("convert_pixel_format should not be called")
        return self._converted_frame

    def as_opencv_image(self):
        return self._image


def fake_imwrite(filename, image):
    Path(filename).write_bytes(b"fake-image")
    return True


def build_simulation_controller(tmp_path) -> RAPController:
    return RAPController(
        config=RAPControllerConfig(capture_output_dir=tmp_path / "captures"),
        simulation=True,
    )


def run_app_script(tmp_path, scenario_code: str) -> dict:
    python_dir = Path(__file__).resolve().parents[2] / "python"
    capture_dir = tmp_path / "captures"
    script = f"""
import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

sys.path.insert(0, {str(python_dir)!r})

fake_cv2 = ModuleType("cv2")

def imwrite(filename, image):
    Path(filename).write_bytes(b"fake-image")
    return True

fake_cv2.imwrite = imwrite
sys.modules["cv2"] = fake_cv2

import httpx
import labthings_fastapi.actions as lt_actions

lt_actions.ActionDescriptor.emit_changed_event = lambda *args, **kwargs: None

app_module = importlib.import_module("rap_labthings.app")
from rap_labthings.controller import RAPController, RAPControllerConfig

async def wait_for_completion(client, href):
    path = href.replace("http://testserver", "")
    for _ in range(50):
        payload = (await client.get(path)).json()
        if payload["status"] in {{"completed", "error"}}:
            return payload
        await asyncio.sleep(0.01)
    raise RuntimeError("Action invocation did not complete in time")

async def main():
    controller = RAPController(
        config=RAPControllerConfig(capture_output_dir=Path({str(capture_dir)!r})),
        simulation=True,
    )
    app = app_module.create_app(controller=controller)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
{textwrap.indent(scenario_code, " " * 8)}

asyncio.run(main())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_app_imports_and_create_app_works():
    assert app_module.app is not None
    app = app_module.create_app(simulation=True)
    assert app is not None


def test_status_endpoint_reports_lock_state(tmp_path):
    payload = run_app_script(
        tmp_path,
        """
response = await client.get("/rap/status")
first = response.json()
controller.capture_lock.acquire()
try:
    second = (await client.get("/rap/status")).json()
finally:
    controller.capture_lock.release()
print(json.dumps({"first": first, "second": second}))
""",
    )
    assert payload == {
        "first": {"busy": False, "simulation": True},
        "second": {"busy": True, "simulation": True},
    }


def test_config_endpoint_returns_effective_paths(tmp_path):
    payload = run_app_script(
        tmp_path,
        """
response = await client.get("/rap/config")
print(json.dumps(response.json()))
""",
    )
    assert payload["freerun_config_path"].endswith("config/freerun.xml")
    assert payload["trigger_config_path"].endswith("config/trigger.xml")
    assert payload["capture_output_dir"] == str((tmp_path / "captures").resolve())
    assert payload["default_timeout_ms"] == 2000


def test_capture_frame_action_writes_file_and_returns_metadata(tmp_path):
    payload = run_app_script(
        tmp_path,
        """
response = await client.post(
    "/rap/capture_frame",
    json={"timeout_ms": 2500, "filename_prefix": "test_capture"},
)
invocation = await wait_for_completion(client, response.json()["href"])
output = await client.get(invocation["href"].replace("http://testserver", "") + "/output")
body = output.json()
print(json.dumps({
    "post_status": response.status_code,
    "invocation_status": invocation["status"],
    "output_status": output.status_code,
    "output": body,
    "saved_exists": Path(body["saved_path"]).exists(),
}))
""",
    )
    assert payload["post_status"] == 201
    assert payload["invocation_status"] == "completed"
    assert payload["output_status"] == 200
    assert payload["saved_exists"] is True
    assert payload["output"]["simulation"] is True
    assert payload["output"]["pixel_format"] == "Mono8"
    assert payload["output"]["width"] == 816
    assert payload["output"]["height"] == 624
    assert payload["output"]["saved_path"].endswith(".tif")
    assert Path(payload["output"]["saved_path"]).parent == (tmp_path / "captures").resolve()


def test_capture_frame_invalid_input_returns_422(tmp_path):
    payload = run_app_script(
        tmp_path,
        """
first = await client.post("/rap/capture_frame", json={"timeout_ms": 0, "filename_prefix": "bad"})
second = await client.post("/rap/capture_frame", json={"timeout_ms": 10, "filename_prefix": "bad/name"})
print(json.dumps({"first": first.status_code, "second": second.status_code}))
""",
    )
    assert payload == {"first": 422, "second": 422}


def test_busy_capture_maps_to_clean_http_response(tmp_path):
    payload = run_app_script(
        tmp_path,
        """
controller.capture_lock.acquire()
try:
    response = await client.post(
        "/rap/capture_frame_sync",
        json={"timeout_ms": 1000, "filename_prefix": "sync"},
    )
finally:
    controller.capture_lock.release()
print(json.dumps({"status_code": response.status_code, "body": response.json()}))
""",
    )
    assert payload == {
        "status_code": 409,
        "body": {
            "error": "rap_busy",
            "detail": "A capture is already in progress.",
        },
    }


def test_controller_hardware_capture_uses_legacy_helpers_and_releases_resources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(controller_module.cv2, "imwrite", fake_imwrite, raising=False)

    converted_frame = FakeFrame(
        np.full((4, 5), 7, dtype=np.uint8),
        controller_module.rap.opencv_display_format,
    )
    raw_frame = FakeFrame(
        np.full((4, 5), 3, dtype=np.uint8),
        controller_module.rap.PixelFormat.Bgr8,
        converted_frame=converted_frame,
    )
    camera = FakeCamera(raw_frame)
    calls = []

    monkeypatch.setattr(
        controller_module.rap.VmbSystem,
        "get_instance",
        classmethod(lambda cls: FakeVmbSystemContext()),
    )
    monkeypatch.setattr(
        controller_module.rap,
        "get_camera",
        lambda _camera_id: camera,
    )
    monkeypatch.setattr(
        controller_module.rap,
        "setup_camera",
        lambda cam: calls.append(("setup_camera", cam)),
    )
    monkeypatch.setattr(
        controller_module.rap,
        "load_camera_settings",
        lambda cam, path: calls.append(("load_camera_settings", cam, path)),
    )
    monkeypatch.setattr(
        controller_module.rap,
        "setup_pixel_format",
        lambda cam: calls.append(("setup_pixel_format", cam)),
    )

    controller = RAPController(
        config=RAPControllerConfig(capture_output_dir=tmp_path / "captures"),
        simulation=False,
    )

    response = controller.capture_frame(timeout_ms=3210, filename_prefix="hardware")

    assert response.simulation is False
    assert response.pixel_format == "Mono8"
    assert response.width == 5
    assert response.height == 4
    assert Path(response.saved_path).exists()
    assert camera.enter_count == 1
    assert camera.exit_count == 1
    assert camera.get_frame_calls == [3210]
    assert raw_frame.convert_calls == [controller_module.rap.opencv_display_format]
    assert calls == [
        ("setup_camera", camera),
        ("load_camera_settings", camera, str(controller.config.freerun_config_path)),
        ("setup_pixel_format", camera),
    ]
    assert controller.capture_lock.locked() is False


def test_legacy_system_exit_becomes_rap_camera_error_and_releases_lock(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        controller_module.rap.VmbSystem,
        "get_instance",
        classmethod(lambda cls: FakeVmbSystemContext()),
    )
    monkeypatch.setattr(
        controller_module.rap,
        "get_camera",
        lambda _camera_id: (_ for _ in ()).throw(SystemExit(2)),
    )

    controller = RAPController(
        config=RAPControllerConfig(capture_output_dir=tmp_path / "captures"),
        simulation=False,
    )

    with pytest.raises(RAPCameraError, match="Failed to access a RAP camera."):
        controller.capture_frame(timeout_ms=1000, filename_prefix="legacy")

    assert controller.capture_lock.locked() is False


def test_controller_raises_busy_error_when_lock_is_held(tmp_path):
    controller = build_simulation_controller(tmp_path)
    controller.capture_lock.acquire()
    try:
        with pytest.raises(RAPBusyError, match="A capture is already in progress."):
            controller.capture_frame()
    finally:
        controller.capture_lock.release()


def test_capture_save_failure_raises_capture_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        controller_module.cv2,
        "imwrite",
        lambda *_args, **_kwargs: False,
        raising=False,
    )
    controller = build_simulation_controller(tmp_path)

    with pytest.raises(RAPCaptureError, match="Failed to save captured frame"):
        controller.capture_frame()
