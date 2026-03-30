from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import labthings_fastapi as lt
from pydantic import Field

from .controller import (
    CaptureFrameRequest,
    DEFAULT_FILENAME_PREFIX,
    DEFAULT_TIMEOUT_MS,
    FILENAME_PATTERN,
    MAX_TIMEOUT_MS,
    CaptureFrameResponse,
    ConfigResponse,
    ErrorResponse,
    RAPController,
    RAPError,
    StatusResponse,
)


class RAPThing(lt.Thing):
    def __init__(
        self,
        controller: RAPController | None = None,
        thing_server_interface=None,
    ) -> None:
        super().__init__(thing_server_interface=thing_server_interface)
        self._controller = controller or RAPController()

    @lt.property
    def status(self) -> StatusResponse:
        return self._controller.get_status()

    @lt.property
    def config(self) -> ConfigResponse:
        return self._controller.get_config()

    @lt.action
    def capture_frame(
        self,
        timeout_ms: Annotated[int, Field(ge=1, le=MAX_TIMEOUT_MS)] = DEFAULT_TIMEOUT_MS,
        filename_prefix: Annotated[
            str,
            Field(min_length=1, pattern=FILENAME_PATTERN),
        ] = DEFAULT_FILENAME_PREFIX,
    ) -> CaptureFrameResponse:
        return self._controller.capture_frame(
            timeout_ms=timeout_ms,
            filename_prefix=filename_prefix,
        )


def create_app(
    controller: RAPController | None = None,
    simulation: bool = False,
) -> FastAPI:
    effective_controller = controller or RAPController(
        simulation=simulation or _simulation_enabled()
    )
    settings_root = Path(tempfile.gettempdir()) / "rap-labthings-settings"
    thing_config = lt.ThingConfig(
        cls=RAPThing,
        kwargs={"controller": effective_controller},
    )
    server = lt.ThingServer(
        {"rap": thing_config},
        settings_folder=str(settings_root),
    )
    app = server.app
    app.state.thing_server = server
    app.state.rap_controller = effective_controller
    app.add_exception_handler(RAPError, _rap_error_handler)

    @app.post("/rap/capture_frame_sync", response_model=CaptureFrameResponse)
    def capture_frame_sync(request: CaptureFrameRequest) -> CaptureFrameResponse:
        return effective_controller.capture_frame(
            timeout_ms=request.timeout_ms,
            filename_prefix=request.filename_prefix,
        )

    return app


async def _rap_error_handler(_request: Request, exc: RAPError) -> JSONResponse:
    payload = ErrorResponse(error=exc.error_code, detail=exc.detail)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


def _simulation_enabled() -> bool:
    return os.getenv("RAP_LABTHINGS_SIMULATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


app = create_app()
