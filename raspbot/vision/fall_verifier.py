"""
Debounce / verification gate for the remote YOLO fall detector.

A single `falling=True` frame is not enough to commit to "this is a real
fall" — the model occasionally flickers on people who lean, squat, or
walk past at an awkward angle. The verifier holds the car stopped while
the signal stabilises, then promotes once it has been continuously True
for `cfg.FALL_VERIFY_SECONDS`.

States:
    "idle"       — no falling signal
    "verifying"  — falling=True, but not yet held long enough to confirm
    "confirmed"  — held continuously for the verify window; pin + voice OK

The car should stop in BOTH "verifying" and "confirmed". Only "confirmed"
should drop a map pin or open a voice session.
"""

from __future__ import annotations

import time
from typing import Literal

FallStatus = Literal["idle", "verifying", "confirmed"]


class FallVerifier:
    def __init__(self, verify_seconds: float) -> None:
        self.verify_seconds = max(0.0, float(verify_seconds))
        self._held_since: float | None = None
        self._status: FallStatus = "idle"

    @property
    def status(self) -> FallStatus:
        return self._status

    def update(self, falling: bool, now: float | None = None) -> FallStatus:
        """Feed the latest YOLO signal. Returns the new status."""
        t = time.time() if now is None else now

        if not falling:
            self._held_since = None
            self._status = "idle"
            return self._status

        if self._held_since is None:
            self._held_since = t

        if t - self._held_since >= self.verify_seconds:
            self._status = "confirmed"
        else:
            self._status = "verifying"
        return self._status

    def held_seconds(self, now: float | None = None) -> float:
        """How long the current `falling=True` run has been held. 0 when idle."""
        if self._held_since is None:
            return 0.0
        t = time.time() if now is None else now
        return max(0.0, t - self._held_since)
