"""
Motor driver for the Yahboom Raspbot (STM8 @ I2C 0x16 -> AT8236 -> motors).

The Raspbot's motor driver is NOT wired to Raspberry Pi GPIO pins. The Pi
talks to an STM8 MCU over I2C, which in turn drives the AT8236 H-bridge.
We delegate to Yahboom's library YB_Pcb_Car.py — drop it next to this file
(raspbot/hardware/YB_Pcb_Car.py) or install it where Python can import it.
"""

from __future__ import annotations

import time

import raspbot.config as cfg


class MotorDriverError(RuntimeError):
    pass


def _scale_speed(speed: int) -> int:
    speed = max(0, min(100, int(speed)))
    return int(round(speed * 255 / 100))


class MotorController:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.car = None

        if self.dry_run:
            print("[motor] DRY-RUN: motors will not move.")
            return

        try:
            import YB_Pcb_Car  # type: ignore
        except Exception as exc:
            raise MotorDriverError(
                "YB_Pcb_Car library not found.\n"
                "Place YB_Pcb_Car.py at raspbot/hardware/YB_Pcb_Car.py "
                "or install it on PYTHONPATH."
            ) from exc

        self.car = YB_Pcb_Car.YB_Pcb_Car()
        self.stop()

    def forward(self, speed: int) -> None:
        if cfg.INVERT_FORWARD:
            return self.back_no_invert(speed)
        self.forward_no_invert(speed)

    def back(self, speed: int) -> None:
        if cfg.INVERT_FORWARD:
            return self.forward_no_invert(speed)
        self.back_no_invert(speed)

    def forward_no_invert(self, speed: int) -> None:
        s = _scale_speed(speed)
        if self.dry_run:
            print(f"[motor] forward speed={speed} (raw={s})")
            return
        assert self.car is not None
        self.car.Car_Run(s, s)

    def back_no_invert(self, speed: int) -> None:
        s = _scale_speed(speed)
        if self.dry_run:
            print(f"[motor] back speed={speed} (raw={s})")
            return
        assert self.car is not None
        self.car.Car_Back(s, s)

    def spin_left(self, speed: int) -> None:
        if cfg.INVERT_STEERING:
            return self.spin_right_no_invert(speed)
        self.spin_left_no_invert(speed)

    def spin_right(self, speed: int) -> None:
        if cfg.INVERT_STEERING:
            return self.spin_left_no_invert(speed)
        self.spin_right_no_invert(speed)

    def spin_left_no_invert(self, speed: int) -> None:
        s = _scale_speed(speed)
        if self.dry_run:
            print(f"[motor] spin_left speed={speed} (raw={s})")
            return
        assert self.car is not None
        if hasattr(self.car, "Car_Spin_Left"):
            self.car.Car_Spin_Left(s, s)
        else:
            self.car.Car_Left(s, s)

    def spin_right_no_invert(self, speed: int) -> None:
        s = _scale_speed(speed)
        if self.dry_run:
            print(f"[motor] spin_right speed={speed} (raw={s})")
            return
        assert self.car is not None
        if hasattr(self.car, "Car_Spin_Right"):
            self.car.Car_Spin_Right(s, s)
        else:
            self.car.Car_Right(s, s)

    def stop(self) -> None:
        if self.dry_run:
            print("[motor] stop")
            return
        assert self.car is not None
        self.car.Car_Stop()

    def cleanup(self) -> None:
        if self.dry_run:
            return
        try:
            self.stop()
            time.sleep(0.05)
            if self.car is not None:
                del self.car
                self.car = None
        except Exception as exc:
            print(f"[motor] cleanup warning: {exc}")

    def safe_stop(self) -> None:
        self.cleanup()
