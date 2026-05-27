"""
Telemetry publisher: pushes pose + fall events from the Pi to the laptop API.

Runs in a daemon thread. POSTs the latest pose at TELEMETRY_PUBLISH_HZ and
drains a fall-event queue every tick. All HTTP failures are swallowed —
the control loop must never block on telemetry.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Tuple

import requests

import raspbot.config as cfg


PoseFn = Callable[[], Tuple[float, float, float]]
StateFn = Callable[[], str]
MetricsFn = Callable[[], dict]


class TelemetryPublisher:
    def __init__(
        self,
        api_url: str,
        robot_id: str,
        get_pose: PoseFn,
        get_state: StateFn,
        get_metrics: MetricsFn | None = None,
        publish_hz: float = 5.0,
        timeout_sec: float = 1.0,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.robot_id = robot_id
        self.get_pose = get_pose
        self.get_state = get_state
        self.get_metrics = get_metrics
        self.publish_hz = max(0.5, float(publish_hz))
        self.timeout_sec = timeout_sec

        self._http = requests.Session()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="telemetry-pub"
        )
        self._fall_lock = threading.Lock()
        self._fall_queue: deque[dict] = deque()
        self._warned_unreachable = False

    def start(self) -> None:
        self._thread.start()

    def shutdown(self) -> None:
        self._stop.set()

    def emit_fall(
        self,
        x: float,
        y: float,
        ts: float | None = None,
        track_id: int | None = None,
    ) -> None:
        evt: dict = {
            "robot_id": self.robot_id,
            "x": float(x),
            "y": float(y),
            "ts": float(ts if ts is not None else time.time()),
        }
        if track_id is not None:
            evt["track_id"] = int(track_id)
        with self._fall_lock:
            self._fall_queue.append(evt)

    def emit_log(self, level: str, message: str) -> None:
        """Fire-and-forget log line to the dashboard. Best-effort, never blocks.

        Use sparingly — one line per interesting state change (voice start /
        end, fall confirmed, error). Per-frame logs would flood the WS.
        """
        t = threading.Thread(
            target=self._post_log,
            args=(level.upper(), str(message), time.time()),
            daemon=True,
        )
        t.start()

    def _post_log(self, level: str, message: str, ts: float) -> None:
        try:
            self._http.post(
                f"{self.api_url}/api/v1/telemetry/log",
                json={
                    "source": self.robot_id,
                    "level": level,
                    "message": message,
                    "ts": ts,
                    "function": "raspbot",
                },
                timeout=self.timeout_sec,
            )
        except Exception:
            pass

    def _loop(self) -> None:
        dt = 1.0 / self.publish_hz
        while not self._stop.wait(dt):
            self._post_pose()
            self._drain_falls()

    def _post_pose(self) -> None:
        try:
            x, y, theta = self.get_pose()
            state = self.get_state()
        except Exception:
            return

        metrics: dict = {}
        if self.get_metrics is not None:
            try:
                m = self.get_metrics()
                if isinstance(m, dict):
                    metrics = m
            except Exception:
                metrics = {}

        payload = {
            "robot_id": self.robot_id,
            "x": x,
            "y": y,
            "theta": theta,
            "state": state,
            "ts": time.time(),
            "metrics": metrics,
        }
        try:
            self._http.post(
                f"{self.api_url}/api/v1/telemetry/pose",
                json=payload,
                timeout=self.timeout_sec,
            )
            self._warned_unreachable = False
        except Exception as exc:
            if not self._warned_unreachable:
                print(
                    f"[telemetry] pose POST failed ({type(exc).__name__}). "
                    f"Is the API reachable at {self.api_url}? "
                    "Suppressing further warnings."
                )
                self._warned_unreachable = True

    def _drain_falls(self) -> None:
        with self._fall_lock:
            pending = list(self._fall_queue)
            self._fall_queue.clear()
        for evt in pending:
            try:
                self._http.post(
                    f"{self.api_url}/api/v1/telemetry/fall",
                    json=evt,
                    timeout=self.timeout_sec,
                )
                print(f"[telemetry] fall pin posted  x={evt['x']:.2f} y={evt['y']:.2f}")
            except Exception:
                # Requeue and retry next tick.
                with self._fall_lock:
                    self._fall_queue.append(evt)
                return
