"""
Sensor aggregator for obstacle awareness.

Owns the background ultrasonic thread and the IR sensor pair. The main loop
pulls `distance_cm()` and `read_ir()` each frame and decides what to do — no
motor logic lives here (intentionally; behavior is centralized in
`raspbot.apps.line_follow`).
"""

from __future__ import annotations

import raspbot.config as cfg
from raspbot.hardware.ir_sensors import IRReading, IRSensors
from raspbot.hardware.ultrasonic import UltrasonicSensor


class Sensors:
    """Thin owner of the ultrasonic + IR sensors."""

    def __init__(self, simulate: bool = False) -> None:
        self.ultrasonic = UltrasonicSensor(simulate=simulate)
        # If IR is disabled in config, run the IR module in simulate mode so
        # it always reports "not blocked".
        self.ir = IRSensors(simulate=simulate or not cfg.IR_ENABLED)
        self.ultrasonic.start()

    def distance_cm(self) -> float:
        return self.ultrasonic.latest_cm()

    def read_ir(self) -> IRReading:
        return self.ir.read()

    def obstacle_ahead(self) -> bool:
        return self.distance_cm() <= cfg.OBSTACLE_DISTANCE_CM

    def cleanup(self) -> None:
        self.ultrasonic.cleanup()


# Backwards-compatible alias — older scripts/tests imported `Avoider`.
Avoider = Sensors
