from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from raspbot.config import AppConfig
from raspbot.hardware.ir_sensors import IRReading
from raspbot.hardware.motor import MotorLike
from raspbot.vision.types import LaneDetectionResult


@dataclass(frozen=True)
class NavigationTelemetry:
    action: str
    reason: str
    distance_cm: float
    ir_left_detected: bool
    ir_right_detected: bool
    lane_direction: str
    lane_confidence: float
    left_motor_speed: int
    right_motor_speed: int


class LineFollowerController:
    """Combines sensor readings + lane detection into motor commands."""

    def __init__(self, motor: MotorLike, config: AppConfig | None = None):
        self.motor = motor
        self.config = config or AppConfig()

    def decide(
        self,
        distance_cm: float,
        ir: Optional[IRReading],
        lane: LaneDetectionResult,
    ) -> NavigationTelemetry:
        nav_cfg = self.config.navigation
        motor_cfg = self.config.motor

        left_ir_detected = bool(ir.left_detected) if ir else False
        right_ir_detected = bool(ir.right_detected) if ir else False

        if distance_cm != -1 and distance_cm < nav_cfg.emergency_stop_cm:
            return self._telemetry("stop", "front_emergency_obstacle", distance_cm, left_ir_detected, right_ir_detected, lane, 0, 0)

        if distance_cm != -1 and distance_cm < nav_cfg.caution_cm:
            return self._telemetry("slow_forward", "front_caution_zone", distance_cm, left_ir_detected, right_ir_detected, lane, motor_cfg.slow_speed, motor_cfg.slow_speed)

        if left_ir_detected and right_ir_detected:
            return self._telemetry("stop", "both_side_ir_obstacles", distance_cm, True, True, lane, 0, 0)

        if left_ir_detected:
            return self._telemetry("steer_right", "left_ir_obstacle", distance_cm, True, False, lane, motor_cfg.turn_speed, int(motor_cfg.turn_speed * 0.55))

        if right_ir_detected:
            return self._telemetry("steer_left", "right_ir_obstacle", distance_cm, False, True, lane, int(motor_cfg.turn_speed * 0.55), motor_cfg.turn_speed)

        if lane.direction == "straight":
            return self._telemetry("forward", lane.reason, distance_cm, False, False, lane, motor_cfg.forward_speed, motor_cfg.forward_speed)

        if lane.direction == "left":
            return self._telemetry("steer_left", lane.reason, distance_cm, False, False, lane, int(motor_cfg.turn_speed * 0.55), motor_cfg.turn_speed)

        if lane.direction == "right":
            return self._telemetry("steer_right", lane.reason, distance_cm, False, False, lane, motor_cfg.turn_speed, int(motor_cfg.turn_speed * 0.55))

        if nav_cfg.no_lane_behavior == "stop":
            return self._telemetry("stop", "no_lane_detected", distance_cm, False, False, lane, 0, 0)

        return self._telemetry("slow_forward", "no_lane_detected_slow_forward", distance_cm, False, False, lane, motor_cfg.slow_speed, motor_cfg.slow_speed)

    def apply(self, telemetry: NavigationTelemetry) -> None:
        self.motor.set_speed(telemetry.left_motor_speed, telemetry.right_motor_speed)

    def _telemetry(
        self,
        action: str,
        reason: str,
        distance_cm: float,
        left_ir_detected: bool,
        right_ir_detected: bool,
        lane: LaneDetectionResult,
        left_speed: int,
        right_speed: int,
    ) -> NavigationTelemetry:
        return NavigationTelemetry(
            action=action,
            reason=reason,
            distance_cm=distance_cm,
            ir_left_detected=left_ir_detected,
            ir_right_detected=right_ir_detected,
            lane_direction=lane.direction,
            lane_confidence=lane.confidence,
            left_motor_speed=left_speed,
            right_motor_speed=right_speed,
        )
