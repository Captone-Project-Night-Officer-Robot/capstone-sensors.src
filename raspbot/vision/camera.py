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

import raspbot.config as cfg


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

        # Optional exposure lock — prevents auto-exposure from blowing
        # the sensor out under glare or sunlight. Wrapped in try/except
        # because not every libcamera build accepts the same control
        # names; the camera still works without it.
        if cfg.CAMERA_FIX_EXPOSURE:
            try:
                self.picam2.set_controls({
                    "AeEnable": False,
                    "AwbEnable": False,
                    "ExposureTime": int(cfg.CAMERA_EXPOSURE_TIME_US),
                    "AnalogueGain": float(cfg.CAMERA_ANALOGUE_GAIN),
                })
                print(
                    f"[camera] exposure locked: "
                    f"{cfg.CAMERA_EXPOSURE_TIME_US}us gain={cfg.CAMERA_ANALOGUE_GAIN}"
                )
            except Exception as exc:
                print(f"[camera] WARNING: could not lock exposure ({exc})")

    def read(self) -> np.ndarray:
        frame = self.picam2.capture_array()

        # We asked for RGB888 but libcamera can fall back to a different
        # format if the configured sensor is missing (e.g. CSI camera
        # unplugged, USB UVC is picked up instead and returns YUYV). Be
        # defensive about channel count.
        if frame.ndim == 2:
            # Grayscale → upsample to BGR so the rest of the pipeline can
            # treat it uniformly.
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        channels = frame.shape[2] if frame.ndim == 3 else 0
        if channels == 3:
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        if channels == 4:
            return cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        if channels == 2:
            # YUYV (Y0 U Y1 V) packed in 2 channels — happens when the
            # actual sensor is a USB UVC cam exposing only YUYV. Unpack
            # via the YUY2 → BGR conversion.
            return cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUY2)

        raise RuntimeError(
            f"PiCamera2Camera: unexpected frame shape {frame.shape}. "
            "Is the CSI ribbon seated? Run `rpicam-hello --list-cameras`."
        )

    def release(self) -> None:
        self.picam2.stop()


def create_camera(camera_type: str, index: int, width: int, height: int, fps: int) -> Camera:
    if camera_type == "picamera2":
        return PiCamera2Camera(width=width, height=height, fps=fps)

    if camera_type == "usb":
        return USBCamera(index=index, width=width, height=height, fps=fps)

    raise ValueError("camera_type must be 'picamera2' or 'usb'")
