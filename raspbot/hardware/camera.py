from __future__ import annotations

import time

import cv2

from raspbot.config import CameraConfig


class PiCamera:
    """PiCamera2 wrapper that always returns BGR frames for OpenCV."""

    def __init__(self, config: CameraConfig | None = None):
        self.config = config or CameraConfig()
        self.camera = None

    def start(self) -> None:
        try:
            from picamera2 import Picamera2
        except Exception as exc:
            raise RuntimeError("picamera2 is required on Raspberry Pi hardware.") from exc

        self.camera = Picamera2()
        self.camera.configure(
            self.camera.create_preview_configuration(
                main={
                    "format": self.config.format,
                    "size": self.config.size,
                }
            )
        )
        self.camera.start()
        time.sleep(self.config.warmup_seconds)

    def read_bgr(self):
        if self.camera is None:
            raise RuntimeError("Camera is not started. Call camera.start() first.")

        yuv_frame = self.camera.capture_array("main")
        return cv2.cvtColor(yuv_frame, cv2.COLOR_YUV2BGR_I420)

    def stop(self) -> None:
        if self.camera is not None:
            self.camera.stop()
            self.camera = None
