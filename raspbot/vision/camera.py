"""
Camera support for Raspberry Pi 4B.

Supports:
- Raspberry Pi Camera Module through picamera2
- USB camera through OpenCV VideoCapture
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np


class Camera(Protocol):
    def read(self) -> np.ndarray:
        ...

    def release(self) -> None:
        ...


@dataclass
class USBCamera:
    index: int
    width: int
    height: int
    fps: int

    def __post_init__(self) -> None:
        self.cap = cv2.VideoCapture(self.index)

        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open USB camera index {self.index}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

    def read(self) -> np.ndarray:
        ok, frame = self.cap.read()

        if not ok or frame is None:
            raise RuntimeError("Could not read frame from USB camera.")

        return frame

    def release(self) -> None:
        self.cap.release()


@dataclass
class PiCamera2Camera:
    width: int
    height: int
    fps: int

    def __post_init__(self) -> None:
        try:
            from picamera2 import Picamera2  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "picamera2 is not installed.\n"
                "Install it with:\n"
                "  sudo apt install -y python3-picamera2\n"
                "Create venv with:\n"
                "  python3 -m venv .venv --system-site-packages\n"
            ) from exc

        self.picam2 = Picamera2()

        config = self.picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (self.width, self.height)}
        )

        self.picam2.configure(config)
        self.picam2.start()

    def read(self) -> np.ndarray:
        frame_rgb = self.picam2.capture_array()

        # OpenCV uses BGR.
        return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    def release(self) -> None:
        self.picam2.stop()


def create_camera(camera_type: str, index: int, width: int, height: int, fps: int) -> Camera:
    if camera_type == "picamera2":
        return PiCamera2Camera(width=width, height=height, fps=fps)

    if camera_type == "usb":
        return USBCamera(index=index, width=width, height=height, fps=fps)

    raise ValueError("camera_type must be 'picamera2' or 'usb'")
