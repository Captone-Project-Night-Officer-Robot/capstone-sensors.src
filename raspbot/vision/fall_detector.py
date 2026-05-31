"""
Client for the remote fall-detection server.

Reads a USB camera in a background thread, POSTs each frame as JPEG to the
inference server, and exposes the latest result through thread-safe accessors.

Failure modes are handled gracefully:
  - Server unreachable → state stays last-known, error is recorded.
  - No update for STALE_AFTER_SEC seconds → falling is forced to False.
  - USB camera missing → start() raises, caller can disable the feature.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
import requests


def _corner_rect(
    img: np.ndarray,
    x1: int, y1: int, x2: int, y2: int,
    color: tuple[int, int, int],
    thick: int = 2,
    corner_len: int = 18,
) -> None:
    """cvzone.cornerRect-style box: a faint outline + bright corner ticks."""
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)

    # top-left
    cv2.line(img, (x1, y1), (x1 + corner_len, y1), color, thick)
    cv2.line(img, (x1, y1), (x1, y1 + corner_len), color, thick)
    # top-right
    cv2.line(img, (x2, y1), (x2 - corner_len, y1), color, thick)
    cv2.line(img, (x2, y1), (x2, y1 + corner_len), color, thick)
    # bottom-left
    cv2.line(img, (x1, y2), (x1 + corner_len, y2), color, thick)
    cv2.line(img, (x1, y2), (x1, y2 - corner_len), color, thick)
    # bottom-right
    cv2.line(img, (x2, y2), (x2 - corner_len, y2), color, thick)
    cv2.line(img, (x2, y2), (x2, y2 - corner_len), color, thick)


def _filled_label(
    img: np.ndarray,
    text: str,
    x: int, y: int,
    color: tuple[int, int, int],
    font_scale: float = 0.45,
) -> None:
    """Solid-color background behind text for readability against any frame."""
    (tw, th), baseline = cv2.getTextSize(
        text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
    )
    pad = 4
    top = max(0, y - th - 2 * pad)
    cv2.rectangle(
        img, (x, top), (x + tw + 2 * pad, y), color, -1
    )
    cv2.putText(
        img, text, (x + pad, y - pad),
        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 1, cv2.LINE_AA,
    )


@dataclass
class FallState:
    falling: bool = False
    falling_ids: list[int] = field(default_factory=list)
    people: list[dict[str, Any]] = field(default_factory=list)
    infer_ms: float = 0.0
    last_update: float = 0.0
    last_error: str = ""
    annotated_frame: np.ndarray | None = None
    # Measured FPS of the fall-camera pipeline (frame read + send + decode).
    # Updated on every successful POST.
    fps: float = 0.0


class FallDetectorClient:
    def __init__(
        self,
        server_url: str,
        camera_index: int = 0,
        camera_width: int = 320,
        camera_height: int = 240,
        target_fps: float = 5.0,
        jpeg_quality: int = 70,
        timeout_sec: float = 2.0,
        stale_after_sec: float = 3.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.camera_index = camera_index
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.target_fps = max(0.1, target_fps)
        self.jpeg_quality = jpeg_quality
        self.timeout_sec = timeout_sec
        self.stale_after_sec = stale_after_sec

        self._state = FallState()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._cap: cv2.VideoCapture | None = None
        self._session = requests.Session()
        # Sliding-window FPS estimator. Records the timestamps of recent
        # successful inferences; FPS = N / (newest - oldest).
        self._tick_log: list[float] = []
        self._tick_log_max = 30

    def start(self) -> None:
        if self._thread is not None:
            return

        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            self._cap = None
            raise RuntimeError(
                f"USB camera index {self.camera_index} did not open. "
                "Check `ls /dev/video*` and the --fall-camera-index flag."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def state(self) -> FallState:
        with self._lock:
            s = self._state
            if s.last_update == 0.0:
                return s
            if time.time() - s.last_update > self.stale_after_sec:
                return FallState(
                    falling=False,
                    falling_ids=[],
                    people=[],
                    infer_ms=s.infer_ms,
                    last_update=s.last_update,
                    last_error="stale",
                    annotated_frame=s.annotated_frame,
                    fps=0.0,
                )
            return s

    def is_falling(self) -> bool:
        return self.state().falling

    def _run(self) -> None:
        interval = 1.0 / self.target_fps

        while not self._stop_event.is_set():
            t_loop = time.time()

            try:
                assert self._cap is not None
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    time.sleep(0.1)
                    continue

                result = self._send(frame)
                annotated = self._annotate(frame, result)

                # Update FPS estimator on every successful POST.
                now = time.time()
                self._tick_log.append(now)
                if len(self._tick_log) > self._tick_log_max:
                    del self._tick_log[: len(self._tick_log) - self._tick_log_max]
                if len(self._tick_log) >= 2:
                    span = self._tick_log[-1] - self._tick_log[0]
                    fps = (len(self._tick_log) - 1) / span if span > 0 else 0.0
                else:
                    fps = 0.0

                people = result.get("people", [])
                falling_ids = [
                    int(p["track_id"])
                    for p in people
                    if p.get("is_falling") and p.get("track_id") is not None
                ]

                with self._lock:
                    self._state = FallState(
                        falling=bool(result.get("falling", False)),
                        falling_ids=falling_ids,
                        people=people,
                        infer_ms=float(result.get("infer_ms", 0.0)),
                        last_update=now,
                        last_error="",
                        annotated_frame=annotated,
                        fps=fps,
                    )
            except Exception as exc:
                with self._lock:
                    self._state.last_error = str(exc)
                    # Keep showing the raw frame so the operator still sees the
                    # USB camera even when the server is unreachable.
                    if self._cap is not None:
                        ok, frame = self._cap.read()
                        if ok and frame is not None:
                            self._state.annotated_frame = self._annotate_error(
                                frame, exc
                            )

            elapsed = time.time() - t_loop
            self._stop_event.wait(max(0.0, interval - elapsed))

    def _send(self, frame: np.ndarray) -> dict[str, Any]:
        ok, buf = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if not ok:
            raise RuntimeError("JPEG encode failed")

        files = {"image": ("frame.jpg", buf.tobytes(), "image/jpeg")}
        resp = self._session.post(
            f"{self.server_url}/detect", files=files, timeout=self.timeout_sec
        )
        resp.raise_for_status()
        return resp.json()

    def _annotate(self, frame: np.ndarray, result: dict) -> np.ndarray:
        out = frame.copy()

        for p in result.get("people", []):
            x1, y1, x2, y2 = p["bbox"]
            falling = bool(p.get("is_falling"))
            track_id = p.get("track_id")
            color = (0, 0, 255) if falling else (0, 255, 0)
            id_tag = f"#{track_id} " if track_id is not None else ""
            label = (
                f"{id_tag}{p.get('class','?').upper()}  "
                f"{int(p.get('confidence', 0) * 100)}%"
                + ("  FALL" if falling else "")
            )
            _corner_rect(out, x1, y1, x2, y2, color, thick=2, corner_len=18)
            _filled_label(out, label, x1, y1, color)

        if result.get("falling"):
            cv2.rectangle(out, (0, 0), (out.shape[1], 36), (0, 0, 255), -1)
            cv2.putText(
                out, "FALL DETECTED", (10, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
            )

        infer_ms = float(result.get("infer_ms", 0.0))
        n_people = len(result.get("people", []))
        fps_hint = self._tick_log_fps_hint()
        cv2.putText(
            out,
            f"infer {infer_ms:.0f}ms  people={n_people}  cam={fps_hint:.1f}fps",
            (10, out.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1,
        )
        return out

    def _tick_log_fps_hint(self) -> float:
        # Used only inside _annotate; safe to read without the lock since it's
        # touched on the same thread that owns _tick_log.
        if len(self._tick_log) < 2:
            return 0.0
        span = self._tick_log[-1] - self._tick_log[0]
        return (len(self._tick_log) - 1) / span if span > 0 else 0.0

    def _annotate_error(self, frame: np.ndarray, exc: Exception) -> np.ndarray:
        out = frame.copy()
        cv2.rectangle(out, (0, 0), (out.shape[1], 30), (0, 100, 200), -1)
        msg = f"server error: {type(exc).__name__}"
        cv2.putText(
            out, msg[:48], (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
        )
        return out
