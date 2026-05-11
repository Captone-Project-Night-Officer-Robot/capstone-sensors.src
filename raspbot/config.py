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
    yb_pcb_car_path: str = os.getenv(
        "YB_PCB_CAR_PATH",
        "/home/farmscout/Raspbot/2.Hardware Control course/02.Drive motor",
    )

    forward_speed: int = _env_int("RASPBOT_FORWARD_SPEED", 45)
    turn_speed: int = _env_int("RASPBOT_TURN_SPEED", 35)
    slow_speed: int = _env_int("RASPBOT_SLOW_SPEED", 25)
    max_speed: int = 100


@dataclass(frozen=True)
class LaneConfig:
    lower_green_h: int = 35
    lower_green_s: int = 40
    lower_green_v: int = 40

    upper_green_h: int = 80
    upper_green_s: int = 255
    upper_green_v: int = 255

    morphology_kernel_size: int = 5

    roi_top_ratio: float = 0.35
    roi_left_top_ratio: float = 0.05
    roi_right_top_ratio: float = 0.95

    center_cutout_left_ratio: float = 0.25
    center_cutout_right_ratio: float = 0.75

    hough_rho: int = 2
    hough_theta_divisor: int = 180
    hough_threshold: int = 110
    hough_min_line_length: int = 80
    hough_max_line_gap: int = 30

    lane_center_tolerance_px: int = 25
    min_lines_required: int = 2


@dataclass(frozen=True)
class NavigationConfig:
    emergency_stop_cm: float = _env_float("RASPBOT_EMERGENCY_STOP_CM", 10.0)
    caution_cm: float = _env_float("RASPBOT_CAUTION_CM", 20.0)
    max_valid_distance_cm: float = 500.0

    no_lane_behavior: str = "slow_forward"
    control_loop_sleep_sec: float = 0.05


@dataclass(frozen=True)
class AppConfig:
    gpio: GPIOConfig = GPIOConfig()
    camera: CameraConfig = CameraConfig()
    motor: MotorConfig = MotorConfig()
    lane: LaneConfig = LaneConfig()
    navigation: NavigationConfig = NavigationConfig()
