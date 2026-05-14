"""
Obstacle avoidance layer.

Fuses ultrasonic distance + dual IR into one decision: are we blocked, and if
so which way should we spin? Designed to be called *before* the line-follow
action each frame so it can override the motor command.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import raspbot.config as cfg
from raspbot.hardware.ir_sensors import IRReading, IRSensors
from raspbot.hardware.motor import MotorController
from raspbot.hardware.ultrasonic import UltrasonicSensor


@dataclass
class AvoidDecision:
    blocked: bool
    distance_cm: float
    ir: IRReading
    direction: str  # "left", "right", or "none"
    reason: str


class Avoider:
    def __init__(self, simulate: bool = False) -> None:
        self.simulate = simulate
        self.ultrasonic = UltrasonicSensor(simulate=simulate)
        # If IR is disabled in config, run the IR module in simulate mode so
        # it always reports "not blocked".
        self.ir = IRSensors(simulate=simulate or not cfg.IR_ENABLED)
        self.ultrasonic.start()

    def evaluate(self) -> AvoidDecision:
        """Hard front-safety check. Triggers only on ultrasonic distance.

        IR sensors are still read so callers can use them for line-lost
        navigation, but they no longer fire the emergency stop/spin maneuver.
        """
        distance = self.ultrasonic.latest_cm()
        ir = self.ir.read()

        too_close = distance < cfg.AVOID_DISTANCE_CM

        if not too_close:
            return AvoidDecision(False, distance, ir, "none", "clear")

        # Use IR to bias the spin direction — turn away from a blocked side.
        if ir.left_blocked and not ir.right_blocked:
            direction = "right"
        elif ir.right_blocked and not ir.left_blocked:
            direction = "left"
        else:
            direction = "right"

        return AvoidDecision(True, distance, ir, direction, "distance")

    def read_ir(self) -> IRReading:
        return self.ir.read()

    def execute(self, motor: MotorController, decision: AvoidDecision) -> None:
        motor.stop()
        time.sleep(0.05)

        if cfg.AVOID_BACKUP_SEC > 0:
            motor.back(cfg.AVOID_BACKUP_SPEED)
            time.sleep(cfg.AVOID_BACKUP_SEC)
            motor.stop()
            time.sleep(0.05)

        if decision.direction == "left":
            motor.spin_left(cfg.AVOID_SPIN_SPEED)
        else:
            motor.spin_right(cfg.AVOID_SPIN_SPEED)

        time.sleep(cfg.AVOID_SPIN_SEC)
        motor.stop()

    def cleanup(self) -> None:
        self.ultrasonic.cleanup()
