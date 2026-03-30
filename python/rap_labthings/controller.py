from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import vimba_rap3 as rap


DEFAULT_TIMEOUT_MS = 2000
MAX_TIMEOUT_MS = 60000
DEFAULT_FILENAME_PREFIX = "rap_capture"
FILENAME_PATTERN = r"^[A-Za-z0-9._-]+$"
SIMULATION_IMAGE_SHAPE = (624, 816)


class RAPError(Exception):
    status_code = 500
    error_code = "rap_error"

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class RAPBusyError(RAPError):
    status_code = 409
    error_code = "rap_busy"


class RAPInputError(RAPError):
    status_code = 422
    error_code = "rap_invalid_input"


class RAPConfigError(RAPError):
    status_code = 500
    error_code = "rap_config_error"


class RAPCameraError(RAPError):
    status_code = 503
    error_code = "rap_camera_unavailable"


class RAPCaptureError(RAPError):
    status_code = 500
    error_code = "rap_capture_error"


class ErrorResponse(BaseModel):
    error: str
    detail: str


class StatusResponse(BaseModel):
    busy: bool
    simulation: bool


class ConfigResponse(BaseModel):
    freerun_config_path: str
    trigger_config_path: str
    capture_output_dir: str
    default_timeout_ms: int


class CaptureFrameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: int = Field(default=DEFAULT_TIMEOUT_MS, ge=1, le=MAX_TIMEOUT_MS)
    filename_prefix: str = Field(
        default=DEFAULT_FILENAME_PREFIX,
        min_length=1,
        pattern=FILENAME_PATTERN,
    )


class CaptureFrameResponse(BaseModel):
    saved_path: str
    width: int
    height: int
    pixel_format: str
    simulation: bool
    captured_at: str


@dataclass(frozen=True)
class RAPControllerConfig:
    repo_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    freerun_config_path: Path | None = None
    trigger_config_path: Path | None = None
    capture_output_dir: Path | None = None
    default_timeout_ms: int = DEFAULT_TIMEOUT_MS

    def __post_init__(self) -> None:
        repo_root = self.repo_root.resolve()
        object.__setattr__(self, "repo_root", repo_root)
        object.__setattr__(
            self,
            "freerun_config_path",
            (self.freerun_config_path or repo_root / "config" / "freerun.xml").resolve(),
        )
        object.__setattr__(
            self,
            "trigger_config_path",
            (self.trigger_config_path or repo_root / "config" / "trigger.xml").resolve(),
        )
        object.__setattr__(
            self,
            "capture_output_dir",
            (self.capture_output_dir or repo_root / "data" / "labthings-captures").resolve(),
        )
        if not 1 <= self.default_timeout_ms <= MAX_TIMEOUT_MS:
            raise ValueError("default_timeout_ms must be between 1 and 60000")


class RAPController:
    def __init__(
        self,
        config: RAPControllerConfig | None = None,
        *,
        simulation: bool = False,
    ) -> None:
        self.config = config or RAPControllerConfig()
        self.simulation = simulation
        self._capture_lock = threading.Lock()

    @property
    def capture_lock(self) -> threading.Lock:
        return self._capture_lock

    def get_status(self) -> StatusResponse:
        return StatusResponse(
            busy=self.capture_lock.locked(),
            simulation=self.simulation,
        )

    def get_config(self) -> ConfigResponse:
        return ConfigResponse(
            freerun_config_path=str(self.config.freerun_config_path),
            trigger_config_path=str(self.config.trigger_config_path),
            capture_output_dir=str(self.config.capture_output_dir),
            default_timeout_ms=self.config.default_timeout_ms,
        )

    def capture_frame(
        self,
        *,
        timeout_ms: int | None = None,
        filename_prefix: str | None = None,
    ) -> CaptureFrameResponse:
        request = self._validate_request(
            timeout_ms=self.config.default_timeout_ms if timeout_ms is None else timeout_ms,
            filename_prefix=DEFAULT_FILENAME_PREFIX if filename_prefix is None else filename_prefix,
        )

        lock_acquired = self.capture_lock.acquire(blocking=False)
        if not lock_acquired:
            raise RAPBusyError("A capture is already in progress.")

        try:
            captured_at = datetime.now(timezone.utc)
            if self.simulation:
                image = self._build_simulated_image()
                pixel_format = str(rap.opencv_display_format)
            else:
                image, pixel_format = self._capture_hardware_image(request.timeout_ms)
            saved_path = self._save_image(
                image=image,
                filename_prefix=request.filename_prefix,
                captured_at=captured_at,
            )
            return CaptureFrameResponse(
                saved_path=str(saved_path),
                width=int(image.shape[1]),
                height=int(image.shape[0]),
                pixel_format=pixel_format,
                simulation=self.simulation,
                captured_at=captured_at.isoformat(),
            )
        finally:
            self.capture_lock.release()

    def _validate_request(self, *, timeout_ms: int, filename_prefix: str) -> CaptureFrameRequest:
        try:
            return CaptureFrameRequest(
                timeout_ms=timeout_ms,
                filename_prefix=filename_prefix,
            )
        except ValidationError as exc:
            raise RAPInputError(self._validation_message(exc)) from exc

    def _capture_hardware_image(self, timeout_ms: int) -> tuple[np.ndarray, str]:
        if not self.config.freerun_config_path.exists():
            raise RAPConfigError(
                f"Freerun camera config was not found: {self.config.freerun_config_path}"
            )

        try:
            with rap.VmbSystem.get_instance():
                cam = self._call_legacy(
                    RAPCameraError,
                    "Failed to access a RAP camera.",
                    rap.get_camera,
                    None,
                )
                with cam:
                    self._call_legacy(
                        RAPCameraError,
                        "Failed to configure the RAP camera.",
                        rap.setup_camera,
                        cam,
                    )
                    try:
                        rap.load_camera_settings(cam, str(self.config.freerun_config_path))
                    except SystemExit as exc:
                        raise RAPConfigError(
                            "Failed to load the RAP freerun camera config."
                        ) from exc
                    except Exception as exc:
                        raise RAPConfigError(
                            f"Failed to load the RAP freerun camera config: {exc}"
                        ) from exc

                    self._call_legacy(
                        RAPCameraError,
                        "Failed to select a usable RAP pixel format.",
                        rap.setup_pixel_format,
                        cam,
                    )

                    try:
                        frame = cam.get_frame(timeout_ms=timeout_ms)
                    except Exception as exc:
                        raise RAPCaptureError(f"Failed to capture a RAP frame: {exc}") from exc

                    if frame.get_status() != rap.FrameStatus.Complete:
                        raise RAPCaptureError(
                            f"Captured frame was not complete: {frame.get_status()}"
                        )

                    return self._frame_to_image(frame)
        except RAPError:
            raise
        except Exception as exc:
            raise RAPCameraError(f"Unexpected camera error: {exc}") from exc

    def _frame_to_image(self, frame) -> tuple[np.ndarray, str]:
        display_frame = frame
        pixel_format = frame.get_pixel_format()
        if pixel_format != rap.opencv_display_format:
            try:
                display_frame = frame.convert_pixel_format(rap.opencv_display_format)
            except Exception as exc:
                raise RAPCaptureError(
                    "Failed to convert the RAP frame to the OpenCV display format."
                ) from exc
            pixel_format = rap.opencv_display_format

        try:
            image = display_frame.as_opencv_image().copy()
        except Exception as exc:
            raise RAPCaptureError("Failed to read the RAP frame as an OpenCV image.") from exc

        if image.ndim not in (2, 3):
            raise RAPCaptureError(f"Unsupported captured image shape: {image.shape}")

        return image, str(pixel_format)

    def _build_simulated_image(self) -> np.ndarray:
        rows = np.arange(SIMULATION_IMAGE_SHAPE[0], dtype=np.uint16).reshape(-1, 1)
        cols = np.arange(SIMULATION_IMAGE_SHAPE[1], dtype=np.uint16).reshape(1, -1)
        return ((rows + cols) % 256).astype(np.uint8)

    def _save_image(
        self,
        *,
        image: np.ndarray,
        filename_prefix: str,
        captured_at: datetime,
    ) -> Path:
        try:
            self.config.capture_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RAPCaptureError(
                f"Failed to create capture output directory: {self.config.capture_output_dir}"
            ) from exc

        timestamp = captured_at.strftime("%Y%m%dT%H%M%S%fZ")
        output_path = self.config.capture_output_dir / f"{filename_prefix}_{timestamp}.tif"

        try:
            saved = cv2.imwrite(str(output_path), image)
        except Exception as exc:
            raise RAPCaptureError(f"Failed to save captured frame: {exc}") from exc

        if not saved:
            raise RAPCaptureError(f"Failed to save captured frame: {output_path}")

        return output_path.resolve()

    def _call_legacy(self, exc_type: type[RAPError], message: str, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SystemExit as exc:
            raise exc_type(message) from exc

    @staticmethod
    def _validation_message(exc: ValidationError) -> str:
        first_error = exc.errors()[0]
        location = ".".join(str(part) for part in first_error.get("loc", ()))
        message = first_error.get("msg", "Invalid input.")
        return f"{location}: {message}" if location else message
