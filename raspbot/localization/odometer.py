"""
Dead-reckoning odometer for the Yahboom Pi4WD (no encoders, no IMU).

The motor controller reports every commanded (left, right) wheel speed
through `set_wheels()`. A background thread integrates those commands
into a global pose (x, y, theta) at fixed rate. Expect drift on turns —
this is good enough to sketch the explored area on a dashboard, not to
navigate.

Frame convention:
    x → forward, y → left, theta = 0 along +x, ccw positive.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Tuple

import raspbot.config as cfg


class Odometer:
    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0

        self._left_mu = 0.0   # signed motor units (-100..+100). Forward positive.
        self._right_mu = 0.0
        self._lock = threading.Lock()

        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._integrate_loop, daemon=True, name="odometer"
        )
        self._integration_hz = max(1.0, float(cfg.ODOMETRY_INTEGRATION_HZ))

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def set_wheels(self, left_mu: float, right_mu: float) -> None:
        """Latest commanded wheel speeds in signed motor units (-100..+100)."""
        with self._lock:
            self._left_mu = float(left_mu)
            self._right_mu = float(right_mu)

    def pose(self) -> Tuple[float, float, float]:
        with self._lock:
            return self.x, self.y, self.theta

    def reset(self) -> None:
        with self._lock:
            self.x = 0.0
            self.y = 0.0
            self.theta = 0.0

    def _integrate_loop(self) -> None:
        dt_target = 1.0 / self._integration_hz
        last = time.monotonic()
        mps_per_unit = float(cfg.ODOMETRY_MPS_PER_MOTOR_UNIT)
        wheel_base = max(0.01, float(cfg.ODOMETRY_WHEEL_BASE_M))

        while not self._stop.wait(dt_target):
            now = time.monotonic()
            dt = now - last
            last = now
            if dt <= 0.0:
                continue

            with self._lock:
                v_l = self._left_mu * mps_per_unit
                v_r = self._right_mu * mps_per_unit
                v = 0.5 * (v_l + v_r)
                omega = (v_r - v_l) / wheel_base

                # Midpoint integration for the heading so a turn during dt
                # doesn't bias the (x, y) step.
                theta_mid = self.theta + 0.5 * omega * dt
                self.x += v * math.cos(theta_mid) * dt
                self.y += v * math.sin(theta_mid) * dt
                self.theta += omega * dt
