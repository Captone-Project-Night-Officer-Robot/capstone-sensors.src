from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


@dataclass(frozen=True)
class GPIOConfig:
    """GPIO pin configuration.

    Pin numbering uses GPIO.BOARD mode, matching the original prototype code.
    """

    trig_pin: int = 16
    echo_pin: int = 18

    left_ir_pin: int = 21
    right_ir_pin: int = 19
    ir_enable_pin: int = 22


@dataclass(frozen=True)
class CameraConfig:
    width: int = 640
    height: int = 480
    format: str = "YUV420"
    warmup_seconds: float = 1.0

    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)


@dataclass(frozen=True)
class MotorConfig:
    """Motor runtime tuning.

    This project does NOT read YB_PCB_CAR_PATH from .env anymore.
    The local driver is imported from:
        robot_side/motor_driver/YB_Pcb_Car.py
    """

    forward_speed: int = _env_int("RASPBOT_FORWARD_SPEED", 30)
    turn_speed: int = _env_int("RASPBOT_TURN_SPEED", 25)
    slow_speed: int = _env_int("RASPBOT_SLOW_SPEED", 20)
    max_speed: int = 100


@dataclass(frozen=True)
class LaneConfig:
    # White line HSV threshold:
    # White usually has LOW saturation and HIGH brightness/value.
    lower_white_h: int = 0
    lower_white_s: int = 0
    lower_white_v: int = 170

    upper_white_h: int = 180
    upper_white_s: int = 80
    upper_white_v: int = 255

    morphology_kernel_size: int = 5

    # ROI shape for a single center white line.
    roi_top_ratio: float = 0.35
    roi_left_top_ratio: float = 0.20
    roi_right_top_ratio: float = 0.80

    hough_rho: int = 2
    hough_theta_divisor: int = 180
    hough_threshold: int = 60
    hough_min_line_length: int = 50
    hough_max_line_gap: int = 40

    lane_center_tolerance_px: int = 25
    min_lines_required: int = 1


@dataclass(frozen=True)
class NavigationConfig:
    emergency_stop_cm: float = _env_float("RASPBOT_EMERGENCY_STOP_CM", 10.0)
    caution_cm: float = _env_float("RASPBOT_CAUTION_CM", 20.0)
    max_valid_distance_cm: float = 500.0

    # If no line is detected, either "slow_forward" or "stop".
    no_lane_behavior: str = "slow_forward"

    control_loop_sleep_sec: float = 0.05


@dataclass(frozen=True)
class AppConfig:
    gpio: GPIOConfig = GPIOConfig()
    camera: CameraConfig = CameraConfig()
    motor: MotorConfig = MotorConfig()
    lane: LaneConfig = LaneConfig()
    navigation: NavigationConfig = NavigationConfig()
