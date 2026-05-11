from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from raspbot.config import MotorConfig


class MotorLike(Protocol):
    def move_forward(self, speed: int | None = None) -> None: ...
    def move_backward(self, speed: int | None = None) -> None: ...
    def steer_left(self, speed: int | None = None) -> None: ...
    def steer_right(self, speed: int | None = None) -> None: ...
    def spin_left(self, speed: int | None = None) -> None: ...
    def spin_right(self, speed: int | None = None) -> None: ...
    def set_speed(self, left_speed: int, right_speed: int) -> None: ...
    def stop(self) -> None: ...


@dataclass
class MotorCommand:
    left_speed: int
    right_speed: int
    reason: str = ""


class MotorControl:
    """Safe wrapper around the local YB_Pcb_Car driver.

    No .env path is required.

    Required local file:
        robot_side/motor_driver/YB_Pcb_Car.py

    Required class:
        class YB_Pcb_Car
    """

    def __init__(self, config: MotorConfig | None = None):
        self.config = config or MotorConfig()

        try:
            from robot_side.motor_driver.YB_Pcb_Car import YB_Pcb_Car
        except Exception as exc:
            raise RuntimeError(
                "Could not import local motor driver. Expected file: "
                "robot_side/motor_driver/YB_Pcb_Car.py with class YB_Pcb_Car."
            ) from exc

        self.car = YB_Pcb_Car()

    def _clamp(self, speed: int) -> int:
        speed = int(speed)
        return max(-self.config.max_speed, min(self.config.max_speed, speed))

    def set_speed(self, left_speed: int, right_speed: int) -> None:
        left = self._clamp(left_speed)
        right = self._clamp(right_speed)

        if left == 0 and right == 0:
            self.stop()
            return

        if left >= 0 and right >= 0:
            self.car.Car_Run(left, right)
            return

        if left <= 0 and right <= 0:
            self.car.Car_Back(abs(left), abs(right))
            return

        if left < 0 and right > 0:
            self.car.Car_Spin_Left(abs(left), right)
            return

        if left > 0 and right < 0:
            self.car.Car_Spin_Right(left, abs(right))
            return

        self.stop()

    def move_forward(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.forward_speed
        self.set_speed(speed, speed)

    def move_backward(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.forward_speed
        self.set_speed(-speed, -speed)

    def steer_left(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.turn_speed
        slow = max(0, int(speed * 0.55))
        self.set_speed(slow, speed)

    def steer_right(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.turn_speed
        slow = max(0, int(speed * 0.55))
        self.set_speed(speed, slow)

    def spin_left(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.turn_speed
        self.set_speed(-speed, speed)

    def spin_right(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.turn_speed
        self.set_speed(speed, -speed)

    def stop(self) -> None:
        self.car.Car_Stop()

    def timed_stop(self, seconds: float = 0.2) -> None:
        self.stop()
        time.sleep(seconds)


class MockMotorControl:
    """Dry-run motor implementation for testing without moving the robot."""

    def __init__(self, config: MotorConfig | None = None):
        self.config = config or MotorConfig()
        self.last_command = MotorCommand(0, 0, "init")

    def set_speed(self, left_speed: int, right_speed: int) -> None:
        self.last_command = MotorCommand(left_speed, right_speed, "set_speed")
        print(f"[DRY-RUN MOTOR] left={left_speed}, right={right_speed}")

    def move_forward(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.forward_speed
        self.set_speed(speed, speed)

    def move_backward(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.forward_speed
        self.set_speed(-speed, -speed)

    def steer_left(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.turn_speed
        self.set_speed(int(speed * 0.55), speed)

    def steer_right(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.turn_speed
        self.set_speed(speed, int(speed * 0.55))

    def spin_left(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.turn_speed
        self.set_speed(-speed, speed)

    def spin_right(self, speed: int | None = None) -> None:
        speed = speed if speed is not None else self.config.turn_speed
        self.set_speed(speed, -speed)

    def stop(self) -> None:
        self.set_speed(0, 0)

    def timed_stop(self, seconds: float = 0.2) -> None:
        self.stop()
        time.sleep(seconds)
