"""
Dual IR obstacle-avoidance sensors.

Active-low: a pin reads LOW (0) when its IR beam detects an obstacle.
Both reads are fast GPIO reads (microseconds), so this stays inline in the
main loop rather than running on a background thread.
"""

from __future__ import annotations

from dataclasses import dataclass

import raspbot.config as cfg


@dataclass
class IRReading:
    left_blocked: bool
    right_blocked: bool

    @property
    def any_blocked(self) -> bool:
        return self.left_blocked or self.right_blocked


class IRSensors:
    def __init__(self, simulate: bool = False) -> None:
        self.simulate = simulate
        self._gpio = None

        if simulate:
            return

        try:
            import RPi.GPIO as GPIO  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "RPi.GPIO not available. Run on the Pi, or pass simulate=True."
            ) from exc

        self._gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(cfg.IR_LEFT_PIN, GPIO.IN)
        GPIO.setup(cfg.IR_RIGHT_PIN, GPIO.IN)

        if cfg.IR_POWER_PIN is not None:
            GPIO.setup(cfg.IR_POWER_PIN, GPIO.OUT, initial=GPIO.HIGH)

    def read(self) -> IRReading:
        if self.simulate or self._gpio is None:
            return IRReading(False, False)

        GPIO = self._gpio
        left_raw = GPIO.input(cfg.IR_LEFT_PIN)
        right_raw = GPIO.input(cfg.IR_RIGHT_PIN)
        return IRReading(left_blocked=not left_raw, right_blocked=not right_raw)
